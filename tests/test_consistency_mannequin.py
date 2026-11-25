"""image-and-report check, PR 2: the mannequin generator, the PNG writer and the level 1 set (design note sections 4.1 and 12)."""
import dataclasses
import itertools
import math
import xml.etree.ElementTree as ET

import numpy as np
import pytest

from para_triage.consistency import dataset
from para_triage.consistency import mannequin as mq
from para_triage.consistency.png import SIGNATURE, decode_png, encode_png
from para_triage.consistency.schema import UNKNOWN, Attrs, level1_combinations

CLEAN = mq.Appearance()  # no scale, rotation, shift or noise


def expected_parts(attrs: Attrs) -> set:
    parts = {"head", "neck", "torso"}
    for side, word in (("L", "left"), ("R", "right")):
        lower, upper = getattr(attrs, f"lower_{word}"), getattr(attrs, f"upper_{word}")
        parts |= {f"{side}.upper_arm", f"{side}.thigh"}
        if upper <= 1:
            parts.add(f"{side}.forearm")
        if upper == 0:
            parts.add(f"{side}.hand")
        if lower <= 2:
            parts.add(f"{side}.shank")
        if lower <= 1:
            parts.add(f"{side}.foot")
    return parts


# ---- PNG ---------------------------------------------------------------------------------------


def test_the_png_writer_round_trips_and_is_deterministic():
    pixels = np.random.RandomState(0).randint(0, 256, (17, 23, 3)).astype(np.uint8)
    data = encode_png(pixels)
    assert data[:8] == SIGNATURE and encode_png(pixels) == data
    assert (decode_png(data) == pixels).all()


def test_the_png_reader_refuses_what_is_not_ours():
    with pytest.raises(ValueError):
        decode_png(b"not a png at all")
    good = bytearray(encode_png(np.zeros((4, 4, 3), np.uint8)))
    good[-20] ^= 0xFF  # corrupt a byte inside a chunk: the checksum must catch it
    with pytest.raises(ValueError):
        decode_png(bytes(good))
    with pytest.raises(ValueError):
        encode_png(np.zeros((4, 4), np.uint8))


# ---- the drawing -------------------------------------------------------------------------------


def test_the_same_seed_gives_the_same_svg_and_the_same_png():
    a = dataset.appearance_for(5, 1)
    first, second = mq.render(Attrs(1, 2, 0, 1), a), mq.render(Attrs(1, 2, 0, 1), a)
    assert first.svg == second.svg and first.png == second.png
    assert dataset.appearance_for(5, 1) == dataset.appearance_for(5, 1)
    other = dataclasses.replace(a, noise_seed=a.noise_seed + 1)
    assert mq.render(Attrs(1, 2, 0, 1), other).png != first.png and mq.render(Attrs(1, 2, 0, 1), other).svg == first.svg  # noise is only in the PNG


def test_every_one_of_the_144_combinations_draws_exactly_its_segments_and_not_the_absent_ones():
    seen = set()
    for attrs in level1_combinations():
        parts = mq.build_scene(attrs, CLEAN).parts()
        assert len(parts) == len(set(parts))
        assert set(parts) == expected_parts(attrs), attrs
        scene = mq.build_scene(attrs, CLEAN)
        seen.add(frozenset((s.part, round(s.p[0]), round(s.p[1]), round(s.q[0]), round(s.q[1])) for s in scene.shapes))
    assert len(seen) == 4 * 4 * 3 * 3  # every combination looks different (in which segments, and how long)


def test_a_missing_segment_leaves_only_background_where_it_would_have_been():
    full = mq.coverage(mq.nominal_shapes(Attrs(0, 0, 0, 0)))
    for attrs in (Attrs(3, 0, 0, 0), Attrs(0, 2, 0, 0), Attrs(0, 0, 2, 0), Attrs(0, 0, 0, 1), Attrs(1, 1, 1, 1)):
        drawn = mq.coverage(mq.nominal_shapes(attrs))
        assert not (drawn & ~full).any(), "a truncated figure never draws outside the full one"
        assert (full & ~drawn).any()
    # the pixels: a clean render has the plain background wherever the absent segment would be
    attrs = Attrs(3, 0, 2, 0)
    pixels = mq.render_pixels(attrs, CLEAN)
    missing = mq.coverage(mq.nominal_shapes(Attrs(0, 0, 0, 0))) & ~mq.coverage(mq.nominal_shapes(attrs))
    background = mq._background(CLEAN, mq.WIDTH, mq.HEIGHT)
    assert missing.sum() > 1000
    assert (pixels[missing] == np.rint(background[missing]).astype(np.uint8)).all()


@pytest.mark.parametrize("view,left_on_right", [("front", True), ("back", False)])
def test_the_left_of_the_person_is_on_the_right_of_the_front_image(view, left_on_right):
    for attrs in level1_combinations():
        scene = mq.build_scene(attrs, mq.Appearance(view=view))
        for shape in scene.shapes:
            if shape.part.startswith(("L.", "R.")):
                on_right = (shape.p[0] + shape.q[0]) / 2 > mq.CENTER_X
                assert on_right == ((shape.part[0] == "L") == left_on_right), (attrs, shape.part)
        if attrs.lower_left == 3 and attrs.lower_right == 0:
            break
    # in pixels: a left leg cut above the knee leaves the right half of the image without a shank
    pixels = mq.render_pixels(Attrs(3, 0, 0, 0), mq.Appearance(view=view))
    background = mq._background(CLEAN, mq.WIDTH, mq.HEIGHT)
    foot_rows = slice(300, 360)
    left_half, right_half = pixels[foot_rows, : mq.WIDTH // 2], pixels[foot_rows, mq.WIDTH // 2 :]
    differs = lambda half, x0: (half != np.rint(background[foot_rows, x0 : x0 + half.shape[1]]).astype(np.uint8)).any(axis=2).sum()  # noqa: E731
    on_the_image_right = differs(right_half, mq.WIDTH // 2)
    on_the_image_left = differs(left_half, 0)
    assert (on_the_image_right == 0) if left_on_right else (on_the_image_left == 0)
    assert (on_the_image_left > 500) if left_on_right else (on_the_image_right > 500)


def test_mirroring_the_picture_equals_swapping_the_sides_of_the_label():
    for attrs in (Attrs(3, 0, 1, 2), Attrs(1, 2, 0, 0), Attrs(2, 1, 2, 1), Attrs(0, 3, 2, 0)):
        flipped = np.fliplr(mq.render_pixels(attrs, CLEAN))
        swapped = mq.render_pixels(attrs.swapped_sides(), CLEAN)
        assert (flipped != swapped).any(axis=2).mean() < 1e-4, attrs


def test_the_variations_never_change_what_the_label_says_and_never_the_drawn_segments():
    attrs = Attrs(2, 1, 2, 0)
    base = set(mq.build_scene(attrs, mq.Appearance(pose="standing")).parts())
    for pose in mq.POSE_ORDER:
        for variation in range(3):
            appearance = dataclasses.replace(dataset.appearance_for(17, variation), pose=pose)
            assert set(mq.build_scene(attrs, appearance).parts()) == base
    records = list(dataset.level1_records(combos=[attrs], variations=3))
    assert [r.attrs for r in records] == [attrs] * 3
    assert len({r.png for r in records}) == 3 and len({r.pose for r in records}) == 3


def test_the_mannequin_cannot_draw_an_unknown_limb():
    with pytest.raises(ValueError):
        mq.build_scene(Attrs(lower_left=UNKNOWN, lower_right=0, upper_left=0, upper_right=0))


def test_the_svg_is_well_formed_and_carries_no_label_only_the_drawn_parts():
    attrs = Attrs(3, 0, 2, 1)
    scene = mq.build_scene(attrs, dataset.appearance_for(3, 0))
    root = ET.fromstring(mq.to_svg(scene))
    assert root.tag.endswith("svg")
    drawn = [e.get("data-part") for e in root if e.get("data-part")]
    assert sorted(drawn) == sorted(scene.parts()) == sorted(expected_parts(attrs))
    text = mq.to_svg(scene)
    assert "lower_left" not in text and "level" not in text


# ---- the level 1 set ---------------------------------------------------------------------------


def test_the_level_1_set_is_144_combinations_by_3_variations_with_unique_ids():
    assert len(level1_combinations()) * dataset.VARIATIONS == 432
    records = list(itertools.islice(dataset.level1_records(), 9))
    assert [r.image_id for r in records] == [f"K34-L1-{i:04d}" for i in range(1, 10)]
    assert [r.attrs for r in records] == [level1_combinations()[i // 3] for i in range(9)]
    assert all(r.level == 1 and r.attrs.wheelchair == r.attrs.prosthesis == UNKNOWN for r in records)
    assert [r.pose for r in records[:3]] == list(mq.POSE_ORDER)


def test_the_appearance_draw_respects_the_ranges_and_always_contrasts_with_the_background():
    for combo, variation in itertools.product(range(144), range(3)):
        a = dataset.appearance_for(combo, variation)
        assert 0.92 <= a.scale <= 1.08 and abs(a.rotation_deg) <= 3 and abs(a.dx) <= 8 and abs(a.dy) <= 8
        assert 0 <= a.noise_sigma <= 8
        for figure in (a.skin, a.shirt, a.shoe):
            for ground in (a.bg_top, a.bg_bottom):
                assert math.dist(figure, ground) >= dataset.MIN_CONTRAST


def test_a_different_seed_gives_a_different_set_but_the_same_labels():
    one = list(dataset.level1_records(seed=1, combos=level1_combinations()[:2]))
    two = list(dataset.level1_records(seed=2, combos=level1_combinations()[:2]))
    assert [r.attrs for r in one] == [r.attrs for r in two] and [r.png for r in one] != [r.png for r in two]
