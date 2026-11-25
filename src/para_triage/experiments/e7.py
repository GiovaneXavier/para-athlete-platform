"""E7: selective prediction and split conformal prediction, for the MLP and for gradient boosting.

    python -m para_triage.experiments.e7 --seeds 0 1 2 3 4 --jobs 5 --out runs/e7

Reuses what E1 saved (`runs/e1`): the split of each seed, the MLP trained at (1, 1) and the chosen
gradient-boosting configuration. Both models are trained once per seed on the (1, 1) view and are
scored on every noisy view of that seed.

Declared before running (see config.json): LAC is the primary conformal score and APS the secondary
one; alpha = 0.1 is the main level; nothing is tuned or chosen on the test rows. Conformal sets are
calibrated on one random half of the 4,140 held-out rows (calibration + test of the split) and
evaluated on the other half, repeated for 20 repartitions per seed. The repartitions reuse the same
rows, so their spread understates the variation between datasets; the spread between seeds does not.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

from ..models.mlp import predict_logits, softmax
from ..models.predict import Predictor
from . import conformal as C
from . import protocol as P
from .baselines import _FIELDS, RuleImputer, fit_gb, gb_proba, imputed_rule_labels
from .e1 import GB_GRID, _log
from .provenance import provenance, write_json
from .splits import halves

ALPHAS = (0.05, 0.1, 0.2)
ALPHA_MAIN = 0.1
N_SPLITS = 20
METHODS = ("LAC", "APS")
PRIMARY_METHOD = "LAC"
MODELS = ("mlp", "gb")
CONDITIONAL_CELLS = (P.DEFAULT_CELL, (1.0, 2.0))
BAND_CUTS = (0, 1, 2)  # missing applicable fields: 0, 1, 2 or more (shares in missing_bands.json)
SELECTIVE_COVERAGES = (0.5, 0.7, 0.9)


def missing_counts(true, view: P.View) -> np.ndarray:
    """Applicable fields (recorded in the true profile) that the observed profile lacks."""
    return np.array(
        [sum(getattr(t, f) is not None and getattr(s, f) is None for f in _FIELDS) for t, s in zip(true.profiles, view.profiles)]
    )


def band(counts: np.ndarray) -> np.ndarray:
    top = BAND_CUTS[-1]
    return np.array([f"{top}+" if c >= top else str(c) for c in counts])


def cell_key(prefix: str, cell: P.Cell) -> dict:
    return {f"{prefix}_noise": cell[0], f"{prefix}_missing": cell[1]}


def selective_outputs(seed: int, y: np.ndarray, probs: dict, rules: np.ndarray, rules_imp: np.ndarray, classes: np.ndarray):
    """Risk-coverage curves, summary per confidence score, and the operating points of the other systems."""
    from ..data.generator import ABSTAIN

    correct = {m: classes[probs[m].argmax(1)] == classes[y] for m in probs}
    scores = {
        "mlp_maxprob": (probs["mlp"], C.max_prob, correct["mlp"]),
        "mlp_margin": (probs["mlp"], C.margin, correct["mlp"]),
        "gb_maxprob": (probs["gb"], C.max_prob, correct["gb"]),
        "gb_margin": (probs["gb"], C.margin, correct["gb"]),
    }
    y_label = classes[y]
    rules_cov = float((rules != ABSTAIN).mean())
    curve, summary = [], []
    for name, (p, fn, ok) in scores.items():
        conf = fn(p)
        for k in range(1, 101):
            curve.append({"seed": seed, "method": name, "coverage": k / 100, "selective_accuracy": C.selective_accuracy_at(conf, ok, k / 100)})
        row = {"seed": seed, "method": name, "aurc": C.aurc(conf, ok), "rules_coverage": rules_cov,
               "selective_accuracy_at_rules_coverage": C.selective_accuracy_at(conf, ok, rules_cov)}
        for c in SELECTIVE_COVERAGES:
            row[f"selective_accuracy_at_{round(100 * c)}"] = C.selective_accuracy_at(conf, ok, c)
        row["accuracy_full"] = float(ok.mean())
        summary.append(row)

    decided, decided_imp = rules != ABSTAIN, rules_imp != ABSTAIN
    hybrid = np.where(decided, rules, classes[probs["mlp"].argmax(1)])
    points = [
        {"seed": seed, "system": "rules", "coverage": rules_cov, "selective_accuracy": float((rules[decided] == y_label[decided]).mean())},
        {"seed": seed, "system": "rules_imp", "coverage": float(decided_imp.mean()),
         "selective_accuracy": float((rules_imp[decided_imp] == y_label[decided_imp]).mean())},
        {"seed": seed, "system": "hybrid", "coverage": 1.0, "selective_accuracy": float((hybrid == y_label).mean())},
    ]
    return pd.DataFrame(curve), pd.DataFrame(summary), pd.DataFrame(points)


def run_seed(
    seed: int, e1_dir: Path, out: Path, n_splits: int, force: bool = False,
    n_per_label: int = P.N_PER_LABEL, cells: list[P.Cell] | None = None,
) -> None:
    sdir = out / f"seed_{seed}"
    if (sdir / "marginal.csv").exists() and not force:
        _log(f"seed {seed}: already done, skipping")
        return
    sdir.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()

    cells = cells or P.cell_grid()
    true, views = P.make_views(seed, cells, n_per_label)
    e1s = e1_dir / f"seed_{seed}"
    sp = np.load(e1s / "split.npz")
    split_mode = str(sp["mode"]) if "mode" in sp.files else "row"  # E1 runs from before the option are by row
    classes = sp["classes"]
    y = np.searchsorted(classes, true.labels)
    amb = int(np.where(classes == -1)[0][0])
    pool = np.sort(np.concatenate([sp["cal"], sp["test"]]))
    test_pos = np.searchsorted(pool, sp["test"])
    train = sp["train"]
    groups = np.asarray(true.groups)

    default = views[P.DEFAULT_CELL]
    predictor = Predictor.load(e1s / "mlp_default.pt")
    tuning = json.loads((e1s / "tuning.json").read_text(encoding="utf-8"))
    gb = fit_gb(default.x[train], default.m[train], y[train], GB_GRID[tuning["gb_chosen"]], seed)
    imputer = RuleImputer().fit([default.profiles[i] for i in train])

    probs = {"mlp": {}, "gb": {}}
    for cell, v in views.items():
        x, m = v.x[pool], v.m[pool]
        probs["mlp"][cell] = softmax(predict_logits(predictor.model, predictor.scaler.transform(x, m), m), predictor.temperature)
        probs["gb"][cell] = gb_proba(gb, x, m, len(classes))
    _log(f"seed {seed}: models loaded, probabilities for {len(views)} views ({time.perf_counter() - t0:.0f}s)")

    # The numbers must match E1 for the same models, or this is not the same experiment.
    e1_res = pd.read_csv(e1_dir / "results.csv")
    sanity = {}
    for name in MODELS:
        ours = float((classes[probs[name][P.DEFAULT_CELL][test_pos].argmax(1)] == true.labels[sp["test"]]).mean())
        ref = e1_res[(e1_res.seed == seed) & (e1_res.train_noise == 1) & (e1_res.train_missing == 1)
                     & (e1_res.test_noise == 1) & (e1_res.test_missing == 1) & (e1_res.system == name)]["accuracy"].iloc[0]
        sanity[name] = {"e7": ours, "e1": float(ref), "match": abs(ours - ref) < 1e-6}
        if not sanity[name]["match"]:
            warnings.warn(f"seed {seed}: {name} accuracy differs from E1 ({ours:.6f} vs {ref:.6f})")
    write_json(sdir / "sanity.json", sanity)

    # Selective prediction on the E1 test rows of the (1, 1) view.
    test_view_df = default.df.iloc[sp["test"]]
    rules_imp = imputed_rule_labels(imputer, [default.profiles[i] for i in sp["test"]])
    curve, summary, points = selective_outputs(
        seed, y[sp["test"]], {m: probs[m][P.DEFAULT_CELL][test_pos] for m in MODELS},
        test_view_df["rule_label"].to_numpy(), rules_imp, classes,
    )
    curve.to_csv(sdir / "selective_curve.csv", index=False)
    summary.to_csv(sdir / "selective_summary.csv", index=False)
    points.to_csv(sdir / "selective_points.csv", index=False)

    # Conditioning variables of the pool rows, per cell where they are reported.
    bands, band_shares = {}, {}
    for cell in CONDITIONAL_CELLS:
        counts = missing_counts(true, views[cell])[pool]
        bands[cell] = band(counts)
        band_shares[f"{cell[0]:g},{cell[1]:g}"] = {k: float((bands[cell] == k).mean()) for k in sorted(set(bands[cell]))}
    write_json(sdir / "missing_bands.json", {"cuts": f"0, 1, {BAND_CUTS[-1]} or more", "shares_of_pool_rows": band_shares})

    y_pool = y[pool]
    strata = pd.Series(groups[pool]).str.cat(pd.Series(true.labels[pool].astype(str)), sep="|")
    marginal, conditional = [], []
    for r in range(n_splits):
        a, b = halves(split_mode, true, pool, seed * 1000 + r)  # random by row, or by true profile
        for model in MODELS:
            for method in (*METHODS, f"{PRIMARY_METHOD}_Mondrian"):
                mondrian = method.endswith("_Mondrian")
                for alpha in ALPHAS:
                    base = {"seed": seed, "split": r, "model": model, "method": method, "alpha": alpha}
                    test_cells = [P.DEFAULT_CELL] if mondrian else cells
                    for tc in test_cells:
                        for cc in dict.fromkeys([P.DEFAULT_CELL, tc]):
                            sets = C.conformal_sets(probs[model][cc][a], y_pool[a], probs[model][tc][b], alpha, method, per_class=mondrian)
                            marginal.append({**base, **cell_key("cal", cc), **cell_key("test", tc), **C.set_metrics(sets, y_pool[b], amb)})
                            if cc == tc and tc in CONDITIONAL_CELLS:
                                keys = {"group": groups[pool][b], "class": classes[y_pool[b]].astype(str), "missing_fields": bands[tc][b]}
                                cond = C.coverage_by(sets, y_pool[b], keys)
                                for k, v in {**base, **cell_key("cell", tc)}.items():
                                    cond[k] = v
                                conditional.append(cond)
        if r % 5 == 4:
            _log(f"seed {seed}: conformal split {r + 1}/{n_splits} ({time.perf_counter() - t0:.0f}s)")

    pd.concat(conditional, ignore_index=True).to_csv(sdir / "conditional.csv", index=False)
    pd.DataFrame(marginal).to_csv(sdir / "marginal.csv", index=False)  # last: marks the seed as done
    _log(f"seed {seed}: done in {time.perf_counter() - t0:.0f}s")


def aggregate(out: Path, seeds: list[int]) -> None:
    for name in ("marginal", "conditional", "selective_curve", "selective_summary", "selective_points"):
        frames = [pd.read_csv(out / f"seed_{s}" / f"{name}.csv") for s in seeds if (out / f"seed_{s}" / f"{name}.csv").exists()]
        if frames:
            pd.concat(frames, ignore_index=True).to_csv(out / f"{name}.csv", index=False)


def write_config(out: Path, seeds: list[int], n_splits: int, e1_dir: Path = Path("runs/e1")) -> None:
    e1_config = e1_dir / "config.json"
    split_mode = json.loads(e1_config.read_text(encoding="utf-8")).get("split_mode", "row") if e1_config.exists() else "row"
    write_json(
        out / "config.json",
        {
            "experiment": "E7",
            "seeds": seeds,
            "uses": f"{e1_dir}: split.npz, mlp_default.pt and tuning.json of each seed",
            "split_mode": split_mode,
            "halves": "random by row, stratified by group and label" if split_mode == "row" else "by true profile within each (group, label), so calibration and test halves share no profile",
            "models": "MLP (temperature scaled) and gradient boosting, both trained once at (1, 1)",
            "declared_before_running": {
                "primary_conformal_score": PRIMARY_METHOD,
                "secondary_conformal_score": "APS (non-randomized)",
                "main_alpha": ALPHA_MAIN,
                "alphas": list(ALPHAS),
                "confidence": "maximum probability (margin as ablation)",
                "nothing_tuned_on_test": True,
            },
            "conformal": "half of calibration+test rows calibrate, the other half tests; repeated n_splits times per seed",
            "n_splits_per_seed": n_splits,
            "rows_in_the_pool": "calibration + test rows of the E1 split",
            "conditioning": {"group": "9 rule groups", "class": "label", "missing_fields_bands": f"0, 1, {BAND_CUTS[-1]} or more applicable fields missing",
                             "cells": [list(c) for c in CONDITIONAL_CELLS]},
            "shift": "calibrate on the (1, 1) view or on the tested view; model always trained at (1, 1)",
            **provenance(),
        },
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2, 3, 4])
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--threads", type=int, default=3)
    parser.add_argument("--e1", type=Path, default=Path("runs/e1"))
    parser.add_argument("--out", type=Path, default=Path("runs/e7"))
    parser.add_argument("--n-splits", type=int, default=N_SPLITS)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--aggregate-only", action="store_true")
    args = parser.parse_args(argv)

    if args.aggregate_only:
        aggregate(args.out, args.seeds)
        return
    if args.jobs > 1 and len(args.seeds) > 1:
        env = {**os.environ, "OMP_NUM_THREADS": str(args.threads), "MKL_NUM_THREADS": str(args.threads)}
        args.out.mkdir(parents=True, exist_ok=True)
        write_config(args.out, args.seeds, args.n_splits, args.e1)
        pending, running = list(args.seeds), []
        while pending or running:
            while pending and len(running) < args.jobs:
                cmd = [sys.executable, "-m", "para_triage.experiments.e7", "--seeds", str(pending.pop(0)), "--out", str(args.out),
                       "--e1", str(args.e1), "--n-splits", str(args.n_splits), "--threads", str(args.threads)]
                if args.force:
                    cmd.append("--force")
                running.append(subprocess.Popen(cmd, env=env))
            running = [p for p in running if p.poll() is None]
            time.sleep(2)
        aggregate(args.out, args.seeds)
        return

    import torch

    torch.set_num_threads(int(os.environ.get("OMP_NUM_THREADS", args.threads)))
    for seed in args.seeds:
        run_seed(seed, args.e1, args.out, args.n_splits, args.force)
    if len(args.seeds) > 1:
        write_config(args.out, args.seeds, args.n_splits, args.e1)
    aggregate(args.out, args.seeds)


if __name__ == "__main__":
    main()
