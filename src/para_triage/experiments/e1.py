"""E1: sweeps of measurement noise and of missing fields, matched and mismatched.

    python -m para_triage.experiments.e1 --seeds 0 1 2 3 4 --jobs 5 --out runs/e1

For each seed there is one set of true profiles and one noisy view per (noise, missing) cell.
Models are trained on one cell and tested on the held-out rows of another. Matched means the
same cell for training and testing; mismatched models are trained at (1, 1) and at (0, 0) and
tested on every cell. Hyperparameters of the MLP and of gradient boosting are chosen on the
validation rows of the (1, 1) view, from four configurations each, and kept for every other cell.
"""
from __future__ import annotations

import argparse
import dataclasses
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from ..data import NoiseConfig
from ..data.generator import TrueSamples
from ..models.mlp import Standardizer, TrainConfig, fit_model, fit_temperature, predict_logits, softmax
from ..models.train import save_checkpoint
from . import protocol as P
from .baselines import GbConfig, RuleImputer, fit_gb, gb_proba, imputed_rule_labels
from .evaluate import evaluate
from .provenance import provenance, write_json
from .splits import MODES, split_for

MLP_GRID = (
    TrainConfig(),
    TrainConfig(hidden=(256, 128), dropout=0.3, lr=1e-3),
    TrainConfig(hidden=(64, 32), dropout=0.1),
    TrainConfig(weight_decay=1e-3, feature_dropout=0.2),
)
GB_GRID = (
    GbConfig(),
    GbConfig(max_leaf_nodes=31, l2_regularization=1.0),
    GbConfig(max_iter=200, learning_rate=0.05, l2_regularization=1.0),
    GbConfig(max_iter=150, max_leaf_nodes=7),
)
SELECTION = "validation negative log-likelihood"


@dataclass
class Trained:
    scaler: Standardizer
    mlp: object
    temperature: float
    gb: object
    imputer: RuleImputer
    classes: np.ndarray


def _log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def fit_mlp(view: P.View, split, y_idx, n_classes: int, cfg: TrainConfig):
    train, val = split["train"], split["val"]
    scaler = Standardizer().fit(view.x[train], view.m[train])
    xs = scaler.transform(view.x, view.m)
    model, history = fit_model(
        (xs[train], view.m[train], y_idx[train]), (xs[val], view.m[val], y_idx[val]), n_classes, cfg
    )
    logits_val = predict_logits(model, xs[val], view.m[val])
    return scaler, model, fit_temperature(logits_val, y_idx[val]), len(history)


def val_nll(proba: np.ndarray, y: np.ndarray) -> float:
    return float(-np.log(np.clip(proba[np.arange(len(y)), y], 1e-12, 1.0)).mean())


def tune(view: P.View, split, y_idx, n_classes: int, seed: int) -> dict:
    """Chooses one configuration per model on the validation rows of the (1, 1) view."""
    val = split["val"]
    out: dict = {"selection": SELECTION, "mlp": [], "gb": []}
    for i, cfg in enumerate(MLP_GRID):
        t = time.perf_counter()
        cfg = dataclasses.replace(cfg, seed=seed)
        scaler, model, temp, epochs = fit_mlp(view, split, y_idx, n_classes, cfg)
        xs = scaler.transform(view.x[val], view.m[val])
        score = val_nll(softmax(predict_logits(model, xs, view.m[val]), temp), y_idx[val])
        out["mlp"].append({"index": i, "config": dataclasses.asdict(cfg), "val_nll": score, "epochs": epochs})
        _log(f"seed {seed} tune mlp {i}: val NLL {score:.4f} ({time.perf_counter() - t:.0f}s)")
    for i, cfg in enumerate(GB_GRID):
        t = time.perf_counter()
        train = split["train"]
        model = fit_gb(view.x[train], view.m[train], y_idx[train], cfg, seed)
        score = val_nll(gb_proba(model, view.x[val], view.m[val], n_classes), y_idx[val])
        out["gb"].append({"index": i, "config": dataclasses.asdict(cfg), "val_nll": score})
        _log(f"seed {seed} tune gb {i}: val NLL {score:.4f} ({time.perf_counter() - t:.0f}s)")
    out["mlp_chosen"] = int(np.argmin([r["val_nll"] for r in out["mlp"]]))
    out["gb_chosen"] = int(np.argmin([r["val_nll"] for r in out["gb"]]))
    return out


def train_cell(view: P.View, split, y_idx, classes, mlp_cfg: TrainConfig, gb_cfg: GbConfig, seed: int) -> Trained:
    train = split["train"]
    scaler, model, temp, _ = fit_mlp(view, split, y_idx, len(classes), mlp_cfg)
    gb = fit_gb(view.x[train], view.m[train], y_idx[train], gb_cfg, seed)
    imputer = RuleImputer().fit([view.profiles[i] for i in train])
    return Trained(scaler, model, temp, gb, imputer, classes)


def test_cell(trained: Trained, view: P.View, test: np.ndarray) -> dict:
    """Probabilities and rule labels of every system on the test rows of `view`."""
    x, m = view.x[test], view.m[test]
    p_mlp = softmax(predict_logits(trained.mlp, trained.scaler.transform(x, m), m), trained.temperature)
    p_gb = gb_proba(trained.gb, x, m, len(trained.classes))
    rules_imp = imputed_rule_labels(trained.imputer, [view.profiles[i] for i in test])
    sub = view.df.iloc[test]
    return {
        "y": sub["label"].to_numpy(),
        "groups": sub["group"].to_numpy(),
        "rules": sub["rule_label"].to_numpy(),
        "rules_imp": rules_imp,
        "p_mlp": p_mlp,
        "p_gb": p_gb,
    }


def run_seed(seed: int, out: Path, cells: list[P.Cell], n_per_label: int, force: bool = False, split_mode: str = "row") -> None:
    sdir = out / f"seed_{seed}"
    if (sdir / "results.csv").exists() and not force:
        _log(f"seed {seed}: already done, skipping")
        return
    sdir.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()

    all_cells = list(dict.fromkeys([*cells, P.DEFAULT_CELL, P.CLEAN_CELL]))
    true, views = P.make_views(seed, all_cells, n_per_label)
    _log(f"seed {seed}: {len(true)} true profiles, {len(views)} views ({time.perf_counter() - t0:.0f}s)")
    classes = np.unique(true.labels)
    y_idx = np.searchsorted(classes, true.labels)
    split = split_for(split_mode, true, seed)
    np.savez(sdir / "split.npz", classes=classes, mode=np.array(split_mode), **split)

    tuning = tune(views[P.DEFAULT_CELL], split, y_idx, len(classes), seed)
    write_json(sdir / "tuning.json", tuning)
    mlp_cfg = dataclasses.replace(MLP_GRID[tuning["mlp_chosen"]], seed=seed)
    gb_cfg = GB_GRID[tuning["gb_chosen"]]

    results, extras, by_group = [], [], []
    for train_cell_ in cells:
        t = time.perf_counter()
        trained = train_cell(views[train_cell_], split, y_idx, classes, mlp_cfg, gb_cfg, seed)
        if train_cell_ == P.DEFAULT_CELL:
            artifacts = {
                "model": trained.mlp,
                "classes": classes,
                "scaler": trained.scaler,
                "temperature": trained.temperature,
            }
            save_checkpoint(artifacts, mlp_cfg, sdir / "mlp_default.pt")
        test_cells = cells if train_cell_ in (P.DEFAULT_CELL, P.CLEAN_CELL) else [train_cell_]
        for tc in test_cells:
            r = test_cell(trained, views[tc], split["test"])
            sys_rows, ex, grp = evaluate(r["y"], r["groups"], classes, r["rules"], r["rules_imp"], r["p_mlp"], r["p_gb"])
            key = {
                "seed": seed,
                "train_noise": train_cell_[0],
                "train_missing": train_cell_[1],
                "test_noise": tc[0],
                "test_missing": tc[1],
            }
            results += [{**key, **row} for row in sys_rows]
            extras.append({**key, **ex})
            by_group += [{**key, **row} for row in grp]
        _log(f"seed {seed}: trained on {train_cell_}, tested on {len(test_cells)} cell(s) ({time.perf_counter() - t:.0f}s)")

    pd.DataFrame(extras).to_csv(sdir / "extras.csv", index=False)
    pd.DataFrame(by_group).to_csv(sdir / "by_group.csv", index=False)
    pd.DataFrame(results).to_csv(sdir / "results.csv", index=False)  # last: marks the seed as done
    _log(f"seed {seed}: done in {time.perf_counter() - t0:.0f}s")


def aggregate(out: Path, seeds: list[int]) -> None:
    for name in ("results", "extras", "by_group"):
        frames = [pd.read_csv(out / f"seed_{s}" / f"{name}.csv") for s in seeds if (out / f"seed_{s}" / f"{name}.csv").exists()]
        if frames:
            pd.concat(frames, ignore_index=True).to_csv(out / f"{name}.csv", index=False)


def write_config(out: Path, args, cells, seeds) -> None:
    write_json(
        out / "config.json",
        {
            "experiment": "E1",
            "seeds": seeds,
            "n_per_label": args.n_per_label,
            "split": dict(zip(("train", "val", "cal", "test"), P.SPLIT)),
            "split_mode": args.split_mode,
            "split_mode_meaning": {"row": "random by row, stratified by group and label", "profile_by_label": "by true profile within each (group, label): no profile in two parts, labels stay in training"},
            "noise_levels": sorted({c[0] for c in cells}),
            "missing_levels": sorted({c[1] for c in cells}),
            "default_noise_config": dataclasses.asdict(NoiseConfig()),
            "mismatched_training_cells": [P.DEFAULT_CELL, P.CLEAN_CELL],
            "mlp_grid": [dataclasses.asdict(c) for c in MLP_GRID],
            "gb_grid": [dataclasses.asdict(c) for c in GB_GRID],
            "tuning": f"4 configurations each, chosen per seed on the (1, 1) view by {SELECTION}, then fixed",
            "streams": "profiles from default_rng(seed); each view from SeedSequence([seed, 1000*noise, 1000*missing])",
            **provenance(),
        },
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2, 3, 4])
    parser.add_argument("--jobs", type=int, default=1, help="seeds run in parallel as separate processes")
    parser.add_argument("--threads", type=int, default=3, help="threads per process when --jobs > 1")
    parser.add_argument("--out", type=Path, default=Path("runs/e1"))
    parser.add_argument("--n-per-label", type=int, default=P.N_PER_LABEL)
    parser.add_argument("--split-mode", choices=MODES, default="row", help="how the rows are divided into train, validation, calibration and test")
    parser.add_argument("--noise-levels", type=float, nargs="+", default=list(P.NOISE_LEVELS))
    parser.add_argument("--missing-levels", type=float, nargs="+", default=list(P.MISSING_LEVELS))
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--aggregate-only", action="store_true")
    args = parser.parse_args(argv)
    cells = P.cell_grid(args.noise_levels, args.missing_levels)

    if args.aggregate_only:
        aggregate(args.out, args.seeds)
        return
    if args.jobs > 1 and len(args.seeds) > 1:
        env = {**os.environ, "OMP_NUM_THREADS": str(args.threads), "MKL_NUM_THREADS": str(args.threads)}
        args.out.mkdir(parents=True, exist_ok=True)
        write_config(args.out, args, cells, args.seeds)
        pending, running = list(args.seeds), []
        while pending or running:
            while pending and len(running) < args.jobs:
                seed = pending.pop(0)
                cmd = [sys.executable, "-m", "para_triage.experiments.e1", "--seeds", str(seed), "--out", str(args.out),
                       "--n-per-label", str(args.n_per_label), "--threads", str(args.threads), "--split-mode", args.split_mode,
                       "--noise-levels", *map(str, args.noise_levels), "--missing-levels", *map(str, args.missing_levels)]
                if args.force:
                    cmd.append("--force")
                running.append(subprocess.Popen(cmd, env=env))
            running = [p for p in running if p.poll() is None]
            time.sleep(2)
        aggregate(args.out, args.seeds)
        return

    import torch

    torch.set_num_threads(int(os.environ.get("OMP_NUM_THREADS", args.threads if args.jobs > 1 else torch.get_num_threads())))
    for seed in args.seeds:
        run_seed(seed, args.out, cells, args.n_per_label, args.force, args.split_mode)
    if len(args.seeds) > 1:
        write_config(args.out, args, cells, args.seeds)
    aggregate(args.out, args.seeds)


if __name__ == "__main__":
    main()
