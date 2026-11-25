"""V1: do identical profiles appear in the training and the test rows?

    python -m para_triage.experiments.v1 --seeds 0 1 2 3 4 --jobs 5 --out runs/v1

The split of E1 is by row, and the generator draws discrete profiles (amputation levels, functional ratings,
yes/no answers) that repeat. A test row whose true profile also sits in the training rows can be answered by
memory, which inflates its accuracy. Measured on the E1 split, with the models of E1:
  - the share of test rows whose TRUE profile appears among the training rows, per group;
  - the share whose OBSERVED profile (noise and missing fields included) appears among the observed training rows;
  - accuracy of every system on test rows with and without such a duplicate.
Nothing is excluded from the E1 results; this only says how much they depend on repeats.

Then the same pipeline is run once more at the default cell on a split BY TRUE PROFILE (no profile in two parts),
with the hyperparameters chosen in E1 (not retuned). Where the space of true profiles is small (amputation
levels, functional ratings), this asks the model for profiles it has never seen; where values are continuous
(vision, stature) it changes little. Labels that exist only in test profiles cannot be learned, and their
share is reported.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from ..eval import metrics
from . import protocol as P
from .e1 import test_cell, train_cell
from .evaluate import evaluate, system_predictions
from .provenance import provenance, write_json
from .splits import profile_split
from .seed_context import default_models, load_seed, log, seed_main


def duplicate_flags(profiles, train: np.ndarray, test: np.ndarray) -> np.ndarray:
    """For each test row: is its profile equal to the profile of some training row."""
    seen = {profiles[i] for i in train}
    return np.array([profiles[i] in seen for i in test])


VARIANTS = ("profile", "profile_by_label")


def run_grouped(ctx, seed: int, variant: str) -> tuple[list[dict], list[dict], list[dict]]:
    """E1's default cell, trained and tested on a split by true profile (same hyperparameters, no retuning)."""
    split = profile_split(ctx.true.profiles, ctx.true.groups, seed, ctx.true.labels if variant == "profile_by_label" else None)
    view = ctx.views[P.DEFAULT_CELL]
    trained = train_cell(view, split, ctx.y, ctx.classes, ctx.mlp_config, ctx.gb_config, seed)
    r = test_cell(trained, view, split["test"])
    sys_rows, _, grp_rows = evaluate(r["y"], r["groups"], ctx.classes, r["rules"], r["rules_imp"], r["p_mlp"], r["p_gb"])
    train_labels = set(ctx.true.labels[split["train"]].tolist())
    unseen = np.array([l not in train_labels for l in ctx.true.labels[split["test"]]])
    meta = [{"seed": seed, "variant": variant, "n_train": len(split["train"]), "n_test": len(split["test"]), "share_test_label_unseen_in_train": float(unseen.mean()),
             "unique_true_profiles": len(set(ctx.true.profiles))}]
    return [{"seed": seed, "variant": variant, **row} for row in sys_rows], [{"seed": seed, "variant": variant, **row} for row in grp_rows], meta


def run_seed(seed: int, out: Path, e1_dir: Path, n_per_label: int, force: bool) -> None:
    sdir = out / f"seed_{seed}"
    if (sdir / "accuracy.csv").exists() and not force:
        log(f"seed {seed}: already done, skipping")
        return
    ctx = load_seed(seed, e1_dir, cells=[P.DEFAULT_CELL], n_per_label=n_per_label)
    models = default_models(ctx)
    view = ctx.views[P.DEFAULT_CELL]
    train, test = ctx.split["train"], ctx.split["test"]
    true_dup = duplicate_flags(ctx.true.profiles, train, test)
    obs_dup = duplicate_flags(view.profiles, train, test)

    groups = np.asarray(ctx.true.groups)[test]
    rows = []
    for g in [*sorted(set(groups)), "all"]:
        sel = np.ones(len(test), dtype=bool) if g == "all" else groups == g
        rows.append({"seed": seed, "group": g, "n_test": int(sel.sum()), "share_true_duplicate": float(true_dup[sel].mean()), "share_observed_duplicate": float(obs_dup[sel].mean())})

    x, m = view.x[test], view.m[test]
    preds = system_predictions(
        ctx.classes, view.df["rule_label"].to_numpy()[test], models.imputed_rules([view.profiles[i] for i in test]), models.mlp_proba(x, m), models.gb_proba(x, m)
    )
    y = ctx.true.labels[test]
    acc_rows = []
    for subset, flag in (("true_duplicate", true_dup), ("no_true_duplicate", ~true_dup), ("observed_duplicate", obs_dup), ("no_observed_duplicate", ~obs_dup), ("all", np.ones(len(test), dtype=bool))):
        for name, pred in preds.items():
            acc_rows.append({"seed": seed, "subset": subset, "system": name, "n": int(flag.sum()), "accuracy": metrics.accuracy(y[flag], pred[flag]) if flag.any() else float("nan")})
    # per group, for the systems that learn
    group_rows = []
    for g in sorted(set(groups)):
        for subset, flag in (("true_duplicate", true_dup), ("no_true_duplicate", ~true_dup)):
            sel = (groups == g) & flag
            for name in ("mlp", "gb"):
                group_rows.append({"seed": seed, "group": g, "subset": subset, "system": name, "n": int(sel.sum()), "accuracy": metrics.accuracy(y[sel], preds[name][sel]) if sel.any() else float("nan")})

    grouped_sys, grouped_grp, grouped_meta = [], [], []
    for variant in VARIANTS:
        a, b, c = run_grouped(ctx, seed, variant)
        grouped_sys, grouped_grp, grouped_meta = grouped_sys + a, grouped_grp + b, grouped_meta + c
    sdir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(grouped_sys).to_csv(sdir / "grouped_systems.csv", index=False)
    pd.DataFrame(grouped_grp).to_csv(sdir / "grouped_by_group.csv", index=False)
    pd.DataFrame(grouped_meta).to_csv(sdir / "grouped_meta.csv", index=False)
    pd.DataFrame(rows).to_csv(sdir / "duplicates.csv", index=False)
    pd.DataFrame(group_rows).to_csv(sdir / "accuracy_by_group.csv", index=False)
    pd.DataFrame(acc_rows).to_csv(sdir / "accuracy.csv", index=False)  # last: marks the seed as done
    log(f"seed {seed}: done")


FILES = ("duplicates", "accuracy", "accuracy_by_group", "grouped_systems", "grouped_by_group", "grouped_meta")


def aggregate(out: Path, seeds: list[int]) -> None:
    for name in FILES:
        frames = [pd.read_csv(out / f"seed_{s}" / f"{name}.csv") for s in seeds if (out / f"seed_{s}" / f"{name}.csv").exists()]
        if frames:
            pd.concat(frames, ignore_index=True).to_csv(out / f"{name}.csv", index=False)


def write_config(out: Path, seeds: list[int], n_per_label: int) -> None:
    write_json(
        out / "config.json",
        {
            "experiment": "V1",
            "seeds": seeds,
            "n_per_label": n_per_label,
            "uses": "runs/e1: split.npz, MLP checkpoint and tuning of each seed; nothing is retrained or excluded",
            "duplicate": "a test row whose profile is exactly equal (every field) to the profile of some training row",
            "profiles_compared": ["true (before noise and missing fields)", "observed at the default level (1, 1)"],
            "grouped_split": {
                "profile": "by true profile within each group, 60/10/15/15 of the rows; labels that exist only in test profiles cannot be learned",
                "profile_by_label": "by true profile within each (group, label): a test profile is new but its label is not (a label with one profile stays in training)",
                "models": "retrained at (1, 1) with the E1 configurations, not retuned",
            },
            **provenance(),
        },
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--e1", type=Path, default=Path("runs/e1"))
    parser.add_argument("--out", type=Path, default=Path("runs/v1"))
    parser.add_argument("--n-per-label", type=int, default=P.N_PER_LABEL)
    seed_main(
        "para_triage.experiments.v1",
        parser,
        argv,
        run_one=lambda seed, a: run_seed(seed, a.out, a.e1, a.n_per_label, a.force),
        write_config=lambda a: write_config(a.out, a.seeds, a.n_per_label),
        aggregate=lambda a: aggregate(a.out, a.seeds),
        extra_args=lambda a: ["--e1", str(a.e1), "--n-per-label", str(a.n_per_label)],
    )


if __name__ == "__main__":
    main()
