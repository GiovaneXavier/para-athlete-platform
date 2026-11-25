"""The split of the K35 data, fixed BEFORE any result is seen. Pure Python.

- 12 of the 144 level combinations are HELD OUT: never in the training set or the development set; they appear only in the test
  set (500 images per level), where they are measured apart from the 1,500 images of the 132 combinations the network has seen.
- The three sets use disjoint random seeds (train 1000, dev 2000, test 3000; K34 used 34), so no image, appearance or
  noise draw is shared. `tests/test_k35_splits.py` checks that no seed, no held-out combination and no image byte is shared.
- What the network sees in training holds every value of every limb (a held-out combination is a new COMBINATION of known
  values), so the held-out measurement tests whether the heads confuse the limbs with each other (shortcuts by correlation), not
  whether the network generalises to a level it never saw. The report says so.
"""
from __future__ import annotations

import random

from para_triage.consistency.schema import LIMB_FIELDS, level1_combinations

SEEDS = {"train": 1000, "dev": 2000, "test": 3000}
SIZES = {"train": 6000, "dev": 1000, "test_seen": 1500, "test_held": 500}  # per level
N_HELD = 12
BANDS = 4


def combos():
    return level1_combinations()


def held_out_indices() -> tuple[int, ...]:
    """12 combination indices, drawn with a seed, such that every value of every limb stays in the seen combinations."""
    all_combos = combos()
    for attempt in range(1000):
        rng = random.Random(f"k35-heldout:{attempt}")
        held = tuple(sorted(rng.sample(range(len(all_combos)), N_HELD)))
        seen = [c for i, c in enumerate(all_combos) if i not in held]
        if all({getattr(c, f) for c in seen} == {getattr(c, f) for c in all_combos} for f in LIMB_FIELDS):
            return held
    raise RuntimeError("no draw keeps every limb value in the seen combinations")


def seen_indices() -> tuple[int, ...]:
    held = set(held_out_indices())
    return tuple(i for i in range(len(combos())) if i not in held)


def items(level: int, split: str) -> list[tuple[int, int, int, bool]]:
    """What to render for `split` in {train, dev, test}: a list of (combo_index, band, index, held).

    With the seed, `index` fixes every random draw of the image. At level 1 `band` is -1 and `index` is the VARIATION number of the
    combination (0, 1, 2, ...), whose pose cycles standing, arms up, seated, so every combination meets every pose (pairing the
    combination with the image number would have tied each combination to one pose). At level 2 `index` is unique in the set, the
    band cycles 0, 1, 2, 3 and the combination changes every fourth image, so each combination meets every band.
    """
    parts = [("train", SIZES["train"], False)] if split == "train" else [("dev", SIZES["dev"], False)] if split == "dev" else [("test", SIZES["test_seen"], False), ("test", SIZES["test_held"], True)]
    out = []
    index = 0
    for _, n, held in parts:
        pool = held_out_indices() if held else seen_indices()
        for i in range(n):
            if level == 1:
                out.append((pool[i % len(pool)], -1, i // len(pool), held))
            else:
                out.append((pool[(i // BANDS) % len(pool)], i % BANDS, index, held))
            index += 1
    return out
