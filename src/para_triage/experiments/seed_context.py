"""What the follow-up experiments (E2, E3, E-MNAR, V7) share with E1: the data and split of a seed."""
from __future__ import annotations

import dataclasses
import json
import os
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ..data.generator import TrueSamples
from ..models.mlp import TrainConfig, predict_logits, softmax
from ..models.predict import Predictor
from . import protocol as P
from .baselines import GbConfig, RuleImputer, fit_gb, gb_proba, imputed_rule_labels
from .e1 import GB_GRID, MLP_GRID


@dataclass
class SeedContext:
    seed: int
    e1_dir: Path
    true: TrueSamples
    views: dict[P.Cell, P.View]
    split: dict[str, np.ndarray]
    classes: np.ndarray
    y: np.ndarray  # class index of every row
    tuning: dict

    @property
    def mlp_config(self) -> TrainConfig:
        """The configuration chosen on the validation rows of (1, 1) in E1, with this seed."""
        return dataclasses.replace(MLP_GRID[self.tuning["mlp_chosen"]], seed=self.seed)

    @property
    def gb_config(self) -> GbConfig:
        return GB_GRID[self.tuning["gb_chosen"]]

    @property
    def ambiguous_index(self) -> int:
        return int(np.where(self.classes == -1)[0][0])


def load_seed(seed: int, e1_dir: Path, cells: list[P.Cell] | None = None, n_per_label: int = P.N_PER_LABEL) -> SeedContext:
    """Regenerates the true profiles and views of an E1 seed (same streams) and loads its split and tuning."""
    cells = cells if cells is not None else P.cell_grid()
    true, views = P.make_views(seed, list(dict.fromkeys([*cells, P.DEFAULT_CELL, P.CLEAN_CELL])), n_per_label)
    e1s = e1_dir / f"seed_{seed}"
    sp = np.load(e1s / "split.npz")
    split = {k: sp[k] for k in ("train", "val", "cal", "test")}
    classes = sp["classes"]
    tuning = json.loads((e1s / "tuning.json").read_text(encoding="utf-8"))
    return SeedContext(seed, e1_dir, true, views, split, classes, np.searchsorted(classes, true.labels), tuning)


@dataclass
class DefaultModels:
    """The models trained at (1, 1) in E1 (the MLP from its checkpoint, boosting and the imputer refit identically)."""

    predictor: Predictor
    gb: object
    imputer: RuleImputer
    classes: np.ndarray

    def mlp_proba(self, x: np.ndarray, m: np.ndarray) -> np.ndarray:
        p = self.predictor
        return softmax(predict_logits(p.model, p.scaler.transform(x, m), m), p.temperature)

    def gb_proba(self, x: np.ndarray, m: np.ndarray) -> np.ndarray:
        return gb_proba(self.gb, x, m, len(self.classes))

    def imputed_rules(self, profiles) -> np.ndarray:
        return imputed_rule_labels(self.imputer, profiles)


def default_models(ctx: SeedContext) -> DefaultModels:
    default, train = ctx.views[P.DEFAULT_CELL], ctx.split["train"]
    return DefaultModels(
        Predictor.load(ctx.e1_dir / f"seed_{ctx.seed}" / "mlp_default.pt"),
        fit_gb(default.x[train], default.m[train], ctx.y[train], ctx.gb_config, ctx.seed),
        RuleImputer().fit([default.profiles[i] for i in train]),
        ctx.classes,
    )


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def run_seeds_in_parallel(
    module: str, seeds: list[int], out: Path, jobs: int, threads: int, extra: list[str], force: bool = False
) -> None:
    """One process per seed (`python -m module --seeds s ...`), `jobs` at a time."""
    env = {**os.environ, "OMP_NUM_THREADS": str(threads), "MKL_NUM_THREADS": str(threads)}
    pending, running = list(seeds), []
    while pending or running:
        while pending and len(running) < jobs:
            cmd = [sys.executable, "-m", module, "--seeds", str(pending.pop(0)), "--out", str(out), "--threads", str(threads), *extra]
            if force:
                cmd.append("--force")
            running.append(subprocess.Popen(cmd, env=env))
        running = [p for p in running if p.poll() is None]
        time.sleep(2)


def seed_main(
    module: str,
    parser,
    argv: list[str] | None,
    run_one: Callable,
    write_config: Callable,
    aggregate: Callable,
    extra_args: Callable,
) -> None:
    """Common command line: `--seeds`, `--jobs`, `--threads`, `--out`, `--force`, `--aggregate-only`."""
    parser.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2, 3, 4])
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--threads", type=int, default=3)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--aggregate-only", action="store_true")
    args = parser.parse_args(argv)
    if args.aggregate_only:
        aggregate(args)
        return
    if args.jobs > 1 and len(args.seeds) > 1:
        args.out.mkdir(parents=True, exist_ok=True)
        write_config(args)  # the mechanism and the grid are written down before anything runs
        run_seeds_in_parallel(module, args.seeds, args.out, args.jobs, args.threads, extra_args(args), args.force)
        aggregate(args)
        return
    import torch

    torch.set_num_threads(int(os.environ.get("OMP_NUM_THREADS", args.threads)))
    if len(args.seeds) > 1:
        args.out.mkdir(parents=True, exist_ok=True)
        write_config(args)
    for seed in args.seeds:
        run_one(seed, args)
    if len(args.seeds) > 1:  # a single seed is a child of a parallel run: the parent aggregates once all are done
        aggregate(args)
