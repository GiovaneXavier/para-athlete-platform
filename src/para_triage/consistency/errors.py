"""Planted errors and the seven pairs of every image (design note section 5).

Each image gets, next to its CONSISTENT report, six more pairs, each with one thing changed:

    consistent        the report says what the label says
    a_side_swap       left and right swapped
    b_level           one known limb level moved one step, inside its domain
    c_region          what was a limb's level in one region is said of the other region
    d_omission        the report omits a side, or a level
    e_other_person    the report of another image of the set
    f_noise           abbreviations, typos, irrelevant sentences, a longer paragraph: NO error of fact

The expected verdict is never written by hand: it is the comparator applied to the true label of
the image and the label of the report. A planted error that changed nothing in the labels
(e.g. swapping two equal sides) is kept, marked `indistinguishable`, and counted apart; one that
cannot be built for an image (e.g. a level change in an image whose limbs are all `?`) is marked
`not_applicable`. Neither is hidden.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

from .compare import compare
from .reports import ReportContent, render_report
from .schema import ATTRIBUTES, LIMB_FIELDS, LOWER_FIELDS, LOWER_LEVELS, UNKNOWN, UPPER_FIELDS, UPPER_LEVELS, Attrs

CONSISTENT = "consistent"
SIDE_SWAP = "a_side_swap"
WRONG_LEVEL = "b_level"
WRONG_REGION = "c_region"
OMISSION = "d_omission"
OTHER_PERSON = "e_other_person"
NOISE = "f_noise"
ERROR_KINDS = (SIDE_SWAP, WRONG_LEVEL, WRONG_REGION, OMISSION, OTHER_PERSON)
KINDS = (CONSISTENT, NOISE) + ERROR_KINDS  # the seven pairs of one image

OK = "ok"
INDISTINGUISHABLE = "indistinguishable"
NOT_APPLICABLE = "not_applicable"

LEVELS_OF = {"lower_left": LOWER_LEVELS, "lower_right": LOWER_LEVELS, "upper_left": UPPER_LEVELS, "upper_right": UPPER_LEVELS}
REGION_OF = {"lower_left": "lower", "lower_right": "lower", "upper_left": "upper", "upper_right": "upper"}


@dataclass(frozen=True)
class Pair:
    image_id: str
    kind: str
    content: Optional[ReportContent]  # None when the error cannot be built for this image
    text: Optional[str]
    expected: Optional[str]  # the comparator on the two true labels
    status: str  # ok, indistinguishable, not_applicable
    note: str = ""  # redirected, level_omitted, side_omitted

    @property
    def usable(self) -> bool:
        """Counts in the rates: built, and the planted change changed a fact."""
        return self.status == OK


def _swap(attrs: Attrs, rng: random.Random):
    swapped = attrs.swapped_sides()
    return ReportContent(swapped), (INDISTINGUISHABLE if swapped == attrs else OK), ""


def _level(attrs: Attrs, rng: random.Random):
    known = [n for n in LIMB_FIELDS if getattr(attrs, n) != UNKNOWN]
    if not known:
        return None, NOT_APPLICABLE, ""
    name = rng.choice(known)
    value, step = getattr(attrs, name), rng.choice((-1, 1))
    new, note = value + step, ""
    if new not in LEVELS_OF[name]:  # off the end of the domain: the rule sends it to the neighbour on the other side
        new, note = value - step, "redirected"
    return ReportContent(attrs.with_(**{name: new})), OK, note


def _region(attrs: Attrs, rng: random.Random):
    candidates = [n for n in LIMB_FIELDS if getattr(attrs, n) not in (UNKNOWN, 0)]
    if not candidates:
        return None, NOT_APPLICABLE, ""
    name = rng.choice(candidates)
    side = "left" if name.endswith("left") else "right"
    other = f"{'upper' if REGION_OF[name] == 'lower' else 'lower'}_{side}"
    moved = min(getattr(attrs, name), max(LEVELS_OF[other]))
    return ReportContent(attrs.with_(**{name: 0, other: moved})), OK, "moved_to_" + other


def _omission(attrs: Attrs, rng: random.Random):
    known = list(attrs.known())
    if not known:
        return None, NOT_APPLICABLE, ""
    regions = [r for r, names in (("lower", LOWER_FIELDS), ("upper", UPPER_FIELDS)) if any(getattr(attrs, n) != UNKNOWN for n in names)]
    if regions and rng.random() < 0.5:  # the side is omitted: the level is said, "in one of the limbs"
        region = rng.choice(regions)
        names = LOWER_FIELDS if region == "lower" else UPPER_FIELDS
        level = max(getattr(attrs, n) for n in names if getattr(attrs, n) != UNKNOWN)
        return ReportContent(attrs.with_(**{n: UNKNOWN for n in names}), {region: level}), OK, "side_omitted"
    return ReportContent(attrs.with_(**{rng.choice(known): UNKNOWN})), OK, "level_omitted"


def plant(kind: str, attrs: Attrs, rng: random.Random, others: Sequence[Tuple[str, Attrs]] = ()):
    """(report content or None, status, note) for one kind of pair of an image with this label."""
    if kind in (CONSISTENT, NOISE):
        return ReportContent(attrs), OK, ""
    if kind == SIDE_SWAP:
        return _swap(attrs, rng)
    if kind == WRONG_LEVEL:
        return _level(attrs, rng)
    if kind == WRONG_REGION:
        return _region(attrs, rng)
    if kind == OMISSION:
        return _omission(attrs, rng)
    if kind == OTHER_PERSON:
        if not others:
            return None, NOT_APPLICABLE, ""
        _, theirs = others[rng.randrange(len(others))]
        return ReportContent(theirs), (INDISTINGUISHABLE if theirs == attrs else OK), ""
    raise ValueError(f"unknown kind {kind!r}")


def build_pairs(images: Sequence[Tuple[str, Attrs]], seed: int = 34) -> list[Pair]:
    """The seven pairs of every image of the set, in a fixed order. `images` is (image id, true label)."""
    pairs: list[Pair] = []
    for image_id, attrs in images:
        others = [(i, a) for i, a in images if i != image_id]
        for kind in KINDS:
            rng = random.Random(f"k34-errors:{seed}:{image_id}:{kind}")
            content, status, note = plant(kind, attrs, rng, others)
            if content is None:
                pairs.append(Pair(image_id, kind, None, None, None, status, note))
                continue
            text = render_report(content, f"{seed}:{image_id}:{kind}", noisy=kind == NOISE)
            pairs.append(Pair(image_id, kind, content, text, compare(attrs, content.attrs, ATTRIBUTES).verdict, status, note))
    return pairs
