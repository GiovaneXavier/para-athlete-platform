"""The rule book of the limb deficiency group standing (classes 42-47, step 3b): a gate, two pathways and their merge.

Every probe is compared with the current engine, which stays the default. The merge of the two pathways is the risky part,
so it has named cases built from what the engine does.
"""
import copy
import itertools

import pytest

from para_triage.education import texts_pt as T
from para_triage.education.trace import _lower_standing as k2_lower
from para_triage.education.trace import _upper_standing as k2_upper
from para_triage.education.trace import build_trace
from para_triage.rulebook import Rulebook
from para_triage.rulebook.compare import Case, book_row, domain_cases, engine_row, format_report, profile_of, regress, sample_cases
from para_triage.rules import Impairment, Posture, Profile, RuleEngine
from para_triage.rules.catalog import load_catalog

LOWER, UPPER = (0, 1, 2, 3), (0, 1, 2)
AMPUTATION, STRENGTH = ("limb_deficiency",), ("muscle_power",)
BOTH = ("limb_deficiency", "muscle_power")
ENGINE = RuleEngine()


@pytest.fixture(scope="module")
def book():
    return Rulebook.load("limb_standing")


def levels(ll=0, lr=0, ul=0, ur=0, **extra):
    return {"posture": "standing", "lower_left": ll, "lower_right": lr, "upper_left": ul, "upper_right": ur, **extra}


def rows(book, measures, impairments):
    """(the current engine's row, the rule book's row) of one profile: per class, (status, missing fields)."""
    case = Case("probe", "probe", measures, tuple(impairments))
    return engine_row(ENGINE, profile_of(case, book), book.classes), book_row(book, case)


def same(book, measures, impairments):
    engine, got = rows(book, measures, impairments)
    assert engine == got, (measures, impairments, engine, got)
    return got


def statuses(row):
    return {c: s for c, (s, _) in row.items()}


# --- the regression ----------------------------------------------------------------------------------------------------


def test_the_products_of_the_domains_of_both_pathways_and_of_the_two_together_agree_with_the_current_engine(book):
    cases = domain_cases(book)
    report = regress(book, cases)
    assert {"domain-amputation", "domain-strength_rom", "domain-fusion"} <= set(report.total) and report.clean, format_report(report)


def test_the_study_mode_sample_with_each_measure_hidden_agrees_with_the_current_engine(book):
    cases = sample_cases(book, range(2))
    report = regress(book, cases)
    assert len(cases) > 3000 and report.clean and {"k2-no-posture", "k2-no-lower_limb_sides_affected", "k2-nothing"} <= set(report.total), format_report(report)


def test_the_144_combinations_of_levels_in_both_postures_agree_in_the_amputation_pathway_alone(book):
    cases = [
        Case(f"{posture}-{c}", "levels", levels(*c, posture=posture), AMPUTATION)
        for posture in ("standing", "prosthesis")
        for c in itertools.product(LOWER, LOWER, UPPER, UPPER)
    ]
    report = regress(book, cases)
    assert len(cases) == 2 * 144 and report.clean, format_report(report)


def test_the_functional_pathway_by_a_sweep_of_the_limits_agrees_with_the_current_engine(book):
    pf, arc, leg = (0, 1, 2, 3, 5, None), (0, 9.99, 10, 10.01, 10.05, 30, None), (0, 6.99, 7, 7.01, 7.05, 20, None)
    cases = [
        Case(f"f-{i}", "sweep", {k: v for k, v in {"posture": "standing", "ankle_pf_mrc": a, "ankle_rom_deg": b, "leg_length_diff_cm": c, "hip_knee_deficit": h, "lower_limb_sides_affected": s}.items() if v is not None}, kinds)
        for i, (a, b, c, h, s, kinds) in enumerate(itertools.product(pf, arc, leg, (None, False, True), (None, 1, 2), (STRENGTH, ("rom",), ("leg_length_difference",))))
    ]
    report = regress(book, cases)
    assert len(cases) == 6 * 7 * 7 * 3 * 3 * 3 and report.clean, format_report(report)


def test_the_two_pathways_together_agree_with_levels_missing_and_hidden_one_at_a_time(book):
    functional = [dict(zip(("ankle_pf_mrc", "ankle_rom_deg", "leg_length_diff_cm", "hip_knee_deficit", "lower_limb_sides_affected"), v)) for v in itertools.product((1, 3, None), (10, 10.01), (7, 6.99), (False, True), (1, 2, None))]
    cases = []
    for base in (levels(3, 0, 0, 0), levels(2, 0, 0, 0), levels(3, 3, 0, 0), levels(0, 0, 2, 2), levels(1, 1, 1, 1), levels(0, 0, 0, 0)):
        for hidden in (None, "lower_left", "lower_right", "upper_left", "upper_right", "posture"):
            shown = {k: v for k, v in base.items() if k != hidden}
            cases += [Case(f"m-{len(cases)}", "fusion", {**shown, **f}, kinds) for f in functional for kinds in (BOTH, (*BOTH, "rom"))]
    report = regress(book, cases)
    assert len(cases) > 2000 and report.clean, format_report(report)


def test_the_regression_detects_a_wrong_threshold_a_wrong_missing_field_and_a_wrong_merge(book):
    sample = domain_cases(book)
    assert not regress(book, sample, overrides={"max_ankle_arc_deg": 11}).clean  # a limit moved
    wrong = copy.deepcopy(book.data)
    next(r for r in wrong["pathways"]["strength_rom"]["decision"] if r["id"] == "sides_unknown")["report_always"] = []
    assert not regress(Rulebook(wrong), sample).clean  # the field the verdict asks for
    wrong = copy.deepcopy(book.data)
    rule = next(r for r in wrong["pathways"]["strength_rom"]["decision"] if r["id"] == "sides_unknown")
    rule["report_missing"] = rule.pop("report_always")  # the old reading: only what is missing is asked for
    assert not regress(Rulebook(wrong), sample).clean  # a number of sides outside one and two brings the difference back
    wrong = copy.deepcopy(book.data)
    wrong["pathways"] = dict(reversed(list(wrong["pathways"].items())))  # the order of the pathways decides the missing of a tie
    assert not regress(Rulebook(wrong), sample).clean


# --- the probes of the current engine: the gate -------------------------------------------------------------------------


def test_without_the_posture_everything_is_insufficient_and_only_the_posture_is_asked_for_in_both_pathways(book):
    row = same(book, {"lower_left": 3, "ankle_pf_mrc": 1}, BOTH)
    assert set(row.values()) == {("insufficient_data", ("posture",))}


def test_another_posture_is_not_met_and_asks_for_nothing_even_when_everything_else_is_missing(book):
    for posture in ("prosthesis", "seated", "frame_runner"):
        assert set(same(book, {"posture": posture}, BOTH).values()) == {("not_met", ())}


# --- the amputation pathway alone ---------------------------------------------------------------------------------------


def test_missing_levels_are_listed_in_the_order_of_the_fields_and_both_limbs_together_need_review(book):
    row = same(book, {"posture": "standing", "lower_right": 3, "upper_left": 1}, AMPUTATION)
    assert set(row.values()) == {("insufficient_data", ("lower_left", "upper_right"))}
    assert set(statuses(same(book, levels(3, 0, 1, 0), AMPUTATION)).values()) == {"needs_review"}


def test_each_row_of_the_two_tables_gives_the_class_or_the_review_of_the_engine(book):
    expected = {
        (3, 0, 0, 0): {42: "meets"}, (0, 3, 0, 0): {42: "meets"}, (3, 1, 0, 0): {42: "borderline"}, (3, 2, 0, 0): {}, (3, 3, 0, 0): {},
        (2, 2, 0, 0): {43: "meets"}, (2, 0, 0, 0): {44: "meets"}, (2, 1, 0, 0): {43: "borderline", 44: "borderline"}, (1, 0, 0, 0): {44: "borderline"}, (1, 1, 0, 0): {},
        (0, 0, 2, 2): {45: "meets"}, (0, 0, 2, 0): {46: "meets"}, (0, 0, 1, 1): {46: "meets"}, (0, 0, 2, 1): {45: "borderline", 46: "borderline"}, (0, 0, 1, 0): {47: "meets"},
    }
    for pair, wanted in expected.items():
        got = statuses(same(book, levels(*pair), AMPUTATION))
        review = {c for c, s in got.items() if s == "needs_review"}
        assert {c: s for c, s in got.items() if s in ("meets", "borderline")} == wanted, pair
        assert review == (set(book.classes) if not wanted else set()), pair  # a row without a class is a review of every class
    assert set(statuses(same(book, levels(), AMPUTATION)).values()) == {"not_met"}  # no amputation recorded


# --- the functional pathway alone ---------------------------------------------------------------------------------------


def test_each_minimum_criterion_alone_gives_class_44_on_one_side_with_its_limit_included(book):
    for measure, met, not_met in (("ankle_pf_mrc", 2, 3), ("ankle_rom_deg", 10, 10.01), ("leg_length_diff_cm", 7, 6.99)):
        given = {"posture": "standing", "lower_limb_sides_affected": 1}
        assert statuses(same(book, {**given, measure: met}, STRENGTH))[44] == "meets", measure
        assert statuses(same(book, {**given, measure: not_met}, STRENGTH))[44] == "not_met", measure


def test_two_sides_need_review_and_an_unknown_number_of_sides_makes_44_borderline_and_asks_for_it(book):
    two = same(book, {"posture": "standing", "ankle_pf_mrc": 1, "lower_limb_sides_affected": 2}, STRENGTH)
    assert set(two.values()) == {("needs_review", ())}
    unknown = same(book, {"posture": "standing", "ankle_pf_mrc": 1}, STRENGTH)
    assert unknown[44] == ("borderline", ("lower_limb_sides_affected",)) and unknown[42] == ("not_met", ("lower_limb_sides_affected",))


def test_the_hip_and_knee_deficit_makes_42_borderline_with_or_without_a_minimum_criterion(book):
    alone = same(book, {"posture": "standing", "ankle_pf_mrc": 5, "hip_knee_deficit": True}, STRENGTH)
    assert statuses(alone) == {42: "borderline", 43: "not_met", 44: "not_met", 45: "not_met", 46: "not_met", 47: "not_met"} and alone[42][1] == ()
    with_cme = same(book, {"posture": "standing", "ankle_pf_mrc": 1, "hip_knee_deficit": True, "lower_limb_sides_affected": 1}, STRENGTH)
    assert statuses(with_cme)[44] == "meets" and statuses(with_cme)[42] == "borderline"


def test_no_ankle_measure_is_insufficient_and_asks_for_the_three_and_a_measure_that_is_not_met_asks_for_the_others(book):
    nothing = same(book, {"posture": "standing"}, STRENGTH)
    assert set(nothing.values()) == {("insufficient_data", ("ankle_pf_mrc", "ankle_rom_deg", "leg_length_diff_cm"))}
    partial = same(book, {"posture": "standing", "ankle_pf_mrc": 4}, STRENGTH)
    assert set(partial.values()) == {("not_met", ("ankle_rom_deg", "leg_length_diff_cm"))}


def test_the_pathway_runs_only_for_the_impairments_it_is_about_so_levels_are_ignored_without_limb_deficiency(book):
    row = same(book, levels(3, 0, ankle_pf_mrc=4), STRENGTH)
    assert set(row.values()) == {("not_met", ("ankle_rom_deg", "leg_length_diff_cm"))}  # the 42 of the levels is not read
    assert set(same(book, levels(3, 0), ("rom",)).values()) == {("insufficient_data", ("ankle_pf_mrc", "ankle_rom_deg", "leg_length_diff_cm"))}


@pytest.mark.parametrize("sides", (0, 3, -1))
def test_a_number_of_sides_outside_one_and_two_is_asked_for_again_like_the_current_engine(book, sides):
    # The API only accepts 1 or 2 (`Field(ge=1, le=2)`), but the engine called directly asks for the sides again, and so does `report_always`.
    engine = same(book, {"posture": "standing", "ankle_pf_mrc": 1, "lower_limb_sides_affected": sides}, STRENGTH)
    assert engine[44] == ("borderline", ("lower_limb_sides_affected",)) and engine[42] == ("not_met", ("lower_limb_sides_affected",))
    both = same(book, levels(2, 0, ankle_pf_mrc=1, lower_limb_sides_affected=sides, hip_knee_deficit=True), BOTH)
    assert both[44][0] == "meets" and both[42][0] == "borderline"


def test_a_sweep_of_the_number_of_sides_including_values_outside_the_contract_agrees_with_the_current_engine(book):
    cases = [
        Case(f"s-{i}", "sides", {k: v for k, v in {"posture": "standing", "ankle_pf_mrc": a, "ankle_rom_deg": b, "hip_knee_deficit": h, "lower_limb_sides_affected": s}.items() if v is not None}, kinds)
        for i, (a, b, h, s, kinds) in enumerate(itertools.product((1, 4, None), (10, 30, None), (None, False, True), (None, 0, 1, 2, 3, -1), (STRENGTH, BOTH)))
    ]
    report = regress(book, cases)
    assert len(cases) == 3 * 3 * 3 * 6 * 2 and report.clean, format_report(report)


# --- the merge of the two pathways: named cases built from the engine ---------------------------------------------------


def test_a_meets_beats_a_borderline_of_the_other_pathway_and_the_winner_keeps_its_own_empty_missing(book):
    # amputation: below knee on one side, so 44 meets. strength: a weak ankle but the sides are not provided, so 44 is borderline and asks for them.
    alone = same(book, {"posture": "standing", "ankle_pf_mrc": 1}, STRENGTH)
    assert alone[44] == ("borderline", ("lower_limb_sides_affected",))
    row = same(book, levels(2, 0, ankle_pf_mrc=1), BOTH)
    assert row[44] == ("meets", ())


def test_a_borderline_beats_an_insufficient_and_the_winner_brings_its_own_missing(book):
    # the levels of the lower limbs are missing, so the amputation pathway is insufficient_data on every class (it asks for the levels).
    given = {"posture": "standing", "upper_left": 0, "upper_right": 0, "ankle_pf_mrc": 1}
    row = same(book, given, BOTH)
    assert row[44] == ("borderline", ("lower_limb_sides_affected",))  # the strength pathway wins class 44 and brings its own missing
    assert {row[c] for c in (42, 43, 45, 46, 47)} == {("insufficient_data", ("lower_left", "lower_right"))}  # an insufficient_data beats a not_met
    row = same(book, {**given, "lower_limb_sides_affected": 1}, BOTH)
    assert row[44] == ("meets", ()) and row[42] == ("insufficient_data", ("lower_left", "lower_right"))


def test_a_review_of_one_pathway_beats_the_not_met_of_the_other_but_not_its_meets(book):
    # both sides affected: the strength pathway reviews every class; the amputation pathway meets 44 and has not_met on the rest.
    row = same(book, levels(2, 0, ankle_pf_mrc=1, lower_limb_sides_affected=2), BOTH)
    assert row[44] == ("meets", ()) and {s for c, (s, _) in row.items() if c != 44} == {"needs_review"}


def test_an_insufficient_data_beats_a_not_met_and_brings_the_missing_of_the_pathway_that_could_not_decide(book):
    # no amputation recorded (not_met on every class) and no ankle measure (insufficient_data on every class)
    row = same(book, levels(), BOTH)
    assert set(row.values()) == {("insufficient_data", ("ankle_pf_mrc", "ankle_rom_deg", "leg_length_diff_cm"))}


def test_a_tie_keeps_the_missing_of_the_first_pathway_the_amputation(book):
    # 43 is not_met in both: the amputation pathway reports nothing, the strength pathway asks for the sides; the first one stays.
    row = same(book, levels(2, 0, ankle_pf_mrc=1), BOTH)
    assert row[43] == ("not_met", ()) and row[42] == ("not_met", ())
    # the same with the ankle measures: the strength pathway asks for two of them, and the tie drops them
    row = same(book, levels(2, 0, ankle_pf_mrc=4), BOTH)
    assert row[43] == ("not_met", ()) and row[44] == ("meets", ())
    # both are insufficient_data: the levels come first, not the ankle measures
    row = same(book, {"posture": "standing", "lower_left": 3}, BOTH)
    assert set(row.values()) == {("insufficient_data", ("lower_right", "upper_left", "upper_right"))}


def test_a_tie_adds_the_reasons_of_both_pathways_without_repeating_them(book):
    evaluation = book.evaluate(levels(2, 0, ankle_pf_mrc=4), set(BOTH))
    assert evaluation.verdicts[43].reasons == ("LIMB_UNILATERAL_BELOW", "LIMB_NO_CME_MET") and evaluation.decision == "unilateral_below+no_cme"
    assert evaluation.verdicts[44].reasons == ("LIMB_UNILATERAL_BELOW",)  # a meets does not take the reasons of the loser
    both_insufficient = book.evaluate({"posture": "standing", "lower_left": 3}, set(BOTH)).verdicts[42]
    assert both_insufficient.reasons == ("LIMB_LEVELS_MISSING", "LIMB_NO_ANKLE_MEASURE")


def test_the_hip_and_knee_borderline_survives_the_merge_with_an_amputation_that_meets_44(book):
    row = same(book, levels(2, 0, ankle_pf_mrc=5, hip_knee_deficit=True), BOTH)
    assert row[42] == ("borderline", ()) and row[44] == ("meets", ())
    assert [r for r in book.evaluate(levels(2, 0, ankle_pf_mrc=5, hip_knee_deficit=True), set(BOTH)).verdicts[43].reasons] == ["LIMB_UNILATERAL_BELOW", "LIMB_HIP_KNEE_ASSESSMENT"]


# --- the study mode explains the same table ----------------------------------------------------------------------------


def k2_profile(ll, lr, ul, ur):
    return Profile(impairments=frozenset({Impairment.LIMB_DEFICIENCY}), posture=Posture.STANDING, lower_left=ll, lower_right=lr, upper_left=ul, upper_right=ur)


def test_the_rows_of_the_tables_are_the_rows_of_the_study_mode_with_the_same_conclusion(book):
    checked = 0
    for ll, lr, ul, ur in itertools.product(LOWER, LOWER, UPPER, UPPER):
        trace = build_trace("limb_standing", k2_profile(ll, lr, ul, ur))
        evaluation = book.evaluate(levels(ll, lr, ul, ur), set(AMPUTATION))
        meets = [c for c, v in evaluation.verdicts.items() if v.status == "meets"]
        if max(ll, lr) and max(ul, ur):
            assert evaluation.decision == "lower_and_upper" and trace.answer == "specialist"
        elif not max(ll, lr) and not max(ul, ur):
            assert evaluation.decision == "no_amputation" and trace.answer == "none"
        else:
            lower = bool(max(ll, lr))
            row = (k2_lower if lower else k2_upper)(max(ll, lr) if lower else max(ul, ur), min(ll, lr) if lower else min(ul, ur))
            assert evaluation.decision == row[1] and trace.answer == (f"class:{meets[0]}" if meets else "specialist")
            assert trace.steps[-1].explanation == T.LIMB_ROWS[("lower_standing" if lower else "upper_standing", row[1])]
            checked += 1
    assert checked == 15 + 8  # 15 combinations with only a lower amputation, 8 with only an upper one (the rest: both, or none)


# --- the numbers -----------------------------------------------------------------------------------------------------------


def test_the_three_limits_of_the_functional_pathway_are_provisional_and_say_they_are_an_example_of_a_minimum_criterion(book):
    for name, value in (("max_plantar_flexion_mrc", 2), ("max_ankle_arc_deg", 10), ("min_leg_length_diff_cm", 7)):
        spec = book.data["parameters"][name]
        assert spec["status"] == "provisional" and spec["values"][0]["value"] == value and "note" in spec["source"], name
    assert "F57" in book.data["parameters"]["min_leg_length_diff_cm"]["source"]["note"]
    assert not any(c in book.data["parameters"] for c in ("sides", "hip_knee"))  # the other numbers are not limits


def test_the_classes_of_the_group_are_the_ones_of_the_catalog_and_the_table_is_the_only_copy(book):
    catalog = load_catalog()
    assert book.classes == sorted(c.class_id for c in catalog.group_classes("limb_standing"))
    assert not any(catalog.classes[c].criteria for c in book.classes)
    assert set(book.data["applies_to"]) == {i.value for i in catalog.groups["limb_standing"].impairments}
    assert set(book.data["applies_to"]) == {i for p in book.data["pathways"].values() for i in p["applies_to"]}


def test_the_domains_and_the_fusion_include_numbers_of_sides_outside_the_contract_so_the_difference_cannot_return_unseen(book):
    for values in (book.data["domains"]["lower_limb_sides_affected"], book.data["fusion"]["lower_limb_sides_affected"]):
        assert {0, 3, -1} <= set(values) and {1, 2} <= set(values)
    for source in ("domain-strength_rom", "domain-fusion"):
        seen = {c.measures.get("lower_limb_sides_affected") for c in domain_cases(book) if c.source == source}
        assert {None, 0, 1, 2, 3, -1} <= seen, source
