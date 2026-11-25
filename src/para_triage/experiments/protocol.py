"""Shared protocol of the paper experiments (E1, E7).

One set of true profiles per seed; every noisy view of a seed shares those profiles and the
row order, so a split by row index never puts the same profile in two parts. The noise of a
view comes from its own stream, derived from (seed, noise level, missing level).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

from ..data import NoiseConfig, encode_profiles
from ..data.generator import TrueSamples, observe_samples, sample_true_profiles
from ..rules import Profile

N_PER_LABEL = 300
NOISE_LEVELS = (0.0, 0.5, 1.0, 2.0)
MISSING_LEVELS = (0.0, 0.5, 1.0, 2.0)
DEFAULT_CELL = (1.0, 1.0)
CLEAN_CELL = (0.0, 0.0)
# Fractions of the rows: train, validation (early stopping, temperature, tuning), calibration (E7), test.
SPLIT = (0.60, 0.10, 0.15, 0.15)

Cell = tuple[float, float]  # (noise multiplier, missing multiplier)


def cell_grid(noise_levels=NOISE_LEVELS, missing_levels=MISSING_LEVELS) -> list[Cell]:
    return [(n, m) for n in noise_levels for m in missing_levels]


def view_rng(seed: int, cell: Cell) -> np.random.Generator:
    """Noise stream of one view: independent of the sampler and of every other cell."""
    noise, missing = cell
    return np.random.default_rng(np.random.SeedSequence([seed, round(noise * 1000), round(missing * 1000)]))


@dataclass
class View:
    """One noisy observation of the true profiles."""

    cell: Cell
    profiles: list[Profile]
    df: pd.DataFrame  # records plus group, label, candidates, rule_label
    x: np.ndarray
    m: np.ndarray


def make_view(true: TrueSamples, seed: int, cell: Cell, base: NoiseConfig | None = None) -> View:
    cfg = (base or NoiseConfig()).scaled(*cell)
    profiles, df = observe_samples(true, cfg, view_rng(seed, cell))
    x, m = encode_profiles(profiles)
    return View(cell, profiles, df, x, m)


def make_views(seed: int, cells: list[Cell], n_per_label: int = N_PER_LABEL) -> tuple[TrueSamples, dict[Cell, View]]:
    true = sample_true_profiles(n_per_label, seed=seed)
    return true, {cell: make_view(true, seed, cell) for cell in cells}


def split4(groups, labels, seed: int) -> dict[str, np.ndarray]:
    """60/10/15/15 by row index, stratified by group and label."""
    strata = pd.Series(np.asarray(groups).astype(str)).str.cat(pd.Series(np.asarray(labels).astype(str)), sep="|")
    idx = np.arange(len(strata))
    p_train, p_val, p_cal, p_test = SPLIT
    train, rest = train_test_split(idx, test_size=1 - p_train, stratify=strata, random_state=seed)
    val, rest2 = train_test_split(
        rest, test_size=(p_cal + p_test) / (1 - p_train), stratify=strata.iloc[rest], random_state=seed
    )
    cal, test = train_test_split(rest2, test_size=p_test / (p_cal + p_test), stratify=strata.iloc[rest2], random_state=seed)
    return {"train": np.sort(train), "val": np.sort(val), "cal": np.sort(cal), "test": np.sort(test)}


def cell_name(cell: Cell) -> str:
    return f"n{cell[0]:g}_m{cell[1]:g}"


def mnar_rng(seed: int, stream: int, multiplier: float) -> np.random.Generator:
    """Noise and missingness stream of a view with a not-at-random mechanism (`stream` numbers the regime)."""
    return np.random.default_rng(np.random.SeedSequence([seed, 7, stream, round(multiplier * 1000)]))


def make_mnar_view(true: TrueSamples, seed: int, mechanism, stream: int, multiplier: float, base: NoiseConfig | None = None):
    """A view whose missing fields follow `mechanism`; noise at the default level. Returns (view, missing report)."""
    from ..data.missingness import MissingReport

    cfg = (base or NoiseConfig()).scaled(1.0, multiplier)
    report = MissingReport()
    profiles, df = observe_samples(true, cfg, mnar_rng(seed, stream, multiplier), mechanism, report)
    x, m = encode_profiles(profiles)
    return View((1.0, multiplier), profiles, df, x, m), report
