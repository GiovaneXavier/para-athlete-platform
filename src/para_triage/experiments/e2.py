"""E2: ablations of the masked MLP (feature dropout, missing-field mask) and a thresholded hybrid.

    python -m para_triage.experiments.e2 --seeds 0 1 2 3 4 --jobs 5 --out runs/e2

Variants (hyperparameters as chosen in E1 for each seed, one change at a time):
  full        the model of E1
  no_dropout  feature_dropout = 0 (no extra random masking during training)
  no_mask     the model is not told which fields are missing (they read as the training mean)
  no_dropout_no_mask  both changes, to separate the effect of each from their combination
Each variant is trained at (1, 1) and at (0, 0), and tested on the held-out rows of all 16 cells. Training at
(0, 0) shows what feature dropout alone buys, since that training set has no missing field.

The thresholded hybrid answers with the MLP when its confidence is at least tau or the rules abstain, and with
the rules otherwise; tau is chosen on the validation rows of the training cell from a grid fixed in advance.
"""
from __future__ import annotations

import argparse
import dataclasses
from pathlib import Path

import numpy as np
import pandas as pd

from ..data.generator import ABSTAIN
from ..eval import metrics
from ..models.mlp import predict_logits, softmax
from . import protocol as P
from .e1 import fit_mlp
from .provenance import provenance, write_json
from .seed_context import SeedContext, load_seed, log, seed_main

VARIANTS = {
    "full": {},
    "no_dropout": {"feature_dropout": 0.0},
    "no_mask": {"use_mask": False},
    "no_dropout_no_mask": {"feature_dropout": 0.0, "use_mask": False},
}
TRAIN_CELLS = (P.DEFAULT_CELL, P.CLEAN_CELL)
TAU_GRID = (0.0, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99, 1.01)  # 0 = always the MLP, 1.01 = rules whenever they decide


def probabilities(trained, view: P.View, rows: np.ndarray) -> np.ndarray:
    scaler, model, temperature = trained
    x, m = view.x[rows], view.m[rows]
    return softmax(predict_logits(model, scaler.transform(x, m), m), temperature)


def hybrid_predictions(p: np.ndarray, rules: np.ndarray, classes: np.ndarray, tau: float) -> np.ndarray:
    mlp = classes[p.argmax(1)]
    use_mlp = (rules == ABSTAIN) | (p.max(1) >= tau)
    return np.where(use_mlp, mlp, rules)


def choose_tau(p_val: np.ndarray, rules_val: np.ndarray, y_val: np.ndarray, classes: np.ndarray) -> float:
    accs = [metrics.accuracy(y_val, hybrid_predictions(p_val, rules_val, classes, t)) for t in TAU_GRID]
    return TAU_GRID[int(np.argmax(accs))]  # first best: ties go to the smaller tau, i.e. more reliance on the MLP


def run_seed(seed: int, out: Path, e1_dir: Path, n_per_label: int, force: bool) -> None:
    sdir = out / f"seed_{seed}"
    if (sdir / "results.csv").exists() and not force:
        log(f"seed {seed}: already done, skipping")
        return
    ctx: SeedContext = load_seed(seed, e1_dir, n_per_label=n_per_label)
    cells = P.cell_grid()
    val, test = ctx.split["val"], ctx.split["test"]
    rows = []
    for variant, change in VARIANTS.items():
        cfg = dataclasses.replace(ctx.mlp_config, **change)
        for train_cell in TRAIN_CELLS:
            train_view = ctx.views[train_cell]
            scaler, model, temperature, epochs = fit_mlp(train_view, ctx.split, ctx.y, len(ctx.classes), cfg)
            trained = (scaler, model, temperature)
            p_val = probabilities(trained, train_view, val)
            tau = choose_tau(p_val, train_view.df["rule_label"].to_numpy()[val], ctx.true.labels[val], ctx.classes)
            for test_cell in cells:
                view = ctx.views[test_cell]
                p = probabilities(trained, view, test)
                y_label, y_idx = ctx.true.labels[test], ctx.y[test]
                rules = view.df["rule_label"].to_numpy()[test]
                mlp = ctx.classes[p.argmax(1)]
                decided = rules != ABSTAIN
                rows.append(
                    {
                        "seed": seed,
                        "variant": variant,
                        "train_noise": train_cell[0],
                        "train_missing": train_cell[1],
                        "test_noise": test_cell[0],
                        "test_missing": test_cell[1],
                        "accuracy": metrics.accuracy(y_label, mlp),
                        "macro_f1": metrics.macro_f1(y_label, mlp),
                        "accuracy_rules_decided": metrics.accuracy(y_label[decided], mlp[decided]),
                        "accuracy_rules_abstain": metrics.accuracy(y_label[~decided], mlp[~decided]),
                        "ece": metrics.ece(p, y_idx),
                        "nll": metrics.nll(p, y_idx),
                        "tau": tau,
                        "accuracy_hybrid_tau": metrics.accuracy(y_label, hybrid_predictions(p, rules, ctx.classes, tau)),
                        "accuracy_hybrid": metrics.accuracy(y_label, hybrid_predictions(p, rules, ctx.classes, TAU_GRID[-1])),
                        "accuracy_rules": metrics.accuracy(y_label, rules),
                        "epochs": epochs,
                    }
                )
        log(f"seed {seed}: variant {variant} done")
    sdir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(sdir / "results.csv", index=False)  # last: marks the seed as done


def aggregate(out: Path, seeds: list[int]) -> None:
    frames = [pd.read_csv(out / f"seed_{s}" / "results.csv") for s in seeds if (out / f"seed_{s}" / "results.csv").exists()]
    if frames:
        pd.concat(frames, ignore_index=True).to_csv(out / "results.csv", index=False)


def write_config(out: Path, seeds: list[int], n_per_label: int) -> None:
    write_json(
        out / "config.json",
        {
            "experiment": "E2",
            "seeds": seeds,
            "n_per_label": n_per_label,
            "uses": "runs/e1: split.npz and tuning.json of each seed (the chosen MLP configuration)",
            "variants": {k: v or "none (the E1 model)" for k, v in VARIANTS.items()},
            "train_cells": [list(c) for c in TRAIN_CELLS],
            "test_cells": "all 16 cells of the E1 grid",
            "hybrid_threshold": {
                "rule": "MLP if rules abstain or MLP max probability >= tau, else rules",
                "tau_grid": list(TAU_GRID),
                "chosen_on": "validation rows of the training cell, first best",
            },
            "nothing_tuned_on_test": True,
            **provenance(),
        },
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--e1", type=Path, default=Path("runs/e1"))
    parser.add_argument("--out", type=Path, default=Path("runs/e2"))
    parser.add_argument("--n-per-label", type=int, default=P.N_PER_LABEL)
    seed_main(
        "para_triage.experiments.e2",
        parser,
        argv,
        run_one=lambda seed, a: run_seed(seed, a.out, a.e1, a.n_per_label, a.force),
        write_config=lambda a: write_config(a.out, a.seeds, a.n_per_label),
        aggregate=lambda a: aggregate(a.out, a.seeds),
        extra_args=lambda a: ["--e1", str(a.e1), "--n-per-label", str(a.n_per_label)],
    )


if __name__ == "__main__":
    main()
