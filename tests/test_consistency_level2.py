"""image-and-report check, PR 3 step A: level 2 (our synthetic images with variation) and the measurement of its difficulty
(design note section 4.2)."""
import functools
from collections import Counter

import numpy as np
import pytest

from para_triage.consistency import difficulty as df
from para_triage.consistency import level2 as l2
from para_triage.consistency import mannequin as mq
from para_triage.consistency.png import decode_png
from para_triage.consistency.schema import LIMB_FIELDS, UNKNOWN, Attrs


@functools.lru_cache(maxsize=1)
def records():
    return tuple(l2.level2_records())


def of_band(band):
    return [r for r in records() if r.band == band]


# ---- the set -----------------------------------------------------------------------------------


def test_the_set_is_300_images_in_four_bands_of_75_with_unique_ids():
    rs = records()
    assert len(rs) == 300 and len({r.image_id for r in rs}) == 300
    assert Counter(r.band for r in rs) == {0: 75, 1: 75, 2: 75, 3: 75}
    assert all(r.level == 2 for r in rs) and rs[0].image_id == "K34-L2-0001" and rs[-1].image_id == "K34-L2-0300"
    assert all(decode_png(r.png).shape == (mq.HEIGHT, mq.WIDTH, 3) for r in rs[::37])


def test_every_band_uses_the_same_75_limb_combinations_so_the_bands_differ_in_looks_not_in_content():
    truths = [[tuple(r.detail["true_levels"].values()) for r in of_band(b)] for b in range(4)]
    assert truths[0] == truths[1] == truths[2] == truths[3]
    assert len(set(truths[0])) == 75


def test_the_same_seed_gives_the_same_images_and_another_seed_gives_other_ones():
    a, b = list(l2.level2_records(bands=[2], per_band=3)), list(l2.level2_records(bands=[2], per_band=3))
    assert [r.png for r in a] == [r.png for r in b] and [r.attrs for r in a] == [r.attrs for r in b]
    c = list(l2.level2_records(seed=35, bands=[2], per_band=3))
    assert [r.png for r in a] != [r.png for r in c]


def test_the_difficulty_vector_is_kept_per_image_band_0_is_all_zero_and_the_others_are_the_band_or_one_below():
    for r in records():
        assert set(r.vector) == set(l2.FACTORS) and all(0 <= v <= 3 for v in r.vector.values())
        if r.band == 0:
            assert set(r.vector.values()) == {0}
        else:
            assert set(r.vector.values()) <= {r.band - 1, r.band}
    for band in (1, 2, 3):
        assert {v for r in of_band(band) for v in r.vector.values()} == {band - 1, band}  # both values do occur


def test_the_intensity_table_is_complete_versioned_and_starts_at_the_level_1_ranges():
    assert l2.TABLE_VERSION and set(l2.TABLE) == set(l2.FACTORS)
    for factor, params in l2.TABLE.items():
        for name, values in params.items():
            assert len(values) == 4, (factor, name)
    assert l2.TABLE["geometry"]["scale"][0] == (0.92, 1.08) and l2.TABLE["geometry"]["rotation"][0] == 3.0
    assert l2.TABLE["appearance"]["contrast"][0] == 80.0 and l2.TABLE["noise"]["sigma"][0] == 8.0
    assert set(l2.TABLE["pose"]["pool"][0]) == set(mq.POSE_ORDER)  # level 1 poses
    assert l2.TABLE["equipment"]["chair"][0] == l2.TABLE["equipment"]["prosthesis"][0] == 0.0


# ---- the labels --------------------------------------------------------------------------------


def test_band_0_is_like_level_1_no_equipment_no_unknown_and_the_label_is_the_true_level():
    for r in of_band(0):
        assert r.attrs.wheelchair == "no" and r.attrs.prosthesis == "no" and not r.detail["chair"] and not r.detail["prostheses"]
        assert r.detail["occluders"] == 0
        assert [getattr(r.attrs, n) for n in LIMB_FIELDS] == list(r.detail["true_levels"].values())


def test_a_label_is_either_the_true_level_or_unknown_never_another_level():
    for r in records():
        for name in LIMB_FIELDS:
            assert getattr(r.attrs, name) in (r.detail["true_levels"][name], UNKNOWN), (r.image_id, name)


def test_unknown_limbs_and_equipment_appear_in_the_harder_bands_and_grow_with_them():
    unknown = [sum(getattr(r.attrs, n) == UNKNOWN for r in of_band(b) for n in LIMB_FIELDS) for b in range(4)]
    assert unknown[0] == 0 and unknown[3] > unknown[1] > 0, unknown
    chairs = [sum(bool(r.detail["chair"]) for r in of_band(b)) for b in range(4)]
    prostheses = [sum(bool(r.detail["prostheses"]) for r in of_band(b)) for b in range(4)]
    assert chairs[0] == prostheses[0] == 0 and chairs[3] > 0 and prostheses[3] > 0
    kinds = {r.detail["chair"] for r in records()} - {None}
    assert kinds == {"daily", "racing"}


def test_the_equipment_flags_follow_what_was_drawn():
    for r in records():
        if not r.detail["chair"]:
            assert r.attrs.wheelchair == "no"
        else:
            assert r.attrs.wheelchair in ("yes", UNKNOWN) and r.detail["pose"] == "seated"
        if not r.detail["prostheses"]:
            assert r.attrs.prosthesis == "no"
        else:
            assert r.attrs.prosthesis in ("yes", UNKNOWN)
    assert any(r.attrs.wheelchair == "yes" for r in records()) and any(r.attrs.prosthesis == "yes" for r in records())


def test_a_racing_chair_hides_the_legs_a_daily_one_does_not():
    lower = lambda rs: [getattr(r.attrs, n) for r in rs for n in ("lower_left", "lower_right")]  # noqa: E731
    racing = [r for r in records() if r.detail["chair"] == "racing"]
    daily = [r for r in records() if r.detail["chair"] == "daily"]
    assert racing and daily
    hidden_racing = lower(racing).count(UNKNOWN) / len(lower(racing))
    hidden_daily = lower(daily).count(UNKNOWN) / len(lower(daily))
    assert hidden_racing > 0.5 and hidden_racing > hidden_daily + 0.2, (hidden_racing, hidden_daily)


def test_a_limb_is_unknown_when_more_than_the_limit_of_the_end_of_it_is_hidden():
    region = l2.coverage_padded(l2.limb_region("lower", "L", 2, "standing"))
    assert region.sum() > 500
    rows = np.arange(region.shape[0])[:, None]
    top = region.nonzero()[0]
    assert l2.limb_visible(region, np.zeros_like(region))
    assert not l2.limb_visible(region, region)  # all of it hidden
    assert l2.limb_visible(region, region & (rows <= np.percentile(top, 15)))  # a sliver is not enough to call it hidden
    assert not l2.limb_visible(region, region & (rows <= np.percentile(top, 60)))  # more than the limit is
    assert l2.HIDDEN_LIMIT == 0.30


def test_a_figure_cut_by_the_frame_has_unknown_limbs_beyond_the_cut():
    outside = l2.outside_frame()
    foot = l2.coverage_padded(l2.limb_region("lower", "L", 0, "standing"))
    shifted = np.roll(foot, 120, axis=0)  # the foot now lies below the frame
    assert (shifted & outside).sum() / shifted.sum() > 0.3
    assert not l2.limb_visible(shifted, outside)


def test_the_region_that_must_be_seen_grows_with_how_much_of_the_limb_is_missing():
    areas = [l2.coverage_padded(l2.limb_region("lower", "L", level, "standing")).sum() for level in (0, 1, 2, 3)]
    assert areas[0] < areas[1] < areas[2] < areas[3]
    upper = [l2.coverage_padded(l2.limb_region("upper", "R", level, "standing")).sum() for level in (0, 1, 2)]
    assert upper[0] < upper[1] < upper[2]


# ---- pixels ------------------------------------------------------------------------------------


def test_the_jpeg_like_compression_is_stronger_with_lower_quality_and_a_noop_on_flat_images():
    rs = np.random.RandomState(0)
    image = np.clip(rs.normal(128, 40, (mq.HEIGHT, mq.WIDTH, 3)), 0, 255)
    errors = {q: np.abs(l2.jpeg_like(image, q) - image).mean() for q in (90, 55, 30)}
    assert errors[90] < errors[55] < errors[30]
    flat = np.full((mq.HEIGHT, mq.WIDTH, 3), 200.0)
    assert np.abs(l2.jpeg_like(flat, 30) - flat).max() < 3
    assert np.array_equal(l2.jpeg_like(image, 55), l2.jpeg_like(image, 55))


def test_the_box_blur_keeps_flat_areas_and_smooths_edges():
    flat = np.full((20, 24, 3), 90.0)
    assert np.allclose(l2.box_blur(flat, 2), 90.0)
    edge = np.zeros((20, 24, 3))
    edge[:, 12:] = 255
    blurred = l2.box_blur(edge, 2)
    assert 0 < blurred[10, 11, 0] < 255 and blurred[10, 0, 0] == 0 and blurred[10, 23, 0] == 255 and l2.box_blur(edge, 0) is edge


def test_the_affine_with_no_effect_keeps_the_shapes():
    shapes = mq.nominal_shapes(Attrs(0, 0, 0, 0))
    same = l2.make_affine(1.0, 0.0, 0.0, 1.0, 0.0, 0.0)(shapes)
    assert all(np.allclose(a.p, b.p) and np.allclose(a.q, b.q) and a.size == pytest.approx(b.size) for a, b in zip(shapes, same))
    squeezed = l2.make_affine(1.0, 0.0, 0.0, 0.5, 0.0, 0.0)(shapes)
    assert max(abs(s.p[0] - mq.CENTER_X) for s in squeezed) < max(abs(s.p[0] - mq.CENTER_X) for s in shapes)


def test_the_new_poses_exist_and_keep_the_level_1_ones_unchanged():
    assert set(mq.LEVEL2_POSES) <= set(mq.POSES) and mq.POSE_ORDER == ("standing", "arms_up", "seated")
    crossed = mq.joint("arms_crossed", "wrist", "R")
    assert (crossed[0] > mq.CENTER_X) != (mq.joint("standing", "wrist", "R")[0] > mq.CENTER_X)  # the right wrist crosses the centre line
    for pose in mq.LEVEL2_POSES:
        assert set(mq.build_scene(Attrs(0, 0, 0, 0), mq.Appearance(pose=pose)).parts()) >= {"head", "R.hand", "L.foot"}


# ---- the difficulty measurement ----------------------------------------------------------------


def test_the_score_counts_known_limbs_and_all_limbs_separately():
    truth = Attrs(1, UNKNOWN, 0, 2)
    assert df.score(truth, truth) == (3, 3, 4, 4) or df.score(truth, truth) == (3, 3, 3, 4)
    read = Attrs(1, 2, 0, 1)
    kr, kt, ar, at = df.score(read, truth)
    assert (kr, kt, at) == (2, 3, 4) and ar == 2


def test_the_curve_and_the_criterion_on_fake_readers():
    rs = records()
    truth = {r.png: r.attrs for r in rs}
    rows, _ = df.band_curve(rs, truth.__getitem__, draws=50)
    assert [r.band for r in rows] == [0, 1, 2, 3] and all(r.known_rate == 1.0 for r in rows)
    verdict = df.verdict_of_drop(rows)
    assert verdict["drop"] == 0 and not verdict["harder"] and verdict["required"] == 0.2
    # a reader that degrades with the band
    band_of = {r.png: r.band for r in rs}
    def degrading(png):
        label = truth[png]
        return label.with_(lower_left=(label.lower_left if label.lower_left == UNKNOWN else (label.lower_left + 1) % 4)) if band_of[png] == 3 else label
    rows, reads = df.band_curve(rs, degrading, draws=50)
    verdict = df.verdict_of_drop(rows)
    assert verdict["drop"] > 0.2 and verdict["harder"]
    text = df.format_curve(rows, verdict, l2.TABLE_VERSION)
    assert "N1" in text and l2.TABLE_VERSION in text and "mais difícil" in text
    factors = df.by_factor(rs, reads)
    assert set(factors) == set(l2.FACTORS) and all(sum(c[1] for c in v.values()) > 0 for v in factors.values())


def test_the_classical_baseline_is_good_on_band_0_and_worse_on_band_3_on_a_small_sample():
    from para_triage.consistency.baselines import classical_extract

    sample = [r for r in of_band(0)][::5] + [r for r in of_band(3)][::5]
    rows, _ = df.band_curve(sample, classical_extract, draws=50)
    assert rows[0].known_rate >= 0.9, rows[0]
    assert rows[1].known_rate < rows[0].known_rate - 0.2, rows  # the full 300-image measurement is in the report
