"""Level 1 of image-and-report check: a mannequin drawn by code from the four limb levels (design note section 4.1).

The figure is made of discs and flat-ended bars. A segment that the level says is absent is
NOT drawn: the stump ends where the level says. Nothing here comes from any photograph or from
the LEXI booklet: the geometry is ours, from zero.

Conventions
-----------
* Left and right are the PERSON's. In the front view the person's left is drawn on the RIGHT of
  the image; the back view flips that.
* Nominal coordinates are in pixels of a `WIDTH` x `HEIGHT` canvas; the figure is centred on
  `CENTER_X`. `Appearance` then scales, rotates and shifts the whole figure a little.
* The SVG is the clean drawing; the PNG is the same drawing rasterised with `numpy` (no image
  library) plus the light noise of the appearance.
* The mannequin cannot draw `?` (a hidden limb is a level-2 matter): it refuses it.

Limb levels, as drawn (lower: 0 none, 1 partial foot, 2 below knee, 3 through or above knee;
upper: 0 none, 1 wrist or below elbow, 2 elbow or above):

    lower 0  thigh, shank, whole foot       upper 0  upper arm, forearm, hand
    lower 1  thigh, shank, half foot        upper 1  upper arm, 80% of the forearm
    lower 2  thigh, 45% of the shank        upper 2  upper arm only
    lower 3  65% of the thigh
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable

import numpy as np

from .png import encode_png
from .schema import UNKNOWN, Attrs

WIDTH, HEIGHT = 280, 400
CENTER_X = 140.0
CANVAS_CENTER = (WIDTH / 2.0, HEIGHT / 2.0)

HEAD_RADIUS = 24.0
HAND_RADIUS = 10.0
LIMB_WIDTH = 16.0
TORSO_WIDTH = 66.0
FOOT_WIDTH = 18.0  # the feet do not change with the thickness of the limbs
FOOT_HALF_LENGTH = 18.0
TORSO_TOP, TORSO_BOTTOM = 100.0, 212.0
HEAD_CENTER_Y = 58.0

# How much of each bone is drawn, by level.
SHANK_FRACTION = {0: 1.0, 1: 1.0, 2: 0.45}  # level 3 has no shank
THIGH_FRACTION = {0: 1.0, 1: 1.0, 2: 1.0, 3: 0.65}
FOREARM_FRACTION = {0: 1.0, 1: 0.8}  # level 2 has no forearm

# Joints of one side, as (outward offset from the centre line, y).
POSES: dict[str, dict[str, tuple[float, float]]] = {
    "standing": dict(shoulder=(40, 106), elbow=(58, 160), wrist=(62, 208), hip=(20, 208), knee=(22, 278), ankle=(22, 340)),
    "arms_up": dict(shoulder=(40, 106), elbow=(68, 68), wrist=(92, 34), hip=(20, 208), knee=(22, 278), ankle=(22, 340)),
    "seated": dict(shoulder=(40, 106), elbow=(52, 158), wrist=(50, 196), hip=(20, 208), knee=(46, 240), ankle=(46, 322)),
}
POSE_ORDER = ("standing", "arms_up", "seated")  # the poses of level 1

# Poses of level 2. The base joints are the standing ones; a side may override some of them. Offsets are signed:
# a negative offset crosses the centre line (the arms crossed in front of the chest).
_STANDING = POSES["standing"]
POSES.update({
    "running": dict(_STANDING),
    "jumping": dict(shoulder=(40, 106), elbow=(70, 120), wrist=(90, 82), hip=(20, 208), knee=(42, 262), ankle=(30, 322)),
    "throwing": dict(_STANDING),
    "arms_crossed": dict(shoulder=(40, 106), elbow=(46, 172), wrist=(-18, 150), hip=(20, 208), knee=(22, 278), ankle=(22, 340)),
})
SIDE_POSES: dict[str, dict[str, dict[str, tuple[float, float]]]] = {
    "running": {
        "R": dict(elbow=(56, 150), wrist=(44, 112), knee=(40, 250), ankle=(28, 316)),
        "L": dict(elbow=(60, 150), wrist=(76, 196), knee=(14, 276), ankle=(6, 338)),
    },
    "throwing": {
        "R": dict(elbow=(68, 88), wrist=(62, 46)),
        "L": dict(elbow=(50, 150), wrist=(30, 176), knee=(34, 276), ankle=(46, 338)),
    },
    "arms_crossed": {"L": dict(elbow=(46, 178), wrist=(-20, 162))},
}
LEVEL2_POSES = ("standing", "arms_up", "seated", "running", "jumping", "throwing", "arms_crossed")
VIEWS = ("front", "back")
FOOT_DROP = 8.0  # the foot bar sits this far below the ankle

Color = tuple[int, int, int]


@dataclass(frozen=True)
class Shape:
    """A disc (`p` is the centre, `size` the radius) or a flat-ended bar from `p` to `q` (`size` is its width)."""

    kind: str
    part: str
    color: Color
    p: tuple[float, float]
    q: tuple[float, float]
    size: float


@dataclass(frozen=True)
class Appearance:
    """Everything that varies in the picture without changing what the label says."""

    pose: str = "standing"
    view: str = "front"
    skin: Color = (224, 172, 140)
    shirt: Color = (40, 90, 180)
    shoe: Color = (60, 60, 60)
    bg_top: Color = (235, 235, 235)
    bg_bottom: Color = (235, 235, 235)
    limb_scale: float = 1.0  # thickness of the limbs
    torso_scale: float = 1.0
    scale: float = 1.0
    rotation_deg: float = 0.0
    dx: float = 0.0
    dy: float = 0.0
    noise_sigma: float = 0.0
    noise_seed: int = 0

    def __post_init__(self) -> None:
        if self.pose not in POSES:
            raise ValueError(f"unknown pose {self.pose!r}")
        if self.view not in VIEWS:
            raise ValueError(f"unknown view {self.view!r}")

    def describe(self) -> dict:
        """The variation vector kept next to the image (it is never a label)."""
        return {
            "pose": self.pose, "view": self.view, "scale": round(self.scale, 3), "rotation_deg": round(self.rotation_deg, 2),
            "shift": [round(self.dx, 1), round(self.dy, 1)], "limb_thickness": round(self.limb_scale, 3),
            "torso_thickness": round(self.torso_scale, 3), "noise_sigma": round(self.noise_sigma, 2),
            "skin": list(self.skin), "shirt": list(self.shirt), "bg_top": list(self.bg_top), "bg_bottom": list(self.bg_bottom),
        }


@dataclass(frozen=True)
class Scene:
    shapes: tuple[Shape, ...]
    appearance: Appearance
    width: int = WIDTH
    height: int = HEIGHT

    def parts(self) -> list[str]:
        return [s.part for s in self.shapes]


def out_sign(side: str, view: str = "front") -> int:
    """+1 when the limb of the person's `side` ("L" or "R") is drawn on the right of the image."""
    sign = 1 if side == "L" else -1
    return sign if view == "front" else -sign


def lerp(a: tuple[float, float], b: tuple[float, float], t: float) -> tuple[float, float]:
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def joint(pose: str, name: str, side: str, view: str = "front") -> tuple[float, float]:
    """A nominal joint of the pose, in canvas coordinates, before the appearance transform."""
    offset, y = SIDE_POSES.get(pose, {}).get(side, {}).get(name) or POSES[pose][name]
    return (CENTER_X + out_sign(side, view) * offset, float(y))


def _bar(part, color, p, q, width) -> Shape:
    return Shape("bar", part, color, p, q, width)


def _disc(part, color, c, radius) -> Shape:
    return Shape("disc", part, color, c, c, radius)


def nominal_shapes(attrs: Attrs, pose: str = "standing", view: str = "front", skin: Color = (224, 172, 140),
                   shirt: Color = (40, 90, 180), shoe: Color = (60, 60, 60), limb_scale: float = 1.0,
                   torso_scale: float = 1.0) -> list[Shape]:
    """The shapes of the figure before the appearance transform. Absent segments are simply not here."""
    values = {name: getattr(attrs, name) for name in ("lower_left", "lower_right", "upper_left", "upper_right")}
    if any(v == UNKNOWN for v in values.values()):
        raise ValueError("the mannequin needs the four limb levels; `?` cannot be drawn")
    limb = LIMB_WIDTH * limb_scale
    shapes: list[Shape] = [
        _bar("neck", skin, (CENTER_X, HEAD_CENTER_Y + HEAD_RADIUS - 4), (CENTER_X, TORSO_TOP + 4), 14 * limb_scale),
        _bar("torso", shirt, (CENTER_X, TORSO_TOP), (CENTER_X, TORSO_BOTTOM), TORSO_WIDTH * torso_scale),
        _disc("head", skin, (CENTER_X, HEAD_CENTER_Y), HEAD_RADIUS),
    ]
    for side in ("L", "R"):
        sign = out_sign(side, view)
        lower, upper = values[f"lower_{'left' if side == 'L' else 'right'}"], values[f"upper_{'left' if side == 'L' else 'right'}"]
        # arm
        shoulder, elbow, wrist = (joint(pose, n, side, view) for n in ("shoulder", "elbow", "wrist"))
        shapes.append(_bar(f"{side}.upper_arm", skin, shoulder, elbow, limb))
        if upper <= 1:
            shapes.append(_bar(f"{side}.forearm", skin, elbow, lerp(elbow, wrist, FOREARM_FRACTION[upper]), limb))
        if upper == 0:
            length = math.dist(elbow, wrist) or 1.0
            hand = (wrist[0] + (wrist[0] - elbow[0]) / length * 8, wrist[1] + (wrist[1] - elbow[1]) / length * 8)
            shapes.append(_disc(f"{side}.hand", skin, hand, HAND_RADIUS * limb_scale))
        # leg
        hip, knee, ankle = (joint(pose, n, side, view) for n in ("hip", "knee", "ankle"))
        shapes.append(_bar(f"{side}.thigh", skin, hip, lerp(hip, knee, THIGH_FRACTION[lower]), limb))
        if lower <= 2:
            shapes.append(_bar(f"{side}.shank", skin, knee, lerp(knee, ankle, SHANK_FRACTION[lower]), limb))
        if lower <= 1:
            y = ankle[1] + FOOT_DROP
            inner = ankle[0] - sign * FOOT_HALF_LENGTH
            outer = ankle[0] + sign * FOOT_HALF_LENGTH if lower == 0 else ankle[0]
            shapes.append(_bar(f"{side}.foot", shoe, (inner, y), (outer, y), FOOT_WIDTH))
    return shapes


def transform_points(points: np.ndarray, scale, rotation_deg, dx, dy) -> np.ndarray:
    """The appearance transform (scale and rotate about the canvas centre, then shift).

    `points` is (N, 2); `scale`, `rotation_deg`, `dx` and `dy` are scalars or (K,) arrays, and the
    result is (K, N, 2) when they are arrays and (N, 2) when they are scalars."""
    scalar = np.ndim(scale) == 0
    s, r, tx, ty = (np.atleast_1d(np.asarray(v, float))[:, None] for v in (scale, rotation_deg, dx, dy))
    x = (points[None, :, 0] - CANVAS_CENTER[0]) * s
    y = (points[None, :, 1] - CANVAS_CENTER[1]) * s
    theta = np.radians(r)
    c, sn = np.cos(theta), np.sin(theta)
    moved = np.stack([CANVAS_CENTER[0] + c * x - sn * y + tx, CANVAS_CENTER[1] + sn * x + c * y + ty], axis=-1)
    return moved[0] if scalar else moved


def _transform(point: tuple[float, float], a: Appearance) -> tuple[float, float]:
    x, y = transform_points(np.array([point], float), a.scale, a.rotation_deg, a.dx, a.dy)[0]
    return (float(x), float(y))


def build_scene(attrs: Attrs, appearance: Appearance = Appearance()) -> Scene:
    a = appearance
    shapes = nominal_shapes(attrs, a.pose, a.view, a.skin, a.shirt, a.shoe, a.limb_scale, a.torso_scale)
    moved = tuple(Shape(s.kind, s.part, s.color, _transform(s.p, a), _transform(s.q, a), s.size * a.scale) for s in shapes)
    return Scene(moved, a)


# ---------------------------------------------------------------------------------------------
# SVG


def _hex(c: Color) -> str:
    return "#%02x%02x%02x" % tuple(c)


def to_svg(scene: Scene) -> str:
    """The clean vector drawing (no noise). Deterministic text. It carries no label: only the
    segments that are drawn, named by `data-part`."""
    a = scene.appearance
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{scene.width}" height="{scene.height}" viewBox="0 0 {scene.width} {scene.height}">',
        f'<defs><linearGradient id="bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{_hex(a.bg_top)}"/>'
        f'<stop offset="1" stop-color="{_hex(a.bg_bottom)}"/></linearGradient></defs>',
        f'<rect width="{scene.width}" height="{scene.height}" fill="url(#bg)"/>',
    ]
    for s in scene.shapes:
        if s.kind == "disc":
            out.append(f'<circle data-part="{s.part}" cx="{s.p[0]:.2f}" cy="{s.p[1]:.2f}" r="{s.size:.2f}" fill="{_hex(s.color)}"/>')
        else:
            out.append(
                f'<line data-part="{s.part}" x1="{s.p[0]:.2f}" y1="{s.p[1]:.2f}" x2="{s.q[0]:.2f}" y2="{s.q[1]:.2f}" '
                f'stroke="{_hex(s.color)}" stroke-width="{s.size:.2f}" stroke-linecap="butt"/>'
            )
    out.append("</svg>")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------------------------------
# Rasterisation with numpy


def _background(a: Appearance, width: int, height: int) -> np.ndarray:
    t = np.linspace(0.0, 1.0, height)[:, None, None]
    top, bottom = np.array(a.bg_top, float), np.array(a.bg_bottom, float)
    column = top * (1 - t) + bottom * t  # (height, 1, 3)
    return np.broadcast_to(column, (height, width, 3)).copy()


def _paint(canvas: np.ndarray, shape: Shape) -> None:
    height, width, _ = canvas.shape
    px, py = shape.p
    qx, qy = shape.q
    reach = shape.size + 2
    x0, x1 = max(int(min(px, qx) - reach), 0), min(int(max(px, qx) + reach) + 1, width)
    y0, y1 = max(int(min(py, qy) - reach), 0), min(int(max(py, qy) + reach) + 1, height)
    if x0 >= x1 or y0 >= y1:
        return
    ys, xs = np.mgrid[y0:y1, x0:x1]
    xs, ys = xs + 0.5, ys + 0.5
    if shape.kind == "disc":
        mask = (xs - px) ** 2 + (ys - py) ** 2 <= shape.size**2
    else:
        dx, dy = qx - px, qy - py
        length2 = dx * dx + dy * dy
        t = ((xs - px) * dx + (ys - py) * dy) / length2
        perpendicular = np.abs((xs - px) * dy - (ys - py) * dx) / math.sqrt(length2)
        mask = (t >= 0) & (t <= 1) & (perpendicular <= shape.size / 2)
    canvas[y0:y1, x0:x1][mask] = shape.color


def rasterize(scene: Scene, noise: bool = True) -> np.ndarray:
    """(height, width, 3) uint8. The light noise of the appearance is added last, with a seeded
    legacy `RandomState` (a stream numpy promises to keep)."""
    canvas = _background(scene.appearance, scene.width, scene.height)
    for shape in scene.shapes:
        _paint(canvas, shape)
    a = scene.appearance
    if noise and a.noise_sigma > 0:
        canvas = canvas + np.random.RandomState(a.noise_seed).normal(0.0, a.noise_sigma, canvas.shape)
    return np.clip(np.rint(canvas), 0, 255).astype(np.uint8)


@dataclass(frozen=True)
class Rendering:
    scene: Scene
    svg: str
    png: bytes = field(repr=False)


def render(attrs: Attrs, appearance: Appearance = Appearance()) -> Rendering:
    scene = build_scene(attrs, appearance)
    return Rendering(scene, to_svg(scene), encode_png(rasterize(scene)))


def render_pixels(attrs: Attrs, appearance: Appearance = Appearance(), noise: bool = True) -> np.ndarray:
    return rasterize(build_scene(attrs, appearance), noise=noise)


def drawn_parts(shapes: Iterable[Shape]) -> set[str]:
    return {s.part for s in shapes}


def coverage(shapes: Iterable[Shape], width: int = WIDTH, height: int = HEIGHT) -> np.ndarray:
    """Boolean mask of the pixels the shapes cover (no background, no noise)."""
    canvas = np.zeros((height, width, 3), float)
    for s in shapes:
        _paint(canvas, Shape(s.kind, s.part, (1, 1, 1), s.p, s.q, s.size))
    return canvas[..., 0] > 0
