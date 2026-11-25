"""E-MNAR: do the E1 conclusions survive when missing fields depend on the case?

    python -m para_triage.experiments.emnar --seeds 0 1 2 3 4 --jobs 5 --out runs/emnar

E1 drops every field independently (MCAR), which favors imputation. Here the probability that a field is
missing depends on the case (see `para_triage.data.missingness`): on the label (borderline cases are measured
thoroughly) or on the field's own value. The marginal missing rate of every field stays that of MCAR times the
multiplier; `missing_rates.csv` reports the realized rate of every field in every regime.

Cells: 6 regimes (MCAR and 5 mechanisms) x missing multiplier {1, 2}, measurement noise at 1x. Systems: rules,
rules with imputation, gradient boosting, MLP and hybrid, with the hyperparameters chosen in E1. Each cell is
trained and tested on itself (matched) and tested with the models trained under MCAR at (1, 1), which is
what a model trained on E1-style data would meet in practice (mismatched).

Two predictors see only what the missing pattern says: one uses the declared impairments (which identify the
group) alone, the other the impairments plus the mask of every other field. The second minus the first is how
much the pattern tells about the label.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from ..data.features import FEATURE_NAMES
from ..data.missingness import MissingMechanism
from ..data.noise import NoiseConfig
from ..eval import metrics
from . import protocol as P
from .baselines import GbConfig, fit_gb, gb_proba
from .e1 import test_cell, train_cell
from .evaluate import evaluate
from .provenance import provenance, write_json
from .seed_context import SeedContext, load_seed, log, seed_main

REGIMES: tuple[tuple[str, MissingMechanism | None], ...] = (
    ("mcar", None),
    ("label_0.5", MissingMechanism("label", 0.5)),
    ("label_0.9", MissingMechanism("label", 0.9)),
    ("value_up_0.5", MissingMechanism("value_up", 0.5)),
    ("value_up_0.9", MissingMechanism("value_up", 0.9)),
    ("value_down_0.9", MissingMechanism("value_down", 0.9)),
)
MULTIPLIERS = (1.0, 2.0)
MASK_GB = GbConfig(max_iter=60)
IMPAIRMENT_COLUMNS = [i for i, n in enumerate(FEATURE_NAMES) if n.startswith("impairment_")]
OTHER_COLUMNS = [i for i, n in enumerate(FEATURE_NAMES) if not n.startswith("impairment_")]


def cells() -> list[tuple[str, float]]:
    return [(name, mult) for name, _ in REGIMES for mult in MULTIPLIERS]


def realized_rates(true_profiles, seen_profiles, missing_p: dict, report) -> list[dict]:
    """Target, capped probability and realized missing rate of every field of a view."""
    by_field = {r["field"]: r for r in (report.rows if report is not None else [])}
    out = []
    for name, p_f in missing_p.items():
        rows = [i for i, p in enumerate(true_profiles) if getattr(p, name) is not None]
        if not rows:
            continue
        realized = float(np.mean([getattr(seen_profiles[i], name) is None for i in rows]))
        extra = by_field.get(name, {})
        out.append({"field": name, "rows": len(rows), "target": min(1.0, p_f), "realized": realized,
                    "mean_probability": extra.get("mean_probability", min(1.0, p_f)), "clipped_share": extra.get("clipped_share", 0.0)})
    return out


def mask_only_accuracy(view: P.View, split, y_idx, n_classes: int, seed: int) -> dict[str, float]:
    """Accuracy of boosting on the impairments alone, and on the impairments plus the mask of the other fields."""
    train, test = split["train"], split["test"]
    result = {}
    for name, columns in (("group_only", [view.x[:, IMPAIRMENT_COLUMNS]]), ("group_and_mask", [view.x[:, IMPAIRMENT_COLUMNS], view.m[:, OTHER_COLUMNS]])):
        x = np.hstack(columns)
        model = fit_gb(x[train], np.ones_like(x[train]), y_idx[train], MASK_GB, seed)
        p = gb_proba(model, x[test], np.ones_like(x[test]), n_classes)
        result[name] = metrics.accuracy(y_idx[test], p.argmax(1))
    return result


def run_seed(seed: int, out: Path, e1_dir: Path, n_per_label: int, force: bool) -> None:
    sdir = out / f"seed_{seed}"
    if (sdir / "results.csv").exists() and not force:
        log(f"seed {seed}: already done, skipping")
        return
    ctx: SeedContext = load_seed(seed, e1_dir, cells=[P.DEFAULT_CELL, (1.0, 2.0)], n_per_label=n_per_label)
    base = NoiseConfig()
    views: dict[tuple[str, float], P.View] = {}
    rate_rows = []
    for stream, (name, mech) in enumerate(REGIMES):
        for mult in MULTIPLIERS:
            if mech is None:
                view, report = ctx.views[(1.0, mult)], None
            else:
                view, report = P.make_mnar_view(ctx.true, seed, mech, stream, mult, base)
            views[(name, mult)] = view
            for row in realized_rates(ctx.true.profiles, view.profiles, base.scaled(1.0, mult).missing_p, report):
                rate_rows.append({"seed": seed, "regime": name, "multiplier": mult, **row})
    log(f"seed {seed}: {len(views)} views")

    results, mask_rows = [], []
    mcar_model = None
    for key in cells():
        view = views[key]
        trained = train_cell(view, ctx.split, ctx.y, ctx.classes, ctx.mlp_config, ctx.gb_config, seed)
        if key == ("mcar", 1.0):
            mcar_model = trained
        results += rows_for(trained, view, ctx, seed, key, "matched")
        for name, acc in mask_only_accuracy(view, ctx.split, ctx.y, len(ctx.classes), seed).items():
            mask_rows.append({"seed": seed, "regime": key[0], "multiplier": key[1], "predictor": name, "accuracy": acc})
        log(f"seed {seed}: trained and tested on {key}")
    for key in cells():
        results += rows_for(mcar_model, views[key], ctx, seed, key, "mcar_1x")

    # The MCAR cell at (1, 1) is the E1 cell: it must reproduce E1 exactly, or this is not the same experiment.
    e1_res = pd.read_csv(e1_dir / "results.csv")
    ref = e1_res[(e1_res.seed == seed) & (e1_res.train_noise == 1) & (e1_res.train_missing == 1) & (e1_res.test_noise == 1) & (e1_res.test_missing == 1)]
    ours = pd.DataFrame([r for r in results if r["regime"] == "mcar" and r["multiplier"] == 1.0 and r["training"] == "matched"])
    diffs = {s: abs(float(ours[ours.system == s].accuracy.iloc[0]) - float(ref[ref.system == s].accuracy.iloc[0])) for s in ours.system.unique()}
    sdir.mkdir(parents=True, exist_ok=True)
    write_json(sdir / "sanity.json", {"max_abs_accuracy_difference_to_e1": max(diffs.values()), "matches_e1": max(diffs.values()) < 1e-9, "by_system": diffs})
    pd.DataFrame(rate_rows).to_csv(sdir / "missing_rates.csv", index=False)
    pd.DataFrame(mask_rows).to_csv(sdir / "mask_only.csv", index=False)
    pd.DataFrame(results).to_csv(sdir / "results.csv", index=False)  # last: marks the seed as done
    log(f"seed {seed}: done")


def rows_for(trained, view: P.View, ctx: SeedContext, seed: int, key: tuple[str, float], training: str) -> list[dict]:
    r = test_cell(trained, view, ctx.split["test"])
    rows, _, _ = evaluate(r["y"], r["groups"], ctx.classes, r["rules"], r["rules_imp"], r["p_mlp"], r["p_gb"])
    return [{"seed": seed, "regime": key[0], "multiplier": key[1], "training": training, **row} for row in rows]


FILES = ("results", "mask_only", "missing_rates")


def aggregate(out: Path, seeds: list[int]) -> None:
    for name in FILES:
        frames = [pd.read_csv(out / f"seed_{s}" / f"{name}.csv") for s in seeds if (out / f"seed_{s}" / f"{name}.csv").exists()]
        if frames:
            pd.concat(frames, ignore_index=True).to_csv(out / f"{name}.csv", index=False)


def write_config(out: Path, seeds: list[int], n_per_label: int) -> None:
    write_json(
        out / "config.json",
        {
            "experiment": "E-MNAR",
            "seeds": seeds,
            "n_per_label": n_per_label,
            "uses": "runs/e1: split.npz and tuning.json of each seed (the chosen MLP and boosting configurations)",
            "mechanism_declared_before_running": {
                "probability_of_missing": "p_f * multiplier * m_i / mean(m_i over the rows that have the field f), capped at 1; p_f is the MCAR rate of E1",
                "marginal_rate": "each field keeps its MCAR marginal rate times the multiplier; realized rates and capped shares are in missing_rates.csv",
                "label": "m_i = 1 - s if the label is ambiguous (-1), else 1; borderline cases are measured thoroughly, clear ones less",
                "value_up": "m_i = 1 + s (2 z_i - 1), z_i the mid-rank ECDF of the field's true value; higher values go missing more often",
                "value_down": "the same with 1 - z_i",
                "unordered_fields": "sex, posture and cerebral palsy distribution keep m_i = 1 in the value mechanisms",
                "regimes": {name: ({"kind": m.kind, "strength": m.strength} if m else "MCAR, as in E1") for name, m in REGIMES},
                "multipliers": list(MULTIPLIERS),
                "noise": "default level (1x)",
            },
            "cells": [list(c) for c in cells()],
            "systems": ["rules", "rules_imp", "gb", "mlp", "hybrid"],
            "training": {"matched": "each cell trained and tested on itself", "mcar_1x": "models trained under MCAR at (1, 1), tested on every cell"},
            "mask_only_predictors": {"group_only": "boosting on the declared impairments", "group_and_mask": "boosting on the impairments plus the mask of every other field",
                                       "boosting_config": MASK_GB.__dict__},
            "nothing_tuned_on_test": True,
            **provenance(),
        },
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--e1", type=Path, default=Path("runs/e1"))
    parser.add_argument("--out", type=Path, default=Path("runs/emnar"))
    parser.add_argument("--n-per-label", type=int, default=P.N_PER_LABEL)
    seed_main(
        "para_triage.experiments.emnar",
        parser,
        argv,
        run_one=lambda seed, a: run_seed(seed, a.out, a.e1, a.n_per_label, a.force),
        write_config=lambda a: write_config(a.out, a.seeds, a.n_per_label),
        aggregate=lambda a: aggregate(a.out, a.seeds),
        extra_args=lambda a: ["--e1", str(a.e1), "--n-per-label", str(a.n_per_label)],
    )


if __name__ == "__main__":
    main()
