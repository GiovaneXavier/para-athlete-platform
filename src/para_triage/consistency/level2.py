"""Level 2 of image-and-report check: OUR synthetic images, with variation of appearance, pose, occlusion, lighting, geometry,
background, noise and equipment (design note section 4.2).

* 300 images in four difficulty bands of 75 (band 0 is the control, close to level 1; bands 1 to 3 are light,
  medium and strong). Every band uses the SAME 75 label combinations, so the bands differ in how the picture
  looks, not in what it says.
* Every image carries its difficulty vector: the intensity (0 to 3) of each of the eight factors.
* The labels are exact and come from the geometry: a limb whose end cannot be seen (covered, cut by the frame,
  hidden behind another limb or by a racing chair) is `?`, never a level. See `limb_visible`.
* Equipment is drawn by us: a daily and a racing wheelchair, and prostheses (socket, pylon and blade, or a hook).
* No image library: everything is `numpy`; the compression is an 8x8 block DCT quantisation that imitates JPEG.

The intensity table `TABLE` is the contract of the measurement: it is frozen with `TABLE_VERSION` before any
learned model runs, and only the classical baseline and chance may be used to change it.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Optional, Sequence

import numpy as np

from . import mannequin as mq
from .png import encode_png
from .schema import UNKNOWN, Attrs, level1_combinations

DEFAULT_SEED = 34
BANDS = 4
PER_BAND = 75
FACTORS = ("appearance", "pose", "occlusion", "lighting", "geometry", "background", "noise", "equipment")
PAD = 160  # visibility is measured on a canvas padded by this much, so what leaves the frame counts as hidden
HIDDEN_LIMIT = 0.30  # a limb whose end region is hidden by more than this is `?`
CHAIR_VISIBLE = 0.35
PROSTHESIS_VISIBLE = 0.5

TABLE_VERSION = "2026-11-05.v3"  # v2: noise drawn between 0 and its maximum, as level 1 does. v3: the figure colours are redrawn with the background, so a white shirt never lands on a light background
# The intensity of each factor -> its parameters. Index 0 reproduces level 1 (same ranges).
TABLE = {
    "appearance": {  # thickness of limbs, thickness of torso, minimum colour contrast with the background, decorations
        "limb": [(0.90, 1.15), (0.85, 1.25), (0.80, 1.35), (0.75, 1.45)],
        "torso": [(0.95, 1.10), (0.90, 1.20), (0.85, 1.30), (0.80, 1.40)],
        "contrast": [80.0, 60.0, 40.0, 20.0],
        "decorations": [0, 0, 2, 3],
    },
    "pose": {"pool": [("standing", "arms_up", "seated"), ("standing", "arms_up", "seated", "running"),
                      ("standing", "arms_up", "seated", "running", "jumping", "throwing"), mq.LEVEL2_POSES]},
    "occlusion": {"count": [0, 1, 2, 3], "size": [0.0, 0.7, 1.0, 1.3], "crop": [0.0, 0.0, 40.0, 80.0], "crop_probability": [0.0, 0.0, 0.5, 1.0]},
    "lighting": {"brightness": [0.0, 15.0, 30.0, 50.0], "contrast": [0.0, 0.10, 0.25, 0.45], "gradient": [0.0, 0.10, 0.25, 0.40],
                 "cast": [0.0, 0.0, 15.0, 35.0], "shadow": [0.0, 0.15, 0.30, 0.50]},
    "geometry": {"rotation": [3.0, 6.0, 10.0, 16.0], "scale": [(0.92, 1.08), (0.85, 1.10), (0.75, 1.15), (0.65, 1.20)],
                 "shift": [8.0, 14.0, 20.0, 26.0], "squeeze": [1.0, 0.95, 0.85, 0.72], "shear": [0.0, 0.03, 0.06, 0.10]},
    "background": {"pool": [("plain",), ("plain", "track"), ("track", "stands"), ("stands", "clutter")]},
    "noise": {"sigma": [8.0, 6.0, 14.0, 22.0], "blur": [0, 0, 1, 2], "down": [1, 1, 2, 3], "quality": [None, 85, 55, 30]},
    "equipment": {"chair": [0.0, 0.20, 0.35, 0.50], "prosthesis": [0.0, 0.25, 0.40, 0.55]},
}

SKIN = [(224, 172, 140), (198, 134, 98), (141, 85, 55), (96, 58, 38), (240, 200, 170), (170, 110, 80)]
SHIRT = [(40, 90, 180), (190, 40, 50), (30, 140, 90), (230, 190, 30), (120, 60, 160), (240, 120, 30), (20, 20, 20), (250, 250, 250)]
SHOE = [(60, 60, 60), (20, 20, 20), (250, 250, 250), (30, 30, 130)]
BACKGROUND = [(235, 235, 235), (205, 222, 240), (245, 238, 215), (55, 65, 80), (25, 25, 30), (198, 220, 198), (250, 205, 205)]
METAL = [(70, 75, 85), (190, 190, 205), (30, 30, 35)]
OCCLUDER_COLORS = [(110, 80, 50), (60, 60, 70), (200, 60, 60), (240, 240, 240), (40, 120, 160), (90, 140, 70)]
LIMB_PARTS = {"lower": ("thigh", "shank", "foot", "prosth_lower"), "upper": ("upper_arm", "forearm", "hand", "prosth_upper")}


@dataclass(frozen=True)
class Level2Record:
    image_id: str
    level: int
    attrs: Attrs  # the exact label, `?` included
    png: bytes
    band: int
    vector: dict  # factor -> intensity
    detail: dict = field(default_factory=dict)  # what was drawn; never a label

    @property
    def pose(self) -> str:
        return self.detail.get("pose", "")


# ---------------------------------------------------------------------------------------------
# Geometry helpers


def _rect(part, color, cx, cy, w, h) -> mq.Shape:
    return mq.Shape("bar", part, color, (cx - w / 2, cy), (cx + w / 2, cy), h)


def make_affine(scale: float, rotation_deg: float, shear: float, squeeze: float, dx: float, dy: float):
    theta = math.radians(rotation_deg)
    rot = np.array([[math.cos(theta), -math.sin(theta)], [math.sin(theta), math.cos(theta)]])
    m = rot @ np.array([[squeeze * scale, shear * scale], [0.0, scale]])
    center = np.array(mq.CANVAS_CENTER)
    size = scale * math.sqrt(squeeze)

    def apply(shapes: Sequence[mq.Shape]) -> list[mq.Shape]:
        out = []
        for s in shapes:
            p = center + m @ (np.array(s.p) - center) + (dx, dy)
            q = center + m @ (np.array(s.q) - center) + (dx, dy)
            out.append(mq.Shape(s.kind, s.part, s.color, (float(p[0]), float(p[1])), (float(q[0]), float(q[1])), s.size * size))
        return out

    return apply


def coverage_padded(shapes: Sequence[mq.Shape], pad: int = PAD) -> np.ndarray:
    """Boolean mask on a canvas padded by `pad` on every side (the frame is the middle)."""
    canvas = np.zeros((mq.HEIGHT + 2 * pad, mq.WIDTH + 2 * pad, 3), float)
    for s in shapes:
        mq._paint(canvas, mq.Shape(s.kind, s.part, (1, 1, 1), (s.p[0] + pad, s.p[1] + pad), (s.q[0] + pad, s.q[1] + pad), s.size))
    return canvas[..., 0] > 0


def outside_frame(pad: int = PAD) -> np.ndarray:
    mask = np.ones((mq.HEIGHT + 2 * pad, mq.WIDTH + 2 * pad), bool)
    mask[pad : pad + mq.HEIGHT, pad : pad + mq.WIDTH] = False
    return mask


# ---------------------------------------------------------------------------------------------
# The figure with its equipment, in nominal coordinates (before the geometry of the picture)


def _lerp(a, b, t):
    return mq.lerp(a, b, t)


def prosthesis_shapes(region: str, side: str, level: int, pose: str, color, limb: float) -> list[mq.Shape]:
    """What a prosthesis looks like from the end of the stump to the end of the limb. Drawn by us."""
    part = f"{side}.prosth_{region}"
    sign = mq.out_sign(side)
    shapes: list[mq.Shape] = []
    if region == "lower":
        hip, knee, ankle = (mq.joint(pose, n, side) for n in ("hip", "knee", "ankle"))
        foot_y = ankle[1] + mq.FOOT_DROP
        if level == 3:
            end = _lerp(hip, knee, 0.65)
            shapes += [mq.Shape("bar", part, color, end, knee, limb * 1.3), mq.Shape("bar", part, color, knee, ankle, limb * 0.6)]
        elif level == 2:
            top, bottom = _lerp(knee, ankle, 0.35), _lerp(knee, ankle, 0.7)
            shapes += [mq.Shape("bar", part, color, top, bottom, limb * 1.3), mq.Shape("bar", part, color, bottom, ankle, limb * 0.6)]
        else:  # partial foot: the other half of the foot
            return [mq.Shape("bar", part, color, (ankle[0], foot_y), (ankle[0] + sign * mq.FOOT_HALF_LENGTH, foot_y), mq.FOOT_WIDTH)]
        blade_mid = (ankle[0] + sign * 6, ankle[1] + 20)
        shapes += [mq.Shape("bar", part, color, ankle, blade_mid, 10), mq.Shape("bar", part, color, blade_mid, (ankle[0] + sign * 30, ankle[1] + 36), 10)]
        return shapes
    shoulder, elbow, wrist = (mq.joint(pose, n, side) for n in ("shoulder", "elbow", "wrist"))
    start = elbow if level == 2 else _lerp(elbow, wrist, 0.8)
    length = math.dist(elbow, wrist) or 1.0
    hook = (wrist[0] + (wrist[0] - elbow[0]) / length * 8, wrist[1] + (wrist[1] - elbow[1]) / length * 8)
    return [mq.Shape("bar", part, color, start, wrist, limb * 0.9), mq.Shape("disc", part, color, hook, hook, 9)]


def chair_shapes(kind: str, layer: str) -> list[mq.Shape]:
    """A wheelchair in nominal coordinates for the seated pose. `behind` is drawn before the figure, `front` after."""
    cx = mq.CENTER_X
    wheel = lambda part, x, y, r: [mq.Shape("disc", part, (55, 55, 60), (x, y), (x, y), r), mq.Shape("disc", part, (205, 205, 210), (x, y), (x, y), r - 9),  # noqa: E731
                                   mq.Shape("disc", part, (55, 55, 60), (x, y), (x, y), 8)]
    if kind == "daily":
        if layer == "behind":
            return (wheel("chair", cx - 84, 262, 56) + wheel("chair", cx + 84, 262, 56)
                    + [_rect("chair", (90, 90, 100), cx, 190, 94, 80), _rect("chair", (90, 90, 100), cx, 222, 84, 14)])
        return []
    if layer == "behind":
        return wheel("chair", cx - 112, 304, 62) + wheel("chair", cx + 112, 304, 62) + wheel("chair", cx, 376, 22) + [_rect("chair", (200, 40, 40), cx, 300, 190, 14)]
    return [_rect("chair", (200, 40, 40), cx, 292, 150, 88)]  # the shell that hides the legs below the knees


def decorations(rng: random.Random, count: int, shirt) -> list[mq.Shape]:
    """Stripes, a chest number and a headband: appearance only, drawn right after the torso."""
    out = []
    contrast = tuple(255 - c for c in shirt)
    if count >= 1:
        for y in rng.sample(range(112, 200, 16), 2):
            out.append(_rect("deco", contrast, mq.CENTER_X, y, 66, 8))
    if count >= 2:
        out.append(_rect("deco", rng.choice(OCCLUDER_COLORS), mq.CENTER_X, 150, 20, 26))
    if count >= 3:
        out.append(_rect("deco", rng.choice(OCCLUDER_COLORS), mq.CENTER_X, mq.HEAD_CENTER_Y - 12, 50, 8))
    return out


# ---------------------------------------------------------------------------------------------
# What can be seen: the labels


def limb_region(region: str, side: str, level: int, pose: str) -> list[mq.Shape]:
    """The shapes that must be seen to tell the level: the end of the stump and everything beyond it, up to the
    end the limb would have if it were whole (nominal coordinates)."""
    limb = mq.LIMB_WIDTH
    if region == "lower":
        hip, knee, ankle = (mq.joint(pose, n, side) for n in ("hip", "knee", "ankle"))
        sign = mq.out_sign(side)
        foot_y = ankle[1] + mq.FOOT_DROP
        foot = mq.Shape("bar", "region", (1, 1, 1), (ankle[0] - sign * mq.FOOT_HALF_LENGTH, foot_y), (ankle[0] + sign * mq.FOOT_HALF_LENGTH, foot_y), mq.FOOT_WIDTH)
        window = {3: [(hip, knee, 0.5), (knee, ankle, 0.0)], 2: [(knee, ankle, 0.3)], 1: [(knee, ankle, 0.8)], 0: []}[level]
        bones = [mq.Shape("bar", "region", (1, 1, 1), _lerp(a, b, t), b, limb) for a, b, t in window]
        return bones + [foot]
    shoulder, elbow, wrist = (mq.joint(pose, n, side) for n in ("shoulder", "elbow", "wrist"))
    length = math.dist(elbow, wrist) or 1.0
    hand = (wrist[0] + (wrist[0] - elbow[0]) / length * 8, wrist[1] + (wrist[1] - elbow[1]) / length * 8)
    window = {2: [(shoulder, elbow, 0.5), (elbow, wrist, 0.0)], 1: [(elbow, wrist, 0.4)], 0: []}[level]
    bones = [mq.Shape("bar", "region", (1, 1, 1), _lerp(a, b, t), b, limb) for a, b, t in window]
    return bones + [mq.Shape("disc", "region", (1, 1, 1), hand, hand, mq.HAND_RADIUS)]


def limb_visible(region_mask: np.ndarray, hidden: np.ndarray) -> bool:
    area = region_mask.sum()
    return area == 0 or (region_mask & hidden).sum() / area <= HIDDEN_LIMIT


# ---------------------------------------------------------------------------------------------
# Pixels: background, light, blur, noise, compression


def _colors(rng: random.Random, floor: float):
    """Skin, shirt, shoe and a background whose every figure colour is at least `floor` away from both of its ends."""
    for _ in range(500):
        figure = (rng.choice(SKIN), rng.choice(SHIRT), rng.choice(SHOE))
        top = rng.choice(BACKGROUND)
        bottom = tuple(max(0, min(255, c + rng.randint(-25, 25))) for c in top) if rng.random() < 0.5 else top
        if all(math.dist(f, b) >= floor for f in figure for b in (top, bottom)):
            return figure, top, bottom
    return (SKIN[0], SHIRT[0], SHOE[0]), (235, 235, 235), (235, 235, 235)


def make_background(kind: str, top, bottom, figure_colors, rs: np.random.RandomState) -> np.ndarray:
    h, w = mq.HEIGHT, mq.WIDTH
    t = np.linspace(0.0, 1.0, h)[:, None, None]
    canvas = np.broadcast_to(np.array(top, float) * (1 - t) + np.array(bottom, float) * t, (h, w, 3)).copy()
    if kind == "track":
        for y in range(int(h * 0.55), h, 38):
            canvas[y : y + 14] *= 0.82
        canvas[int(h * 0.55) : int(h * 0.58)] = (240, 240, 240)
    elif kind == "stands":
        for _ in range(260):
            x, y = rs.randint(0, w - 12), rs.randint(0, int(h * 0.7))
            canvas[y : y + rs.randint(6, 16), x : x + rs.randint(6, 16)] = rs.randint(30, 235, 3)
    elif kind == "clutter":
        palette = list(figure_colors) + [tuple(rs.randint(20, 235, 3)) for _ in range(4)]
        for _ in range(60):
            cx, cy, r = rs.randint(0, w), rs.randint(0, h), rs.randint(8, 40)
            ys, xs = np.ogrid[:h, :w]
            canvas[(xs - cx) ** 2 + (ys - cy) ** 2 <= r * r] = palette[rs.randint(0, len(palette))]
        canvas += rs.normal(0, 18, canvas.shape)
    return canvas


def box_blur(pixels: np.ndarray, radius: int) -> np.ndarray:
    if radius <= 0:
        return pixels
    k = 2 * radius + 1
    out = pixels
    for axis in (0, 1):
        padded = np.pad(out, [(radius, radius) if a == axis else (0, 0) for a in range(3)], mode="edge")
        cumulative = np.cumsum(padded, axis=axis, dtype=float)
        zero = np.zeros_like(np.take(cumulative, [0], axis=axis))
        cumulative = np.concatenate([zero, cumulative], axis=axis)
        n = out.shape[axis]
        out = (np.take(cumulative, range(k, k + n), axis=axis) - np.take(cumulative, range(0, n), axis=axis)) / k
    return out


def _dct_matrix() -> np.ndarray:
    c = np.array([[math.cos((2 * x + 1) * u * math.pi / 16) for x in range(8)] for u in range(8)])
    c[0] *= 1 / math.sqrt(2)
    return c * 0.5


Q50 = np.array([[16, 11, 10, 16, 24, 40, 51, 61], [12, 12, 14, 19, 26, 58, 60, 55], [14, 13, 16, 24, 40, 57, 69, 56], [14, 17, 22, 29, 51, 87, 80, 62],
                [18, 22, 37, 56, 68, 109, 103, 77], [24, 35, 55, 64, 81, 104, 113, 92], [49, 64, 78, 87, 103, 121, 120, 101], [72, 92, 95, 98, 112, 100, 103, 99]], float)


def jpeg_like(pixels: np.ndarray, quality: int) -> np.ndarray:
    """8x8 block DCT, quantisation with the standard luminance table scaled by `quality` (as JPEG does), inverse DCT."""
    scale = 5000 / quality if quality < 50 else 200 - 2 * quality
    q = np.clip(np.floor((Q50 * scale + 50) / 100), 1, 255)
    c = _dct_matrix()
    h, w, _ = pixels.shape
    blocks = (pixels - 128).reshape(h // 8, 8, w // 8, 8, 3).transpose(0, 2, 4, 1, 3)  # (by, bx, channel, 8, 8)
    freq = c @ blocks @ c.T
    freq = np.round(freq / q) * q
    back = c.T @ freq @ c
    return back.transpose(0, 3, 1, 4, 2).reshape(h, w, 3) + 128


def degrade(pixels: np.ndarray, p: dict, rs: np.random.RandomState) -> np.ndarray:
    out = box_blur(pixels, p["blur"])
    if p["down"] > 1:
        d = p["down"]
        small = out[::d, ::d]
        out = np.repeat(np.repeat(small, d, axis=0), d, axis=1)[: mq.HEIGHT, : mq.WIDTH]
    if p["sigma"] > 0:
        out = out + rs.normal(0, rs.uniform(0, p["sigma"]), out.shape)  # the intensity gives the MAXIMUM noise
    if p["quality"]:
        out = jpeg_like(np.clip(out, 0, 255), p["quality"])
    return out


def light(pixels: np.ndarray, p: dict, rng: random.Random) -> np.ndarray:
    contrast = 1 + rng.uniform(-p["contrast"], p["contrast"])
    out = (pixels - 128) * contrast + 128 + rng.uniform(-p["brightness"], p["brightness"])
    x = np.linspace(-1, 1, mq.WIDTH)[None, :, None]
    y = np.linspace(-1, 1, mq.HEIGHT)[:, None, None]
    angle = rng.uniform(0, 2 * math.pi)
    out = out * (1 + p["gradient"] * (math.cos(angle) * x + math.sin(angle) * y))
    return out + np.array([rng.uniform(-p["cast"], p["cast"]) for _ in range(3)])


# ---------------------------------------------------------------------------------------------
# One image


def _intensities(rng: random.Random, band: int) -> dict:
    if band == 0:
        return {f: 0 for f in FACTORS}
    return {f: (band if rng.random() < 0.6 else band - 1) for f in FACTORS}


def _occluders(rng: random.Random, count: int, scale: float, box) -> list[mq.Shape]:
    x0, y0, x1, y1 = box
    out: list[mq.Shape] = []
    for _ in range(count):
        kind = rng.choice(("bar", "scoreboard", "banner", "body"))
        color = rng.choice(OCCLUDER_COLORS)
        cx, cy = rng.uniform(x0, x1), rng.uniform(y0 + 40, y1 - 20)
        if kind == "bar":
            out.append(_rect("occluder", color, cx, cy, rng.uniform(110, 280) * scale, rng.uniform(14, 26) * scale))
        elif kind == "scoreboard":
            out.append(_rect("occluder", color, cx, cy, rng.uniform(90, 130) * scale, rng.uniform(45, 75) * scale))
        elif kind == "banner":
            out.append(_rect("occluder", color, cx, cy, rng.uniform(28, 44) * scale, rng.uniform(120, 200) * scale))
            out[-1] = mq.Shape("bar", "occluder", color, (cx, cy - 60 * scale), (cx, cy + 60 * scale), rng.uniform(28, 44) * scale)
        else:  # another body, cut by the figure's side
            out += [mq.Shape("disc", "occluder", color, (cx, cy - 70 * scale), (cx, cy - 70 * scale), 22 * scale),
                    mq.Shape("bar", "occluder", color, (cx, cy - 46 * scale), (cx, cy + 40 * scale), 52 * scale)]
    return out


def _bbox(shapes: Sequence[mq.Shape]):
    xs = [v for s in shapes for v in (s.p[0] - s.size, s.p[0] + s.size, s.q[0] - s.size, s.q[0] + s.size)]
    ys = [v for s in shapes for v in (s.p[1] - s.size, s.p[1] + s.size, s.q[1] - s.size, s.q[1] + s.size)]
    return min(xs), min(ys), max(xs), max(ys)


def render_level2(attrs4: Attrs, band: int, index: int, seed: int = DEFAULT_SEED, table: dict = TABLE):
    """(png bytes, label, vector, detail). `attrs4` is the true level of each limb as built; the label that comes
    back has `?` where the picture does not show the end of a limb, and the chair and prosthesis flags."""
    rng = random.Random(f"k34-level2:{seed}:{band}:{index}")
    rs = np.random.RandomState(rng.randrange(2**31))
    vector = _intensities(rng, band)
    t = {f: {k: (v[vector[f]] if isinstance(v, list) else v) for k, v in table[f].items()} for f in FACTORS}

    pose = rng.choice(t["pose"]["pool"])
    chair = None
    if rng.random() < t["equipment"]["chair"]:
        chair, pose = rng.choice(("daily", "racing")), "seated"
    (skin, shirt, shoe), top, bottom = _colors(rng, t["appearance"]["contrast"])
    limb_scale, torso_scale = rng.uniform(*t["appearance"]["limb"]), rng.uniform(*t["appearance"]["torso"])
    limb = mq.LIMB_WIDTH * limb_scale
    metal = rng.choice(METAL)

    # prostheses: on the impaired limbs, if the equipment factor says so
    impaired = [(r, s, getattr(attrs4, f"{r}_{w}")) for r in ("lower", "upper") for s, w in (("L", "left"), ("R", "right")) if getattr(attrs4, f"{r}_{w}") > 0]
    with_prosthesis = [x for x in impaired if rng.random() < 0.6] if impaired and rng.random() < t["equipment"]["prosthesis"] else []
    if impaired and with_prosthesis == [] and rng.random() < t["equipment"]["prosthesis"] * 0.5:
        with_prosthesis = [rng.choice(impaired)]

    body = mq.nominal_shapes(attrs4, pose, "front", skin, shirt, shoe, limb_scale, torso_scale)
    figure: list[mq.Shape] = []
    for s in body:
        figure.append(s)
        if s.part == "torso":
            figure += decorations(rng, t["appearance"]["decorations"], shirt)
    for region, side, level in with_prosthesis:
        last = max(i for i, s in enumerate(figure) if s.part.startswith(side + ".") and s.part.split(".")[1] in LIMB_PARTS[region][:3])
        figure[last + 1 : last + 1] = prosthesis_shapes(region, side, level, pose, metal, limb)

    behind = chair_shapes(chair, "behind") if chair else []
    front = chair_shapes(chair, "front") if chair else []

    # geometry of the picture (the figure, its chair and the labels' regions move together)
    crop_dx = crop_dy = 0.0
    if rng.random() < t["occlusion"]["crop_probability"]:
        direction = rng.choice(("left", "right", "bottom"))
        amount = t["occlusion"]["crop"]
        crop_dx, crop_dy = {"left": (-amount, 0.0), "right": (amount, 0.0), "bottom": (0.0, amount * 0.8)}[direction]
    g = t["geometry"]
    squeeze = rng.uniform(g["squeeze"], 1.0)
    affine = make_affine(rng.uniform(*g["scale"]), rng.uniform(-g["rotation"], g["rotation"]), rng.uniform(-g["shear"], g["shear"]), squeeze,
                         rng.uniform(-g["shift"], g["shift"]) + crop_dx, rng.uniform(-g["shift"], g["shift"]) + crop_dy)
    figure_t, behind_t, front_t = affine(figure), affine(behind), affine(front)

    box = _bbox(figure_t)
    occluders = _occluders(rng, t["occlusion"]["count"], max(t["occlusion"]["size"], 0.0), (box[0], box[1], box[2], box[3])) if t["occlusion"]["count"] else []

    # pixels
    canvas = make_background(rng.choice(t["background"]["pool"]), top, bottom, (skin, shirt), rs)
    if t["lighting"]["shadow"] > 0:
        ys, xs = np.ogrid[: mq.HEIGHT, : mq.WIDTH]
        cx, floor = (box[0] + box[2]) / 2, min(box[3], mq.HEIGHT - 4) + 4
        canvas[((xs - cx) / 70.0) ** 2 + ((ys - floor) / 11.0) ** 2 <= 1] *= 1 - t["lighting"]["shadow"]
    for s in behind_t + figure_t + front_t + occluders:
        mq._paint(canvas, s)
    canvas = light(canvas, t["lighting"], rng)
    pixels = np.clip(np.rint(degrade(np.clip(canvas, 0, 255), t["noise"], rs)), 0, 255).astype(np.uint8)

    # labels, from the geometry
    outside = outside_frame()
    hidden_front = coverage_padded(front_t + occluders) | outside
    values: dict = {}
    for region in ("lower", "upper"):
        for side, word in (("L", "left"), ("R", "right")):
            level = getattr(attrs4, f"{region}_{word}")
            own = [i for i, s in enumerate(figure_t) if s.part.startswith(side + ".") and s.part.split(".")[1] in LIMB_PARTS[region]]
            later = coverage_padded([s for i, s in enumerate(figure_t) if i > max(own) and s.part != "deco"]) if own else np.zeros_like(hidden_front)
            area = coverage_padded(affine(limb_region(region, side, level, pose)))
            values[f"{region}_{word}"] = level if limb_visible(area, hidden_front | later) else UNKNOWN
    if chair:
        chair_mask = coverage_padded(behind_t + front_t) & ~outside
        seen = chair_mask & ~coverage_padded(figure_t + occluders)
        values["wheelchair"] = "yes" if chair_mask.sum() and seen.sum() / chair_mask.sum() >= CHAIR_VISIBLE else UNKNOWN
        # a chair that is mostly hidden is `?`: something is there, but not enough to say
    else:
        values["wheelchair"] = "no"
    if with_prosthesis:
        prosthesis_mask = coverage_padded([s for s in figure_t if "prosth" in s.part]) & ~outside
        seen = prosthesis_mask & ~coverage_padded(front_t + occluders)
        values["prosthesis"] = "yes" if prosthesis_mask.sum() and seen.sum() / prosthesis_mask.sum() >= PROSTHESIS_VISIBLE else UNKNOWN
    else:
        values["prosthesis"] = "no"
    detail = {"pose": pose, "chair": chair, "prostheses": [f"{s}.{r}{lv}" for r, s, lv in with_prosthesis], "occluders": t["occlusion"]["count"],
              "background": None, "limb_thickness": round(limb_scale, 3), "squeeze": round(squeeze, 3), "true_levels": {k: getattr(attrs4, k) for k in ("lower_left", "lower_right", "upper_left", "upper_right")}}
    return encode_png(pixels), Attrs(**values), vector, detail


def label_combinations(seed: int = DEFAULT_SEED, n: int = PER_BAND) -> list[Attrs]:
    """The 75 combinations of limb levels used by every band (a seeded sample of the 144)."""
    combos = level1_combinations()
    random.Random(f"k34-level2-labels:{seed}").shuffle(combos)
    return combos[:n]


def level2_records(seed: int = DEFAULT_SEED, bands: Sequence[int] = range(BANDS), per_band: int = PER_BAND, table: dict = TABLE):
    """Yields the 300 images, band by band. Nothing is written to disk."""
    combos = label_combinations(seed, per_band)
    for band in bands:
        for i, attrs4 in enumerate(combos):
            png, label, vector, detail = render_level2(attrs4, band, i, seed, table)
            yield Level2Record(f"K34-L2-{band * per_band + i + 1:04d}", 2, label, png, band, vector, detail)
