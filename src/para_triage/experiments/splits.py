"""Splits of the rows of a seed: by row (the default of E1 and E7) or by true profile.

A split by row can put the same true profile (differently corrupted) in training and in test. The generator draws
discrete profiles that repeat, so many test rows have a training twin (see V1). A split by true profile never
shares a profile between two parts. `profile_by_label` does it inside each (group, label): a test profile is new
but its label is not, unless the label has a single profile, which then stays in training.
"""
from __future__ import annotations

import numpy as np

from . import protocol as P

MODES = ("row", "profile_by_label")


def assign_by_profile(profiles, strata, rows: np.ndarray, seed: int, fractions: tuple[float, ...], names: tuple[str, ...]) -> dict[str, np.ndarray]:
    """Split `rows` (indices into `profiles`) so that no profile is in two parts.

    `fractions` are shares of the rows within each stratum. A profile goes to the part that contains the midpoint
    of its rows in a random order, so the shares are approximate when a profile has many rows.
    """
    rng = np.random.default_rng(seed + 424242)
    strata = np.asarray(strata)
    parts: dict[str, list[int]] = {k: [] for k in names}
    for s in sorted(set(strata[rows].tolist())):
        members = rows[strata[rows] == s]
        by_profile: dict = {}
        for i in members:
            by_profile.setdefault(profiles[i], []).append(int(i))
        keys = list(by_profile)
        edges = np.cumsum([f * len(members) for f in fractions])  # row counts at which each part ends
        seen = 0
        for j in rng.permutation(len(keys)):
            group = by_profile[keys[j]]
            midpoint = seen + len(group) / 2
            parts[names[min(int(np.searchsorted(edges, midpoint, side="right")), len(names) - 1)]].extend(group)
            seen += len(group)
    return {k: np.sort(np.array(v, dtype=int)) for k, v in parts.items()}


def profile_split(profiles, groups, seed: int, labels=None) -> dict[str, np.ndarray]:
    """60/10/15/15 by true profile: within each group, or within each (group, label) when `labels` is given."""
    groups = np.asarray(groups)
    strata = groups if labels is None else np.array([f"{g}|{l}" for g, l in zip(groups, labels)])
    return assign_by_profile(profiles, strata, np.arange(len(profiles)), seed, P.SPLIT, ("train", "val", "cal", "test"))


def split_for(mode: str, true, seed: int) -> dict[str, np.ndarray]:
    """The 60/10/15/15 split of a seed in the requested mode."""
    if mode == "row":
        return P.split4(true.groups, true.labels, seed)
    if mode == "profile_by_label":
        return profile_split(true.profiles, true.groups, seed, true.labels)
    raise ValueError(f"unknown split mode {mode!r}; use one of {MODES}")


def halves(mode: str, true, pool: np.ndarray, seed: int) -> tuple[np.ndarray, np.ndarray]:
    """Two halves of the calibration+test rows, as positions in `pool`: random by row, or by true profile."""
    if mode == "row":
        from sklearn.model_selection import train_test_split

        strata = np.array([f"{true.groups[i]}|{true.labels[i]}" for i in pool])
        return tuple(train_test_split(np.arange(len(pool)), test_size=0.5, stratify=strata, random_state=seed))
    pool_profiles = [true.profiles[i] for i in pool]
    strata = np.array([f"{true.groups[i]}|{true.labels[i]}" for i in pool])
    parts = assign_by_profile(pool_profiles, strata, np.arange(len(pool)), seed, (0.5, 0.5), ("a", "b"))
    return parts["a"], parts["b"]
