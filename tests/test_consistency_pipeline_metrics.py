"""K34, PR 2: the pipeline with fake extractors and the metrics (design note sections 8 and 12)."""
import types

import pytest

from para_triage.consistency import errors as er
from para_triage.consistency import fakes, metrics, pipeline
from para_triage.consistency.compare import CONFERE, NAO_CONFERE, NAO_SEI, VERDICTS, compare
from para_triage.consistency.schema import UNKNOWN, Attrs, level1_combinations

LABELS = level1_combinations()[::4]  # 36 labels, every value of every limb present


@pytest.fixture(scope="module")
def world():
    # Fake "images": the bytes are just an identifier, so no rendering is needed to test the pipeline.
    records = [types.SimpleNamespace(image_id=f"img-{i:03d}", level=1, attrs=a, png=f"png-{i:03d}".encode()) for i, a in enumerate(LABELS)]
    pairs = er.build_pairs([(r.image_id, r.attrs) for r in records])
    return records, pairs, pipeline.index_images(records)


def run(world, image_extractor=None, report_extractor=None, **kwargs):
    records, pairs, images = world
    return pipeline.evaluate(pairs, images, image_extractor or fakes.oracle_image_extractor(records),
                             report_extractor or fakes.oracle_report_extractor(pairs), **kwargs)


# ---- the pipeline ------------------------------------------------------------------------------


def test_perfect_fake_extractors_give_the_expected_verdict_everywhere(world):
    outcomes = run(world)
    assert len(outcomes) == sum(1 for p in world[1] if p.content is not None)
    assert all(o.correct and o.locus == "" and not o.image_wrong and not o.report_wrong for o in outcomes)
    assert {o.got for o in outcomes} == set(VERDICTS)


def test_each_image_is_read_once_and_the_extractors_only_get_bytes_and_text(world):
    records, pairs, images = world
    seen_images, seen_texts = [], []
    image_oracle, report_oracle = fakes.oracle_image_extractor(records), fakes.oracle_report_extractor(pairs)

    def image_extractor(png):
        assert isinstance(png, bytes)
        seen_images.append(png)
        return image_oracle(png)

    def report_extractor(text):
        assert isinstance(text, str)
        seen_texts.append(text)
        return report_oracle(text)

    pipeline.evaluate(pairs, images, image_extractor, report_extractor)
    assert len(seen_images) == len(records) == len(set(seen_images))
    assert len(seen_texts) == sum(1 for p in pairs if p.content is not None)


def test_pairs_that_could_not_be_built_are_not_run(world):
    records, pairs, images = world
    only_blank = [("blank", Attrs(wheelchair="yes"))]
    blank_pairs = er.build_pairs(only_blank)
    assert any(p.content is None for p in blank_pairs)
    blank = types.SimpleNamespace(image_id="blank", level=1, attrs=only_blank[0][1], png=b"blank")
    outcomes = pipeline.evaluate(blank_pairs, {"blank": blank}, lambda png: blank.attrs, fakes.oracle_report_extractor(blank_pairs))
    assert len(outcomes) == sum(1 for p in blank_pairs if p.content is not None) < len(blank_pairs)


def test_an_image_extractor_that_swaps_sides_is_found_in_the_image_and_only_there(world):
    outcomes = run(world, image_extractor=fakes.flip_sides(fakes.oracle_image_extractor(world[0])))
    wrong = [o for o in outcomes if not o.correct]
    assert wrong and all(o.locus == "imagem" for o in wrong)
    consistent = [o for o in outcomes if o.kind == er.CONSISTENT]
    for o in consistent:
        assert (o.got == NAO_CONFERE) == (o.image_true.swapped_sides() != o.image_true)  # only asymmetric labels raise the alarm
    assert all(o.report_read == o.report_true for o in outcomes)


def test_a_report_extractor_that_swaps_sides_is_found_in_the_report_and_only_there(world):
    outcomes = run(world, report_extractor=fakes.flip_sides(fakes.oracle_report_extractor(world[1])))
    wrong = [o for o in outcomes if not o.correct]
    assert wrong and all(o.locus == "laudo" for o in wrong)
    assert all(o.image_read == o.image_true for o in outcomes)


def test_two_equal_mistakes_can_cancel_and_the_outcome_still_says_the_readings_were_wrong(world):
    records, pairs, _ = world
    outcomes = run(world, fakes.flip_sides(fakes.oracle_image_extractor(records)), fakes.flip_sides(fakes.oracle_report_extractor(pairs)))
    consistent = [o for o in outcomes if o.kind == er.CONSISTENT and o.image_true.swapped_sides() != o.image_true]
    assert consistent and all(o.correct and o.locus == "" and o.image_wrong and o.report_wrong for o in consistent)


def test_a_level_slip_in_the_image_reading_turns_a_consistent_pair_into_a_false_alarm(world):
    outcomes = run(world, image_extractor=fakes.shift_level(fakes.oracle_image_extractor(world[0]), "lower_left"))
    consistent = [o for o in outcomes if o.kind == er.CONSISTENT]
    assert all(o.got == NAO_CONFERE and o.locus == "imagem" for o in consistent)


def test_an_image_extractor_that_answers_unknown_gives_nao_sei_on_consistent_pairs(world):
    outcomes = run(world, image_extractor=fakes.say_unknown(fakes.oracle_image_extractor(world[0])))
    assert all(o.got == NAO_SEI for o in outcomes if o.kind == er.CONSISTENT)
    assert all(o.locus == "imagem" for o in outcomes if not o.correct)


def test_a_broken_comparator_is_located_in_the_comparison_and_nowhere_else(world):
    outcomes = run(world, comparator=lambda image, report: compare(image, report.with_(lower_left=UNKNOWN)))
    broken = [o for o in outcomes if not o.correct]
    assert broken and all(o.locus == "comparação" for o in broken)


# ---- the metrics -------------------------------------------------------------------------------


def test_wilson_matches_the_reference_values():
    low, high = metrics.wilson(5, 10)
    assert (round(low, 4), round(high, 4)) == (0.2366, 0.7634)
    low, high = metrics.wilson(15, 30)
    assert (round(low, 4), round(high, 4)) == (0.3315, 0.6685)
    z2 = metrics.Z95**2
    assert metrics.wilson(0, 20) == (0.0, pytest.approx(z2 / (20 + z2)))
    assert metrics.wilson(20, 20) == (pytest.approx(20 / (20 + z2)), 1.0)
    assert metrics.wilson(0, 0) == (0.0, 1.0)
    with pytest.raises(ValueError):
        metrics.wilson(11, 10)


def test_the_wilson_interval_always_contains_the_estimate_and_narrows_with_n():
    for n in (5, 30, 432):
        for k in range(0, n + 1, max(1, n // 7)):
            low, high = metrics.wilson(k, n)
            assert 0 <= low <= k / n <= high <= 1
    assert metrics.wilson(15, 30)[1] - metrics.wilson(15, 30)[0] > metrics.wilson(150, 300)[1] - metrics.wilson(150, 300)[0]


def test_the_bootstrap_is_reproducible_with_a_seed_and_changes_with_another():
    cells = {f"i{i}": (i % 4, 4) for i in range(40)}
    assert metrics.bootstrap_by_image(cells, 500, seed=1) == metrics.bootstrap_by_image(cells, 500, seed=1)
    assert metrics.bootstrap_by_image(cells, 500, seed=1) != metrics.bootstrap_by_image(cells, 500, seed=2)
    low, high = metrics.bootstrap_by_image(cells, 500, seed=1)
    assert low <= sum(c[0] for c in cells.values()) / sum(c[1] for c in cells.values()) <= high


def test_the_bootstrap_resamples_images_not_pairs_so_correlated_pairs_widen_the_interval():
    # 20 images, 7 pairs each; every image is either all right or all wrong: only 20 independent units
    cells = {f"i{i}": (7 if i % 2 else 0, 7) for i in range(20)}
    wilson_low, wilson_high = metrics.wilson(70, 140)
    boot_low, boot_high = metrics.bootstrap_by_image(cells, 2000, seed=0)
    assert boot_high - boot_low > 1.5 * (wilson_high - wilson_low)
    assert metrics.bootstrap_by_image({"a": (3, 3)}, 100) == (1.0, 1.0)
    assert metrics.bootstrap_by_image({}, 100) == (0.0, 1.0)


def test_the_summary_has_a_row_per_level_and_kind_with_the_size_of_the_set(world):
    records, pairs, _ = world
    summary = metrics.summarize(run(world), pairs, draws=200)
    kinds = [r.kind for r in summary.rows if r.level == 1]
    assert kinds == list(er.KINDS) + ["all errors"]
    for r in summary.rows:
        assert r.pairs > 0 and r.images > 0 and r.correct == r.pairs and r.rate == 1.0 and r.wilson[1] == 1.0
    swap = next(r for r in summary.rows if r.kind == er.SIDE_SWAP)
    assert swap.indistinguishable == sum(1 for p in pairs if p.kind == er.SIDE_SWAP and p.status == er.INDISTINGUISHABLE) > 0
    assert swap.pairs + swap.indistinguishable == len(records)  # nothing vanishes
    assert next(r for r in summary.rows if r.kind == er.WRONG_LEVEL).redirected > 0


def test_indistinguishable_pairs_are_out_of_the_rates_even_when_the_extractor_gets_them_wrong(world):
    records, pairs, _ = world
    # an image extractor that always says "all zero" hits the symmetric-side images by luck: the swap pair for (0,0,0,0) cannot be wrong
    outcomes = run(world, image_extractor=fakes.say_unknown(fakes.oracle_image_extractor(records), names=("lower_left",)))
    summary = metrics.summarize(outcomes, pairs, draws=50)
    swap = next(r for r in summary.rows if r.kind == er.SIDE_SWAP)
    assert swap.pairs == sum(1 for o in outcomes if o.kind == er.SIDE_SWAP and o.status == er.OK)


def test_false_alarm_unsure_rate_confusion_and_components(world):
    records, pairs, _ = world
    outcomes = run(world, image_extractor=fakes.shift_level(fakes.oracle_image_extractor(records), "upper_left"))
    summary = metrics.summarize(outcomes, pairs, draws=100)
    alarm = summary.false_alarm[1]
    assert alarm.correct == alarm.pairs  # every consistent and noisy pair now raises "não confere"
    matrix = summary.confusion[1]
    used = [o for o in outcomes if o.status == er.OK]
    assert sum(sum(row.values()) for row in matrix.values()) == len(used)
    assert matrix[CONFERE][NAO_CONFERE] == sum(1 for o in used if o.expected == CONFERE)
    image_side = summary.components[1]["image"]
    assert image_side["upper_left"][0] == 0 and image_side["lower_left"] == (len(records), len(records))
    assert summary.components[1]["report"]["lower_left"][0] == summary.components[1]["report"]["lower_left"][1]
    assert summary.wrong_by_locus[1]["imagem"] > 0
    assert summary.unsure_rate[1][1] == len(used)


def test_the_verdict_chance_is_the_most_common_expected_verdict(world):
    summary = metrics.summarize(run(world), world[1], draws=50)
    verdict, count, total = summary.verdict_chance[1]
    expected = [o.expected for o in run(world) if o.status == er.OK]
    assert total == len(expected) and count == max(expected.count(v) for v in VERDICTS) and verdict == NAO_CONFERE


def test_the_formatted_table_names_the_evidence_level_and_never_says_acuracia_without_it(world):
    text = metrics.format_summary(metrics.summarize(run(world), world[1], draws=50))
    assert text.startswith(metrics.EVIDENCE) and "N1" in text
    for line in text.splitlines():
        if "acurácia" in line.lower():
            assert "N1" in line
    assert "| consistent |" in text and "all errors" in text and "Matriz de confusão" in text and "Chute do veredito" in text
    for kind in er.KINDS:
        assert f"| {kind} |" in text
    assert "elegível" not in text and "rejeitad" not in text


def test_an_empty_run_summarizes_to_nothing_without_failing():
    summary = metrics.summarize([], [], draws=10)
    assert summary.rows == [] and metrics.format_summary(summary).startswith("Evidência: N1")
