"""E3: realistic prevalence and values away from the rule thresholds.

    python -m para_triage.experiments.e3 --seeds 0 1 2 3 4 --jobs 5 --out runs/e3

The training data are balanced by label and concentrate values near the rule thresholds, so E1 numbers do not
transfer to a population. Two parts, both on the models trained at (1, 1) in E1, never retrained:

(a) Prevalence scenarios. The E1 test rows are reweighted so that every (group, label) cell has the share a
    scenario prescribes. The scenarios are illustrative stress tests, not estimates from data. Reweighting
    corrects the shift in label frequencies only.
(b) A "natural" sampler: values drawn from the broad clinical ranges, without the extra mass near the
    thresholds and without balancing by label. This also moves the features; the label frequencies are
    whatever the rules give. Not tuned or matched to any real population.

Conformal sets (LAC, alpha 0.1) are calibrated on the balanced calibration rows of E1 and tested under
each scenario; the per-class (Mondrian) version is run for comparison.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from ..data import NoiseConfig
from ..data.generator import ABSTAIN, TrueSamples, observe_samples, sample_natural_profiles
from ..data.features import encode_profiles
from ..eval import metrics
from . import conformal as C
from . import protocol as P
from .provenance import provenance, write_json
from .seed_context import DefaultModels, SeedContext, default_models, load_seed, log, seed_main

ALPHA = 0.1
SYSTEMS = ("rules", "rules_imp", "gb", "mlp", "hybrid")
NATURAL_ROWS_PER_GROUP = 2000
NATURAL_SEED_OFFSET = 10_000
# Fixed, arbitrary orders used by the skewed scenarios (declared in config.json).
GROUP_ORDER = ("limb_standing", "visual", "wheelchair", "neuro_standing", "limb_prosthesis", "neuro_seated",
               "short_stature", "intellectual", "frame_runner")
SCENARIOS = {
    "balanced": "every label equally likely within its group; groups in proportion to their number of labels (the training distribution)",
    "screening": "as balanced, but the label 'no eligible class' (0) is 5 times as likely as any other label of its group",
    "rare_borderline": "as balanced, but the ambiguous label (-1) is 0.2 times as likely",
    "skewed_classes": "within each group, label weights 1/rank with the order: classes by increasing id, then 0, then -1",
    "skewed_groups": "group weights 1/rank in GROUP_ORDER; labels equally likely within a group",
    "combined": "skewed_groups together with screening",
}


def label_order(labels: list[int]) -> list[int]:
    return sorted(l for l in labels if l > 0) + [l for l in (0, -1) if l in labels]


def label_weight(scenario: str, rank: int, label: int) -> float:
    w = 1.0
    if scenario == "skewed_classes":
        w = 1.0 / rank
    if scenario in ("screening", "combined") and label == 0:
        w *= 5.0
    if scenario == "rare_borderline" and label == -1:
        w *= 0.2
    return w


def target_weights(groups: np.ndarray, labels: np.ndarray, scenario: str) -> dict[tuple[str, int], float]:
    """Target probability of every (group, label) cell, normalised to 1, from the cells present in the data."""
    cells: dict[str, list[int]] = {}
    for g, l in set(zip(groups.tolist(), labels.tolist())):
        cells.setdefault(g, []).append(int(l))
    weight: dict[tuple[str, int], float] = {}
    for g, ls in cells.items():
        group_w = 1.0 / (GROUP_ORDER.index(g) + 1) if scenario in ("skewed_groups", "combined") else float(len(ls))
        raw = {l: label_weight(scenario, rank, l) for rank, l in enumerate(label_order(ls), start=1)}
        total = sum(raw.values())
        for l, w in raw.items():
            weight[(g, l)] = group_w * w / total
    z = sum(weight.values())
    return {k: v / z for k, v in weight.items()}


def row_weights(groups: np.ndarray, labels: np.ndarray, scenario: str) -> np.ndarray:
    """Importance weight of each row: the scenario's share of its cell over the cell's share in the rows."""
    target = target_weights(groups, labels, scenario)
    keys = list(zip(groups.tolist(), labels.tolist()))
    counts = pd.Series(keys).value_counts()
    n = len(keys)
    return np.array([target[k] / (counts[k] / n) for k in keys])


def wmean(values: np.ndarray, w: np.ndarray) -> float:
    return float((values * w).sum() / w.sum()) if len(values) and w.sum() > 0 else float("nan")


def predictions(classes, rules, rules_imp, p_mlp, p_gb) -> dict[str, np.ndarray]:
    mlp = classes[p_mlp.argmax(1)]
    return {"rules": rules, "rules_imp": rules_imp, "gb": classes[p_gb.argmax(1)], "mlp": mlp, "hybrid": np.where(rules == ABSTAIN, mlp, rules)}


def weighted_system_rows(y, preds, rules, w, **key) -> list[dict]:
    rows = []
    for name, pred in preds.items():
        decided = pred != ABSTAIN if name in ("rules", "rules_imp") else np.ones(len(y), dtype=bool)
        rows.append({**key, "system": name, "accuracy": wmean(pred == y, w), "coverage": wmean(decided, w),
                     "accuracy_decided": wmean((pred == y)[decided], w[decided])})
    return rows


def conformal_rows(models: DefaultModels, ctx: SeedContext, p_test: np.ndarray, y_test: np.ndarray, w: np.ndarray, **key) -> list[dict]:
    """LAC and per-class LAC sets, calibrated on the balanced E1 calibration rows, scored under weights w."""
    default, cal = ctx.views[P.DEFAULT_CELL], ctx.split["cal"]
    p_cal = models.mlp_proba(default.x[cal], default.m[cal])
    rows = []
    for method, per_class in (("LAC", False), ("LAC_Mondrian", True)):
        sets = C.conformal_sets(p_cal, ctx.y[cal], p_test, ALPHA, method, per_class)
        covered = sets[np.arange(len(y_test)), y_test]
        size = sets.sum(1)
        rows.append({**key, "method": method, "coverage": wmean(covered, w), "size": wmean(size, w),
                     "frac_singleton": wmean(size == 1, w), "frac_empty": wmean(size == 0, w)})
    return rows


def run_seed(seed: int, out: Path, e1_dir: Path, n_per_label: int, force: bool) -> None:
    sdir = out / f"seed_{seed}"
    if (sdir / "scenarios.csv").exists() and not force:
        log(f"seed {seed}: already done, skipping")
        return
    ctx = load_seed(seed, e1_dir, cells=[P.DEFAULT_CELL], n_per_label=n_per_label)
    models = default_models(ctx)
    classes, test = ctx.classes, ctx.split["test"]
    view = ctx.views[P.DEFAULT_CELL]
    x, m = view.x[test], view.m[test]
    p_mlp, p_gb = models.mlp_proba(x, m), models.gb_proba(x, m)
    rules = view.df["rule_label"].to_numpy()[test]
    rules_imp = models.imputed_rules([view.profiles[i] for i in test])
    y_label, groups, y_idx = ctx.true.labels[test], np.asarray(ctx.true.groups)[test], ctx.y[test]
    preds = predictions(classes, rules, rules_imp, p_mlp, p_gb)

    scenario_rows, scenario_conformal = [], []
    for scenario in SCENARIOS:
        w = row_weights(groups, y_label, scenario)
        scenario_rows += weighted_system_rows(y_label, preds, rules, w, seed=seed, scenario=scenario)
        scenario_conformal += conformal_rows(models, ctx, p_mlp, y_idx, w, seed=seed, scenario=scenario)

    # (b) natural sampler, observed with the default noise and missing fields
    natural, dropped = sample_natural_profiles(NATURAL_ROWS_PER_GROUP, seed=seed + NATURAL_SEED_OFFSET)
    rng = P.view_rng(seed + NATURAL_SEED_OFFSET, P.DEFAULT_CELL)
    seen, df = observe_samples(natural, NoiseConfig(), rng)
    xn, mn = encode_profiles(seen)
    keep = np.isin(natural.labels, classes)  # every label exists in training, but be explicit
    p_mlp_n, p_gb_n = models.mlp_proba(xn, mn), models.gb_proba(xn, mn)
    rules_n = df["rule_label"].to_numpy()
    imp_n = models.imputed_rules(seen)
    y_n, groups_n = natural.labels, np.asarray(natural.groups)
    preds_n = predictions(classes, rules_n, imp_n, p_mlp_n, p_gb_n)
    ones = np.ones(len(y_n))
    natural_rows = weighted_system_rows(y_n, preds_n, rules_n, ones, seed=seed, scope="all")
    natural_groups = []
    for g in np.unique(groups_n):
        sel = groups_n == g
        natural_groups += weighted_system_rows(y_n[sel], {k: v[sel] for k, v in preds_n.items()}, rules_n[sel], ones[sel], seed=seed, scope=g)
    y_n_idx = np.searchsorted(classes, y_n)
    natural_conformal = conformal_rows(models, ctx, p_mlp_n, y_n_idx, ones, seed=seed, scope="all")
    for g in np.unique(groups_n):
        sel = groups_n == g
        natural_conformal += conformal_rows(models, ctx, p_mlp_n[sel], y_n_idx[sel], ones[sel], seed=seed, scope=g)
    labels_share = pd.Series(y_n).value_counts(normalize=True).rename_axis("label").reset_index(name="share")
    labels_share.insert(0, "seed", seed)
    meta = pd.DataFrame([{"seed": seed, "rows": len(y_n), "dropped_unlabelled_draws": dropped, "labels_outside_training": int((~keep).sum())}])

    sdir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(scenario_conformal).to_csv(sdir / "scenario_conformal.csv", index=False)
    pd.concat([pd.DataFrame(natural_rows), pd.DataFrame(natural_groups)]).to_csv(sdir / "natural.csv", index=False)
    pd.DataFrame(natural_conformal).to_csv(sdir / "natural_conformal.csv", index=False)
    labels_share.to_csv(sdir / "natural_labels.csv", index=False)
    meta.to_csv(sdir / "natural_meta.csv", index=False)
    pd.DataFrame(scenario_rows).to_csv(sdir / "scenarios.csv", index=False)  # last: marks the seed as done
    log(f"seed {seed}: done")


FILES = ("scenarios", "scenario_conformal", "natural", "natural_conformal", "natural_labels", "natural_meta")


def aggregate(out: Path, seeds: list[int]) -> None:
    for name in FILES:
        frames = [pd.read_csv(out / f"seed_{s}" / f"{name}.csv") for s in seeds if (out / f"seed_{s}" / f"{name}.csv").exists()]
        if frames:
            pd.concat(frames, ignore_index=True).to_csv(out / f"{name}.csv", index=False)


def write_config(out: Path, seeds: list[int], n_per_label: int) -> None:
    write_json(
        out / "config.json",
        {
            "experiment": "E3",
            "seeds": seeds,
            "n_per_label": n_per_label,
            "uses": "runs/e1: split, MLP checkpoint at (1, 1) and tuning of each seed; models are not retrained",
            "scenarios": SCENARIOS,
            "group_order_for_skewed_groups": list(GROUP_ORDER),
            "scenario_note": "illustrative stress tests; not estimated from any population",
            "weights": "row weight = scenario share of its (group, label) cell / share of the cell in the test rows",
            "natural_sampler": {
                "rows_per_group": NATURAL_ROWS_PER_GROUP,
                "values": "broad clinical ranges; mass near the rule thresholds switched off (sampling.natural_ranges)",
                "labels": "not balanced; drawn profiles the rules cannot label are dropped and counted",
                "observation": "default noise and missing fields, as in cell (1, 1)",
                "seed": f"seed + {NATURAL_SEED_OFFSET}",
            },
            "conformal": {"alpha": ALPHA, "score": "LAC and LAC per class (Mondrian)", "calibration": "balanced calibration rows of E1, not recalibrated"},
            "nothing_tuned_on_test": True,
            **provenance(),
        },
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--e1", type=Path, default=Path("runs/e1"))
    parser.add_argument("--out", type=Path, default=Path("runs/e3"))
    parser.add_argument("--n-per-label", type=int, default=P.N_PER_LABEL)
    seed_main(
        "para_triage.experiments.e3",
        parser,
        argv,
        run_one=lambda seed, a: run_seed(seed, a.out, a.e1, a.n_per_label, a.force),
        write_config=lambda a: write_config(a.out, a.seeds, a.n_per_label),
        aggregate=lambda a: aggregate(a.out, a.seeds),
        extra_args=lambda a: ["--e1", str(a.e1), "--n-per-label", str(a.n_per_label)],
    )


if __name__ == "__main__":
    main()
