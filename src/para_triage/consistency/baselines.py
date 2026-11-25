"""Baselines of K34 that need no learned model (design note section 7): (a) the classical reader
of the mannequin PNG and (c) the chance baseline. The CLIP baseline (b) belongs to PR 3.

The classical reader uses the KNOWLEDGE OF THE GEOMETRY, as the note says: it knows where the
generator puts each segment of each pose (it imports the constants of `mannequin`), and nothing
else. It never sees a label, a seed or the appearance vector. From the pixels alone it

1. takes as foreground whatever differs from the background of its row (the rows' edge columns);
2. finds the pose and the small scale, rotation and shift that best align the part of the figure
   that is drawn at EVERY level (head, torso, thighs up to 65%, upper arms) with that foreground,
   using sample points inside it and sample points just outside every drawable shape;
3. looks, side by side, at one probe point per segment that a level can remove, along the chain
   shank, foot / forearm, hand. The first missing segment gives the level.

Left and right are the person's: in the front view the probe of the person's left is on the
right of the image. If the alignment is poor it answers `?` for everything.

It is NOT evidence about photographs. On the clean mannequin it is expected to be close to
perfect, and if it is, the report says so (a deep model does not gain on the mannequin).
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable

import numpy as np

from . import mannequin as mq
from .png import decode_png
from .schema import ATTRIBUTES, UNKNOWN, Attrs

BACKGROUND_COLUMNS = 6
FOREGROUND_DISTANCE = 40.0
MIN_ALIGNMENT = 0.35
PROBE_THRESHOLD = 0.5
FULL, CORE = Attrs(0, 0, 0, 0), Attrs(3, 3, 2, 2)  # the biggest and the smallest figure (the core is drawn at every level)

COARSE = dict(scale=np.arange(0.90, 1.1001, 0.05), rotation=np.arange(-4.0, 4.01, 2.0), shift=np.arange(-12.0, 12.01, 4.0))
FINE_STEPS = dict(scale=np.linspace(-0.025, 0.025, 5), rotation=np.linspace(-1.0, 1.0, 5), shift=np.linspace(-2.0, 2.0, 5))
SAMPLE_STRIDE = 7  # one sample point every this many pixels, in both directions
POSITIVE_MARGIN = 2  # sample points are this far inside the core
NEGATIVE_MARGIN = 2  # and this far outside every drawable shape
PLATEAU = 0.01  # the alignment is the mean of the candidates within this of the best score


def foreground(pixels: np.ndarray) -> np.ndarray:
    """True where a pixel differs from the background of its own row."""
    px = pixels.astype(np.float32)
    edge = np.concatenate([px[:, :BACKGROUND_COLUMNS], px[:, -BACKGROUND_COLUMNS:]], axis=1)
    background = np.median(edge, axis=1)[:, None, :]
    return np.sqrt(((px - background) ** 2).sum(axis=-1)) > FOREGROUND_DISTANCE


def _box_count(mask: np.ndarray, radius: int) -> np.ndarray:
    """For every pixel, how many True pixels lie in the square of the given radius around it."""
    padded = np.pad(mask.astype(np.int32), radius + 1)
    integral = padded.cumsum(0).cumsum(1)
    k = 2 * radius + 1
    h, w = mask.shape
    return integral[k : k + h, k : k + w] - integral[:h, k : k + w] - integral[k : k + h, :w] + integral[:h, :w]


def smooth(mask: np.ndarray, radius: int = 2) -> np.ndarray:
    return _box_count(mask, radius) / float((2 * radius + 1) ** 2)


def _dilate(mask: np.ndarray, radius: int) -> np.ndarray:
    return _box_count(mask, radius) > 0


def _erode(mask: np.ndarray, radius: int) -> np.ndarray:
    return _box_count(mask, radius) == (2 * radius + 1) ** 2


@dataclass(frozen=True)
class Template:
    pose: str
    positives: np.ndarray  # (N, 2) points inside the figure drawn at every level
    negatives: np.ndarray  # (M, 2) points outside every drawable shape, close to the core


@lru_cache(maxsize=None)
def template(pose: str, view: str) -> Template:
    core = mq.coverage(mq.nominal_shapes(CORE, pose, view))
    full = mq.coverage(mq.nominal_shapes(FULL, pose, view))
    grid = np.zeros_like(core)
    grid[::SAMPLE_STRIDE, ::SAMPLE_STRIDE] = True
    positive = _erode(core, POSITIVE_MARGIN) & grid
    negative = ~_dilate(full, NEGATIVE_MARGIN) & _dilate(core, 25) & grid
    to_xy = lambda m: np.argwhere(m)[:, ::-1].astype(float) + 0.5  # noqa: E731  (row, col) -> (x, y)
    return Template(pose, to_xy(positive), to_xy(negative))


def _sample(field: np.ndarray, points: np.ndarray) -> np.ndarray:
    """`field` at (K, N, 2) points, nearest pixel, outside the picture counts as 0."""
    h, w = field.shape
    x, y = np.rint(points[..., 0] - 0.5).astype(int), np.rint(points[..., 1] - 0.5).astype(int)
    inside = (x >= 0) & (x < w) & (y >= 0) & (y < h)
    return np.where(inside, field[np.clip(y, 0, h - 1), np.clip(x, 0, w - 1)], 0.0)


def _search(field: np.ndarray, t: Template, scale, rotation, dx, dy) -> tuple[float, tuple[float, float, float, float]]:
    s, r, x, y = (a.ravel() for a in np.meshgrid(scale, rotation, dx, dy, indexing="ij"))
    positive = _sample(field, mq.transform_points(t.positives, s, r, x, y)).mean(axis=1)
    negative = _sample(field, mq.transform_points(t.negatives, s, r, x, y)).mean(axis=1)
    score = positive - negative
    best = float(score.max())
    near = score >= best - PLATEAU  # a plateau of equally good candidates: take its middle, not its first cell
    return best, (float(s[near].mean()), float(r[near].mean()), float(x[near].mean()), float(y[near].mean()))


def coarse_align(field: np.ndarray, pose: str, view: str):
    return _search(field, template(pose, view), COARSE["scale"], COARSE["rotation"], COARSE["shift"], COARSE["shift"])


def fine_align(field: np.ndarray, pose: str, view: str, around: tuple[float, float, float, float]):
    s, r, x, y = around
    return _search(field, template(pose, view), s + FINE_STEPS["scale"], r + FINE_STEPS["rotation"], x + FINE_STEPS["shift"], y + FINE_STEPS["shift"])


def _probes(pose: str, view: str) -> dict[str, list[np.ndarray]]:
    """The nominal probe points of each removable segment (a segment is "seen" when the mean over its points is high):
    lower_<side>: shank top, shank end, foot tip; upper_<side>: forearm, hand."""
    out: dict[str, list[np.ndarray]] = {}
    for side, word in (("L", "left"), ("R", "right")):
        sign = mq.out_sign(side, view)
        elbow, wrist = mq.joint(pose, "elbow", side, view), mq.joint(pose, "wrist", side, view)
        knee, ankle = mq.joint(pose, "knee", side, view), mq.joint(pose, "ankle", side, view)
        length = max(float(np.hypot(wrist[0] - elbow[0], wrist[1] - elbow[1])), 1.0)
        hand = (wrist[0] + (wrist[0] - elbow[0]) / length * 8, wrist[1] + (wrist[1] - elbow[1]) / length * 8)
        foot_y = ankle[1] + mq.FOOT_DROP
        out[f"upper_{word}"] = [np.array([mq.lerp(elbow, wrist, 0.4)]), np.array([hand])]
        out[f"lower_{word}"] = [
            np.array([mq.lerp(knee, ankle, 0.2)]),
            np.array([mq.lerp(knee, ankle, 0.75)]),
            np.array([(ankle[0] + sign * 9, foot_y), (ankle[0] + sign * 13, foot_y)]),  # the half of the foot that only level 0 draws
        ]
    return out


def _level(present: list[bool], kind: str) -> int:
    """The first missing segment of the chain gives the level."""
    if kind == "upper":
        forearm, hand = present
        return 2 if not forearm else (1 if not hand else 0)
    shank_top, shank_end, foot_tip = present
    return 3 if not shank_top else (2 if not shank_end else (1 if not foot_tip else 0))


@dataclass(frozen=True)
class Reading:
    attrs: Attrs
    pose: str | None
    alignment: float


def classical_read(png: bytes, view: str = "front") -> Reading:
    pixels = decode_png(png)
    field = smooth(foreground(pixels))
    coarse = {pose: coarse_align(field, pose, view) for pose in mq.POSE_ORDER}
    pose = max(coarse, key=lambda p: coarse[p][0])
    score, (s, r, x, y) = fine_align(field, pose, view, coarse[pose][1])
    if score < MIN_ALIGNMENT:
        return Reading(Attrs(), None, score)
    values: dict[str, int] = {}
    for name, segments in _probes(pose, view).items():
        seen = [float(_sample(field, mq.transform_points(points, s, r, x, y)[None])[0].mean()) >= PROBE_THRESHOLD for points in segments]
        values[name] = _level(seen, "upper" if name.startswith("upper") else "lower")
    return Reading(Attrs(**values), pose, score)


def classical_extract(png: bytes, view: str = "front") -> Attrs:
    """The baseline as an image extractor: PNG bytes in, the four limb levels out (wheelchair and prosthesis stay `?`)."""
    return classical_read(png, view).attrs


# ---------------------------------------------------------------------------------------------
# Chance


def majority_attrs(labels: Iterable[Attrs]) -> Attrs:
    """The most common known value of each attribute (ties go to the smaller value). `?` when nothing is known."""
    counts: dict[str, Counter] = {a: Counter() for a in ATTRIBUTES}
    for label in labels:
        for name, value in label.known().items():
            counts[name][value] += 1
    chosen = {}
    for name, counter in counts.items():
        if counter:
            top = max(counter.values())
            chosen[name] = sorted((v for v, c in counter.items() if c == top), key=str)[0]
        else:
            chosen[name] = UNKNOWN
    return Attrs(**chosen)


class ConstantExtractor:
    """The chance baseline as an extractor of either kind: it ignores its input."""

    def __init__(self, answer: Attrs):
        self.answer = answer

    def __call__(self, _item) -> Attrs:
        return self.answer
