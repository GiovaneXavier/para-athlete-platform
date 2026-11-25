"""The level 1 image set: 144 combinations x 3 appearance variations = 432 mannequin images
(design note sections 4.1 and 8).

Everything is derived from one seed, so the set is reproducible. The label of an image is the
combination of limb levels; the appearance (pose, colours, thickness, scale, rotation, shift,
background, noise) never changes it. Variation `v` of every combination uses pose `v`
(standing, arms up, seated), so each combination appears in each pose.

Images are produced lazily: nothing is written to disk and no list of 432 PNGs is kept.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Iterator

from .mannequin import POSE_ORDER, Appearance, render
from .schema import LEVEL1_ATTRIBUTES, Attrs, level1_combinations

DEFAULT_SEED = 34
VARIATIONS = 3

SKIN = [(224, 172, 140), (198, 134, 98), (141, 85, 55), (96, 58, 38), (240, 200, 170), (170, 110, 80)]
SHIRT = [(40, 90, 180), (190, 40, 50), (30, 140, 90), (230, 190, 30), (120, 60, 160), (240, 120, 30), (20, 20, 20), (250, 250, 250)]
SHOE = [(60, 60, 60), (20, 20, 20), (250, 250, 250), (30, 30, 130)]
BACKGROUND = [(235, 235, 235), (205, 222, 240), (245, 238, 215), (55, 65, 80), (25, 25, 30), (198, 220, 198), (250, 205, 205)]
MIN_CONTRAST = 80.0  # in RGB distance, between every figure colour and the background at both ends


def _distance(a, b) -> float:
    return math.dist(a, b)


def sample_appearance(rng: random.Random, pose: str) -> Appearance:
    """Draws one appearance. Colours are redrawn until every figure colour contrasts with the background."""
    for _ in range(200):
        skin, shirt, shoe = rng.choice(SKIN), rng.choice(SHIRT), rng.choice(SHOE)
        bg_top = rng.choice(BACKGROUND)
        bg_bottom = tuple(max(0, min(255, c + rng.randint(-25, 25))) for c in bg_top) if rng.random() < 0.5 else bg_top
        if all(_distance(f, b) >= MIN_CONTRAST for f in (skin, shirt, shoe) for b in (bg_top, bg_bottom)):
            break
    else:  # pragma: no cover - the palettes above always find a pair well before 200 tries
        skin, shirt, shoe, bg_top, bg_bottom = SKIN[0], SHIRT[0], SHOE[0], BACKGROUND[0], BACKGROUND[0]
    return Appearance(
        pose=pose, view="front", skin=skin, shirt=shirt, shoe=shoe, bg_top=bg_top, bg_bottom=bg_bottom,
        limb_scale=rng.uniform(0.9, 1.15), torso_scale=rng.uniform(0.95, 1.1), scale=rng.uniform(0.92, 1.08),
        rotation_deg=rng.uniform(-3, 3), dx=rng.uniform(-8, 8), dy=rng.uniform(-8, 8),
        noise_sigma=rng.uniform(0, 8), noise_seed=rng.randrange(2**31),
    )


@dataclass(frozen=True)
class ImageRecord:
    image_id: str
    level: int
    attrs: Attrs  # the exact label
    png: bytes
    svg: str
    appearance: dict  # the variation vector; never a label
    pose: str
    variation: int


def appearance_for(combo_index: int, variation: int, seed: int = DEFAULT_SEED) -> Appearance:
    # A string seed is hashed the same way on every platform and version.
    rng = random.Random(f"k34-level1:{seed}:{combo_index}:{variation}")
    return sample_appearance(rng, POSE_ORDER[variation % len(POSE_ORDER)])


def level1_records(seed: int = DEFAULT_SEED, variations: int = VARIATIONS, combos: list[Attrs] | None = None) -> Iterator[ImageRecord]:
    chosen = combos if combos is not None else level1_combinations()
    for i, attrs in enumerate(chosen):
        for v in range(variations):
            appearance = appearance_for(i, v, seed)
            rendering = render(attrs, appearance)
            yield ImageRecord(
                image_id=f"K34-L1-{i * variations + v + 1:04d}", level=1, attrs=attrs.restricted(LEVEL1_ATTRIBUTES),
                png=rendering.png, svg=rendering.svg, appearance=appearance.describe(), pose=appearance.pose, variation=v,
            )
