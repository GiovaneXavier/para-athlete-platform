"""Exports the aggregated results of `runs/` to a small versioned JSON for the transparency panel (K11).

    python -m para_triage.transparency.export --runs <path to runs/> [--out web/public/transparency.json]

`--runs` may also come from the PARA_RUNS_DIR environment variable. The web and the API never read
`runs/` at run time: this script is the only reader, and its output is committed. Only aggregates
are exported (means and spreads across seeds); no vignette, answer key, profile or local path.

Every metric here is level N1: agreement with labels produced by the same rules, under simulated
noise. The source columns are called `accuracy`; they are renamed `agreement` on the way out so the
word never labels a rule-fidelity number.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from ..provenance_info.rules_version import CORE_FILES
from ..provenance_info import (
    EVIDENCE_LEVEL,
    EVIDENCE_NOTICE,
    checkpoint_info,
    rules_version,
    rules_version_from_contents,
)
from ..rules.catalog import load_catalog

SCHEMA_VERSION = 1
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUT = REPO_ROOT / "web" / "public" / "transparency.json"
RULES_COVERAGE_DOC = REPO_ROOT / "docs" / "rules_coverage.md"
CHANGELOG = Path(__file__).with_name("rules_changelog.json")
RULES_REL = "src/para_triage/rules"

USAGE_NOTICE = (
    "Triagem e estudo: esta página não é classificação oficial. A classificação esportiva é feita por "
    "classificadores do CPB e da World Para Athletics."
)
SPLITS = {"row": "", "profile_by_label": "_profile"}  # split mode -> suffix of the runs folder
MATCHED_CELL = (1.0, 1.0)  # (noise, missing) multipliers of the default level
MAIN_ALPHA = 0.1
ALPHAS = (0.05, 0.1, 0.2)
CONFORMAL_METHODS = ("LAC", "APS")

# Written by hand: known divergences and limits of the rules, not experiment results.
KNOWN_DIVERGENCES = [
    {
        "id": "class-20-onset-age",
        "classes": [20],
        "text": (
            "Classe 20 (deficiência intelectual): o livreto do CPB (2024) fixa o início aos 22 anos e as regras "
            "da World Para Athletics (2023) aos 18. O catálogo segue o livreto; a divergência está em aberto."
        ),
    },
    {
        "id": "seated-t-f-equivalence",
        "classes": [51, 52, 53, 54, 55, 56, 57],
        "text": (
            "Cadeiras (51 a 57): a equivalência entre a classe F e a classe T é inferência nossa a partir das "
            "descrições do livreto, não uma tabela oficial, e precisa de confirmação."
        ),
    },
    {
        "id": "events-and-equipment",
        "classes": [],
        "text": "Provas e equipamentos por classe ainda não foram validados.",
    },
]

# Source column -> exported name. `accuracy` never leaves this module.
RENAME = {
    "accuracy": "agreement",
    "accuracy_decided": "agreement_when_decided",
    "singleton_accuracy": "singleton_agreement",
    "decided_accuracy": "decided_agreement",
    "selective_accuracy_at_rules_coverage": "selective_agreement_at_rules_coverage",
    "selective_accuracy_at_50": "selective_agreement_at_50",
    "selective_accuracy_at_70": "selective_agreement_at_70",
    "selective_accuracy_at_90": "selective_agreement_at_90",
    "accuracy_full": "agreement_full",
}


class ExportError(RuntimeError):
    """A clear, user-facing reason why the export cannot run."""


# --- small helpers ---------------------------------------------------------------------------------------


def stat(values) -> dict:
    """Mean and spread of one number per seed (sd with ddof=1; 0 when there is a single seed)."""
    series = pd.Series(list(values), dtype=float).dropna()
    if series.empty:
        return {"mean": None, "sd": None, "min": None, "max": None, "n": 0}
    n = len(series)
    sd = float(series.std(ddof=1)) if n > 1 else 0.0
    return {
        "mean": _r(series.mean()),
        "sd": _r(sd),
        "min": _r(series.min()),
        "max": _r(series.max()),
        "n": n,
    }


def _r(x) -> float | None:
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(float(x), 6)


def _stats_by_seed(frame: pd.DataFrame, columns: list[str]) -> dict:
    """One `stat` per column, taken over the per-seed means of `frame` (one or more rows per seed)."""
    per_seed = frame.groupby("seed")[columns].mean()
    return {RENAME.get(c, c): stat(per_seed[c]) for c in columns}


def _read(runs: Path, relative: str) -> pd.DataFrame:
    path = runs / relative
    if not path.is_file():
        raise ExportError(f"arquivo esperado não encontrado: {relative} (em {runs})")
    return pd.read_csv(path)


def _config(runs: Path, folder: str) -> dict:
    path = runs / folder / "config.json"
    if not path.is_file():
        raise ExportError(f"config.json não encontrado: {folder}/config.json (em {runs})")
    return json.loads(path.read_text(encoding="utf-8"))


def _clean_command(command: str) -> str:
    """Script name and arguments only: the original command holds a local path."""
    match = re.search(r"([^\\/\s]+\.py)\s*(.*)$", command)
    return f"{match.group(1)} {match.group(2)}".strip() if match else ""


def _source(config: dict) -> dict:
    out = {
        "commit": config.get("commit"),
        "code_tree_dirty": config.get("code_tree_dirty"),
        "written_at": config.get("written_at"),
        "n_seeds": len(config.get("seeds", [])),
        "seeds": config.get("seeds", []),
        "split_mode": config.get("split_mode"),
        "command": _clean_command(config.get("command", "")),
        "python": config.get("python"),
        "torch": config.get("torch"),
        "scikit_learn": config.get("scikit_learn"),
    }
    if "n_per_label" in config:
        out["n_per_label"] = config["n_per_label"]
    if "split" in config:
        out["split"] = config["split"]
    return out


def _cell(frame: pd.DataFrame, prefix_noise: str, prefix_missing: str) -> pd.DataFrame:
    noise, missing = MATCHED_CELL
    return frame[(frame[prefix_noise] == noise) & (frame[prefix_missing] == missing)]


# --- E1 ---------------------------------------------------------------------------------------------------


def export_e1(runs: Path, folder: str) -> dict:
    results = _read(runs, f"{folder}/results.csv")
    matched = results[(results.train_noise == MATCHED_CELL[0]) & (results.train_missing == MATCHED_CELL[1])]
    matched = _cell(matched, "test_noise", "test_missing")
    metrics = ["accuracy", "macro_f1", "coverage", "accuracy_decided"]
    systems = {name: _stats_by_seed(rows, metrics) for name, rows in matched.groupby("system", sort=False)}
    extras = _read(runs, f"{folder}/extras.csv")
    extras = _cell(_cell_train(extras), "test_noise", "test_missing")
    calibration = _stats_by_seed(extras, ["mlp_top2", "mlp_ece", "mlp_nll", "mlp_brier"])
    return {
        "source": _source(_config(runs, folder)),
        "cell": {"noise": MATCHED_CELL[0], "missing": MATCHED_CELL[1], "training": "matched"},
        "systems": systems,
        "mlp_calibration": calibration,
    }


def _cell_train(frame: pd.DataFrame) -> pd.DataFrame:
    return frame[(frame.train_noise == MATCHED_CELL[0]) & (frame.train_missing == MATCHED_CELL[1])]


# --- E7 ---------------------------------------------------------------------------------------------------


def export_e7(runs: Path, folder: str) -> dict:
    marginal = _read(runs, f"{folder}/marginal.csv")
    base = marginal[marginal.model.eq("mlp")]
    base = base[(base.cal_noise == MATCHED_CELL[0]) & (base.cal_missing == MATCHED_CELL[1])]
    base = _cell(base, "test_noise", "test_missing")
    columns = [
        "coverage",
        "size",
        "frac_singleton",
        "frac_decided",
        "frac_empty",
        "frac_has_ambiguous",
        "singleton_accuracy",
        "decided_accuracy",
    ]
    conformal: dict = {}
    for method in CONFORMAL_METHODS:
        for alpha in ALPHAS:
            rows = base[base.method.eq(method) & base.alpha.round(6).eq(alpha)]
            if rows.empty:
                raise ExportError(f"E7 sem linhas para {method} com alfa {alpha} em {folder}/marginal.csv")
            conformal.setdefault(method, {})[str(alpha)] = {
                "metrics": _stats_by_seed(rows, columns),
                "coverage_min_over_splits": _r(rows.coverage.min()),
                "n_splits_total": int(len(rows)),
            }

    conditional = _read(runs, f"{folder}/conditional.csv")
    conditional = conditional[
        conditional.model.eq("mlp")
        & conditional.method.eq("LAC")
        & conditional.alpha.round(6).eq(MAIN_ALPHA)
        & conditional.cell_noise.eq(MATCHED_CELL[0])
        & conditional.cell_missing.eq(MATCHED_CELL[1])
    ]
    by_missing = _conditional(conditional, "missing_fields")
    by_group = _conditional(conditional, "group")

    selective = _read(runs, f"{folder}/selective_summary.csv")
    selective_cols = [
        "aurc",
        "rules_coverage",
        "selective_accuracy_at_rules_coverage",
        "selective_accuracy_at_50",
        "selective_accuracy_at_70",
        "selective_accuracy_at_90",
        "accuracy_full",
    ]
    selective_out = {
        method: _stats_by_seed(rows, selective_cols)
        for method, rows in selective[selective.method.isin(["mlp_maxprob", "gb_maxprob"])].groupby("method")
    }

    config = _config(runs, folder)
    return {
        "source": _source(config),
        "declared_before_running": config.get("declared_before_running"),
        "main_alpha": MAIN_ALPHA,
        "calibration_cell": {"noise": MATCHED_CELL[0], "missing": MATCHED_CELL[1]},
        "conformal": conformal,
        "coverage_by_missing_fields": by_missing,
        "coverage_by_group": by_group,
        "selective": selective_out,
    }


def _conditional(frame: pd.DataFrame, by: str) -> dict:
    out = {}
    rows = frame[frame["by"] == by]
    for value, group in rows.groupby("value", sort=True):
        per_seed = group.groupby("seed")[["coverage", "size", "n"]].mean()
        out[str(value)] = {
            "coverage": stat(per_seed.coverage),
            "size": stat(per_seed["size"]),
            "n_per_split": _r(per_seed.n.mean()),
        }
    return out


# --- V1 ---------------------------------------------------------------------------------------------------


def export_v1(runs: Path) -> dict:
    accuracy = _read(runs, "v1/accuracy.csv")
    by_subset: dict = {}
    for (subset, system), rows in accuracy.groupby(["subset", "system"], sort=False):
        entry = by_subset.setdefault(subset, {"n_test_rows": _r(rows.groupby("seed").n.mean().mean()), "systems": {}})
        entry["systems"][system] = {"agreement": stat(rows.groupby("seed").accuracy.mean())}

    duplicates = _read(runs, "v1/duplicates.csv")
    shares = {}
    for column in ("share_true_duplicate", "share_observed_duplicate"):
        weighted = duplicates.assign(w=duplicates[column] * duplicates.n_test).groupby("seed").w.sum()
        shares[column] = stat(weighted / duplicates.groupby("seed").n_test.sum())

    grouped = _read(runs, "v1/grouped_systems.csv")
    split_variants = {}
    for variant, rows in grouped.groupby("variant", sort=False):
        split_variants[variant] = {
            name: _stats_by_seed(system_rows, ["accuracy", "macro_f1", "coverage"])
            for name, system_rows in rows.groupby("system", sort=False)
        }
    meta = _read(runs, "v1/grouped_meta.csv")
    for variant, rows in meta.groupby("variant", sort=False):
        split_variants[variant]["_split"] = _stats_by_seed(
            rows, ["n_train", "n_test", "share_test_label_unseen_in_train", "unique_true_profiles"]
        )
    split_variants = {
        v: {"systems": {k: x for k, x in d.items() if k != "_split"}, "split": d["_split"]}
        for v, d in split_variants.items()
    }

    return {
        "source": _source(_config(runs, "v1")),
        "duplicates_in_test": shares,
        "agreement_by_duplicate_subset": by_subset,
        "new_profile_splits": split_variants,
    }


# --- rules, model card, documents ------------------------------------------------------------------------


def _git(*args: str) -> bytes | None:
    try:
        done = subprocess.run(["git", "-C", str(REPO_ROOT), *args], capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout if done.returncode == 0 else None


def rules_id_at_commit(commit: str) -> str | None:
    """Rule book id as it was at `commit`, read from git; None when git or the commit is unavailable."""
    listing = _git("ls-tree", "-r", "--name-only", commit, f"{RULES_REL}/evaluators/")
    catalog = _git("show", f"{commit}:{RULES_REL}/classes.yaml")
    if listing is None or catalog is None:
        return None
    contents = {"classes.yaml": catalog}
    for name in CORE_FILES[1:]:
        blob = _git("show", f"{commit}:{RULES_REL}/{name}")
        if blob is None:
            return None
        contents[name] = blob
    for line in listing.decode().splitlines():
        if line.endswith(".py"):
            blob = _git("show", f"{commit}:{line}")
            if blob is None:
                return None
            contents[line.removeprefix(f"{RULES_REL}/")] = blob
    return rules_version_from_contents(contents).id


def export_rules(commits: dict[str, str | None]) -> dict:
    current = rules_version()
    catalog = load_catalog()
    at_source = {name: (rules_id_at_commit(c) if c else None) for name, c in commits.items()}
    return {
        "id": current.id,
        "sha256": current.sha256,
        "files": [{"path": path, "sha256": digest} for path, digest in current.files],
        "n_classes": len(catalog.classes),
        "n_groups": len(catalog.groups),
        "id_at_source_commit": at_source,
        "unchanged_since_runs": {
            name: (None if rid is None else rid == current.id) for name, rid in at_source.items()
        },
    }


def parse_rule_groups(markdown: str) -> list[dict]:
    """The group table of docs/rules_coverage.md: group, classes, state, origin of the criteria."""
    section = markdown.split("## Classes", 1)[1].split("\n## ", 1)[0]
    groups = []
    for line in section.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 4 or cells[0] in ("Grupo", "") or set(cells[0]) <= {"-"}:
            continue
        state = cells[2].replace("*", "").strip()
        category = (
            "provisional" if state.startswith("provis") else "partial" if state.startswith("parcial") else "implemented"
        )
        groups.append(
            {"group": cells[0], "classes": cells[1], "state": state, "category": category, "origin": cells[3]}
        )
    if not groups:
        raise ExportError("nenhuma linha de grupo encontrada na tabela de docs/rules_coverage.md")
    return groups


def export_model_card(runs: Path) -> dict | None:
    info = checkpoint_info(runs / "mlp_v1" / "model.pt")
    if info is None:
        return None
    card = asdict(info)
    card["limits"] = list(info.limits)
    return card


# --- assembly --------------------------------------------------------------------------------------------


def build_payload(runs: Path) -> dict:
    runs = Path(runs)
    if not runs.is_dir():
        raise ExportError(
            f"a pasta runs/ não existe em {runs}. Passe --runs <caminho> ou defina PARA_RUNS_DIR "
            "(a pasta é ignorada pelo git e fica na máquina de quem rodou os experimentos)."
        )
    experiments: dict = {}
    for name, exporter in (("E1", export_e1), ("E7", export_e7)):
        experiments[name] = {
            "evidence_level": EVIDENCE_LEVEL,
            "splits": {mode: exporter(runs, f"{name.lower()}{suffix}") for mode, suffix in SPLITS.items()},
        }
    experiments["V1"] = {"evidence_level": EVIDENCE_LEVEL, **export_v1(runs)}

    commits = {
        "E1": experiments["E1"]["splits"]["row"]["source"]["commit"],
        "E7": experiments["E7"]["splits"]["row"]["source"]["commit"],
        "V1": experiments["V1"]["source"]["commit"],
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "evidence_level": EVIDENCE_LEVEL,
        "evidence_notice": EVIDENCE_NOTICE,
        "usage_notice": USAGE_NOTICE,
        "rules": export_rules(commits),
        "rule_groups": parse_rule_groups(RULES_COVERAGE_DOC.read_text(encoding="utf-8")),
        "known_divergences": KNOWN_DIVERGENCES,
        "changelog": json.loads(CHANGELOG.read_text(encoding="utf-8")),
        "model_card": export_model_card(runs),
        "experiments": experiments,
    }


def dumps(payload: dict) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--runs", type=Path, default=None, help="pasta runs/ (ou PARA_RUNS_DIR)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="onde gravar o JSON")
    args = parser.parse_args(argv)
    runs = args.runs or (Path(os.environ["PARA_RUNS_DIR"]) if os.environ.get("PARA_RUNS_DIR") else None)
    try:
        if runs is None:
            raise ExportError("informe a pasta runs/ com --runs <caminho> ou a variável PARA_RUNS_DIR.")
        text = dumps(build_payload(runs))
    except ExportError as error:
        print(f"erro: {error}", file=sys.stderr)
        return 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8", newline="\n")
    print(f"gravado {args.out} ({len(text.encode('utf-8'))} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
