"""image-and-report check, PR 2: the classical baseline that reads the mannequin PNG, and the chance baseline (design note sections 7 and 12).

The classical reader is slow-ish (about a third of a second per image), so the default run uses a fixed subset.
The whole level 1 set (432 images) runs with `IMAGEM_LAUDO_COMPLETO=1`; its result, measured, is in the design note.
"""
import os
from collections import Counter

import numpy as np
import pytest

from para_triage.consistency import baselines as bl
from para_triage.consistency import dataset, errors, fakes, pipeline
from para_triage.consistency import mannequin as mq
from para_triage.consistency.png import encode_png
from para_triage.consistency.reports import read_report
from para_triage.consistency.schema import LEVEL1_ATTRIBUTES, UNKNOWN, Attrs, level1_combinations

COMBOS = level1_combinations()


def read(attrs, appearance=mq.Appearance(), view="front"):
    return bl.classical_read(mq.render(attrs, appearance).png, view)


def test_the_classical_reader_gets_the_clean_mannequin_right_in_every_pose():
    for attrs in COMBOS[::17]:
        for pose in mq.POSE_ORDER:
            got = read(attrs, mq.Appearance(pose=pose))
            assert got.attrs == attrs and got.pose == pose, (attrs, pose, got)


def test_reading_the_mirror_image_swaps_the_sides_so_left_and_right_are_the_persons():
    for attrs in (Attrs(3, 0, 1, 2), Attrs(0, 2, 0, 1), Attrs(1, 3, 2, 0)):
        pixels = mq.render_pixels(attrs, mq.Appearance())
        assert bl.classical_extract(encode_png(pixels)) == attrs
        assert bl.classical_extract(encode_png(np.ascontiguousarray(pixels[:, ::-1]))) == attrs.swapped_sides()
        # in the back view the person's left is on the left of the image: reading with the right view gives the same label
        assert bl.classical_extract(mq.render(attrs, mq.Appearance(view="back")).png, view="back") == attrs
        # and reading a back-view picture as if it were a front view swaps the sides
        assert bl.classical_extract(mq.render(attrs, mq.Appearance(view="back")).png, view="front") == attrs.swapped_sides()


def test_the_reader_only_sees_pixels_it_gets_no_label_and_no_appearance():
    import inspect

    assert list(inspect.signature(bl.classical_extract).parameters) == ["png", "view"]
    attrs = Attrs(2, 3, 1, 0)
    assert bl.classical_extract(mq.render(attrs, dataset.appearance_for(9, 2)).png) == bl.classical_extract(mq.render(attrs, dataset.appearance_for(9, 2)).png)


def test_a_picture_without_a_figure_is_answered_with_unknown_not_a_guess():
    blank = encode_png(np.full((mq.HEIGHT, mq.WIDTH, 3), 200, np.uint8))
    got = bl.classical_read(blank)
    assert got.attrs == Attrs() and got.pose is None and got.alignment < bl.MIN_ALIGNMENT


def test_the_foreground_follows_a_vertical_gradient_of_the_background():
    a = mq.Appearance(bg_top=(240, 240, 240), bg_bottom=(200, 220, 240))
    mask = bl.foreground(mq.render_pixels(Attrs(0, 0, 0, 0), a))
    covered = mq.coverage(mq.build_scene(Attrs(0, 0, 0, 0), a).shapes)
    assert (mask & ~covered).sum() == 0 and (covered & ~mask).sum() < 0.02 * covered.sum()


@pytest.fixture(scope="module")
def subset():
    return list(dataset.level1_records(combos=COMBOS[::12]))  # 12 combinations x 3 variations = 36 images, all poses


def test_the_classical_baseline_on_a_fixed_subset_of_level_1_with_all_the_variations(subset):
    assert len(subset) == 36 and {r.pose for r in subset} == set(mq.POSE_ORDER)
    right = Counter()
    for r in subset:
        got = bl.classical_extract(r.png)
        right["whole"] += got == r.attrs
        for name in LEVEL1_ATTRIBUTES:
            right[name] += getattr(got, name) == getattr(r.attrs, name)
        assert got.wheelchair == got.prosthesis == UNKNOWN
    assert right["whole"] >= 0.94 * len(subset), right  # measured: 431 of 432 on the whole set, see the design note
    assert all(right[n] >= 0.94 * len(subset) for n in LEVEL1_ATTRIBUTES), right


def test_the_baselines_run_through_the_pipeline_and_the_chance_baseline_is_the_floor(subset):
    pairs = errors.build_pairs([(r.image_id, r.attrs) for r in subset])
    images = pipeline.index_images(subset)
    classical = pipeline.evaluate(pairs, images, bl.classical_extract, read_report)
    guess = bl.ConstantExtractor(bl.majority_attrs(r.attrs for r in subset))
    chance = pipeline.evaluate(pairs, images, guess, guess)
    usable = lambda outs: [o for o in outs if o.status == errors.OK]  # noqa: E731
    classical_rate = sum(o.correct for o in usable(classical)) / len(usable(classical))
    chance_rate = sum(o.correct for o in usable(chance)) / len(usable(chance))
    assert classical_rate > 0.95 and chance_rate < 0.5 and classical_rate > chance_rate + 0.4
    assert {o.got for o in chance} == {"confere"}  # the constant guess never raises a warning: that is what makes it a floor
    assert all(o.locus in ("", "imagem") for o in classical)  # the rule-based report reader never errs on these reports


def test_the_majority_baseline_picks_the_most_common_known_value_per_attribute():
    labels = [Attrs(1, 2, 0, 1), Attrs(1, 3, 0, 2), Attrs(2, 3, 1, 2, "yes"), Attrs(1, 3, 0, 2, "yes", "no")]
    guess = bl.majority_attrs(labels)
    assert guess == Attrs(1, 3, 0, 2, "yes", "no")
    assert bl.majority_attrs([]) == Attrs()
    assert bl.majority_attrs([Attrs(0, 1), Attrs(1, 0)]) == Attrs(0, 0)  # a tie goes to the smaller value
    assert bl.ConstantExtractor(guess)(b"anything") == guess == bl.ConstantExtractor(guess)("any text")


def test_the_oracle_pipeline_on_real_pngs_agrees_with_the_expected_verdicts(subset):
    pairs = errors.build_pairs([(r.image_id, r.attrs) for r in subset])
    outcomes = pipeline.evaluate(pairs, pipeline.index_images(subset), fakes.oracle_image_extractor(subset), fakes.oracle_report_extractor(pairs))
    assert outcomes and all(o.correct for o in outcomes)


@pytest.mark.skipif(not os.environ.get("IMAGEM_LAUDO_COMPLETO"), reason="renders and reads all 432 images (a few minutes); set IMAGEM_LAUDO_COMPLETO=1")
def test_the_classical_baseline_on_the_whole_level_1_set():
    records = list(dataset.level1_records())
    assert len(records) == 432
    right = sum(bl.classical_extract(r.png) == r.attrs for r in records)
    assert right >= 0.99 * 432, right
