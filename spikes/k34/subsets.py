"""Deterministic subsets of the levels, chosen BEFORE any result is seen. Nothing is written to disk.

A first round used `combos[::3]`, and that was wrong: the 144 combinations are ordered with the last factor (upper_right,
3 values) changing fastest, so a stride that is a multiple of 3 fixes it (upper_right was always 0 in the subset). Now the
combinations are drawn with a seeded random sample, and `python subsets.py` prints each factor's counts.

Two disjoint draws of level-1 combinations: "dev" (used ONLY to look at prompt behaviour) and "eval" (the numbers in the
report). Level 2 uses a stride over its 75 seeded-random label combinations (no aliasing there), with an offset for "dev".
"""
from __future__ import annotations

import random
from collections import Counter

from para_triage.consistency import dataset, level2
from para_triage.consistency.schema import LIMB_FIELDS, level1_combinations

EVAL_COMBOS = 32   # x 3 poses = 96 images
DEV_COMBOS = 8     # x 3 poses = 24 images


def _draw() -> tuple[list[int], list[int]]:
    rng = random.Random("k34-pr3-subsets")
    order = list(range(144))
    rng.shuffle(order)
    return sorted(order[:EVAL_COMBOS]), sorted(order[EVAL_COMBOS:EVAL_COMBOS + DEV_COMBOS])


def level1(subset: str) -> list:
    """`eval` (32 combinations, 96 images) or `dev` (8 other combinations, 24 images). Disjoint."""
    eval_idx, dev_idx = _draw()
    combos = level1_combinations()
    chosen = eval_idx if subset == "eval" else dev_idx
    return list(dataset.level1_records(combos=[combos[i] for i in chosen]))


def level2_subset(subset: str) -> list:
    """In each of the 4 bands: `eval` = every 3rd of the 75 label combinations (25 per band, 100 images), `dev` = every 25th from offset 1 (3 per band)."""
    start, step = (0, 3) if subset == "eval" else (1, 25)
    combos = level2.label_combinations()
    out = []
    for band in range(level2.BANDS):
        for i in range(start, len(combos), step):
            png, label, vector, detail = level2.render_level2(combos[i], band, i, level2.DEFAULT_SEED, level2.TABLE)
            out.append(level2.Level2Record(f"K34-L2-{band * level2.PER_BAND + i + 1:04d}", 2, label, png, band, vector, detail))
    return out


def full(level: int) -> list:
    """All 432 images of level 1 or all 300 of level 2 (used by CLIP, which is cheap)."""
    return list(dataset.level1_records()) if level == 1 else list(level2.level2_records())


def records(level: int, subset: str) -> list:
    return level1(subset) if level == 1 else level2_subset(subset)


def balance(recs: list) -> dict:
    """Counts of each limb level in a subset: a check that no factor is fixed."""
    return {f: dict(Counter(getattr(r.attrs, f) for r in recs)) for f in LIMB_FIELDS}


if __name__ == "__main__":
    for lv in (1, 2):
        for name in ("eval", "dev"):
            r = records(lv, name)
            print(lv, name, len(r), balance(r))
