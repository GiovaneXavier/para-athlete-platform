"""The rule book of the seated physical group (classes 51-57, step 5b): a provisional group reproduced as it is.

Every probe is compared with the current engine, which stays the default. The three limits of the ankle are borrowed from
limb_standing, which has the same set of impairments. Nothing is corrected: the behaviours that look odd are tested as given.
"""
import copy
import datetime as dt
import itertools

import pytest
import yaml

from para_triage.rulebook import Rulebook, RulebookError
from para_triage.rulebook.compare import Case, book_row, domain_cases, engine_row, format_report, profile_of, regress, sample_cases
from para_triage.rulebook.interpreter import DATA
from para_triage.rules import RuleEngine
from para_triage.rules.catalog import load_catalog

ENGINE = RuleEngine()
KINDS = ("limb_deficiency", "muscle_power", "rom", "leg_length_difference")
SEATED = {"posture": "seated"}
LEGS = {"arm_function": 3, "trunk_function": 2}
PF, ARC, LENGTH = (0, 2, 3, None), (9.99, 10, 10.01, None), (6.99, 7, 7.01, None)
ANKLE = {"posture": "seated", "arm_function": 3, "trunk_function": 2, "leg_function": 3}


@pytest.fixture(scope="module")
def book():
    return Rulebook.load("wheelchair")


def rows(book, measures, impairments=KINDS):
    case = Case("probe", "probe", measures, tuple(impairments))
    return engine_row(ENGINE, profile_of(case, book), book.classes), book_row(book, case)


def same(book, measures, impairments=KINDS):
    engine, got = rows(book, measures, impairments)
    assert engine == got, (measures, engine, got)
    return got


def discrete():
    """Every combination of the descriptors (each also missing), with no ankle measure."""
    for combo in itertools.product(("standing", "prosthesis", "seated", "frame_runner", None), (0, 1, 2, 3, None), (0, 1, 2, None), (0, 1, 2, 3, 4, None)):
        yield {k: v for k, v in zip(("posture", "arm_function", "trunk_function", "leg_function"), combo) if v is not None}


def ankle_product():
    for pf, arc, length in itertools.product(PF, ARC, LENGTH):
        yield {**ANKLE, **{k: v for k, v in (("ankle_pf_mrc", pf), ("ankle_rom_deg", arc), ("leg_length_diff_cm", length)) if v is not None}}


# --- the regression ----------------------------------------------------------------------------------------------------


def test_the_whole_product_of_the_descriptors_with_every_set_of_impairments_agrees_with_the_current_engine(book):
    cases = [Case(f"d-{i}-{n}", "discrete", m, kinds) for i, kinds in enumerate([KINDS, ("visual",), ()]) for n, m in enumerate(discrete())]
    report = regress(book, cases)
    assert len(cases) == 3 * 5 * 5 * 4 * 6 and report.clean, format_report(report)


def test_each_of_the_four_impairments_alone_makes_the_group_applicable_like_the_engine(book):
    cases = [Case(f"s-{i}-{n}", "single", m, (kind,)) for n, m in enumerate(discrete()) for i, kind in enumerate(KINDS)]
    assert regress(book, cases).clean and len(cases) == 4 * 600


def test_the_ankle_level_by_every_combination_of_the_three_measures_around_their_limits_agrees_with_the_engine(book):
    cases = [Case(f"a-{i}", "ankle", m, KINDS) for i, m in enumerate(ankle_product())]
    report = regress(book, cases)
    assert len(cases) == 4 * 4 * 4 and report.clean, format_report(report)
    assert {"ankle_cme_met", "ankle_not_documented", "ankle_no_cme"} <= {book.evaluate(c.measures, set(c.impairments)).decision for c in cases}


def test_the_sampled_product_of_the_domains_with_the_ankle_grid_and_the_study_mode_sample_agree_with_the_engine(book):
    report = regress(book, domain_cases(book) + sample_cases(book, range(2)))
    assert report.clean and {"domain", "k2", "k2-no-leg_function", "k2-nothing"} <= set(report.total), format_report(report)


def test_every_branch_of_the_engine_is_reached_by_some_profile_so_none_is_left_out(book):
    cases = [m for m in discrete()] + list(ankle_product())
    reached = {book.evaluate(m, set(KINDS)).decision for m in cases}
    assert reached == {rule["id"] for rule in book.data["decision"]}  # fifteen rules for the thirteen branches of evaluate_seated (the arm has one row for each of its three functions)


def test_the_regression_detects_a_moved_limit_a_wrong_class_and_a_wrong_order(book):
    cases = [Case(f"a-{i}", "ankle", m, KINDS) for i, m in enumerate(ankle_product())] + [Case(f"d-{n}", "discrete", m, KINDS) for n, m in enumerate(discrete())]
    assert not regress(book, cases, overrides={"max_ankle_arc_deg": 11}).clean
    wrong = copy.deepcopy(book.data)
    next(r for r in wrong["decision"] if r["id"] == "hip_and_knee")["result"] = {"classes": {55: "meets"}, "rest": "not_met"}
    assert not regress(Rulebook(wrong), cases).clean
    wrong = copy.deepcopy(book.data)
    ids = [r["id"] for r in wrong["decision"]]
    i, j = ids.index("arm_shoulder_elbow"), ids.index("no_trunk")  # the trunk rule before the arm rows catches the arm deficits
    wrong["decision"][i], wrong["decision"][j] = wrong["decision"][j], wrong["decision"][i]
    assert not regress(Rulebook(wrong), cases).clean


# --- one named probe for each branch of the engine ------------------------------------------------------------------------


def test_the_posture_comes_first_and_another_posture_is_not_met_without_asking_for_anything(book):
    assert set(same(book, {"arm_function": 1}).values()) == {("insufficient_data", ("posture",))}
    for posture in ("standing", "prosthesis", "frame_runner"):
        assert set(same(book, {"posture": posture}).values()) == {("not_met", ())}


def test_the_arm_and_the_trunk_are_asked_for_in_that_order_and_only_the_missing_one(book):
    assert set(same(book, SEATED).values()) == {("insufficient_data", ("arm_function", "trunk_function"))}
    assert set(same(book, {**SEATED, "trunk_function": 1}).values()) == {("insufficient_data", ("arm_function",))}
    assert set(same(book, {**SEATED, "arm_function": 3}).values()) == {("insufficient_data", ("trunk_function",))}


def test_an_arm_deficit_without_trunk_function_is_one_class_each_and_with_trunk_function_needs_review(book):
    for arm, cls in ((0, 51), (1, 52), (2, 53)):
        row = same(book, {**SEATED, "arm_function": arm, "trunk_function": 0})
        assert {c: s for c, (s, _) in row.items()} == {c: ("meets" if c == cls else "not_met") for c in book.classes}
        for trunk in (1, 2):
            assert set(same(book, {**SEATED, "arm_function": arm, "trunk_function": trunk}).values()) == {("needs_review", ())}


def test_preserved_arms_and_no_trunk_is_class_54_and_the_legs_are_not_asked_for(book):
    row = same(book, {**SEATED, "arm_function": 3, "trunk_function": 0})
    assert row[54] == ("meets", ()) and {m for _, m in row.values()} == {()}


def test_the_legs_are_asked_for_when_the_arms_are_preserved_and_there_is_trunk_function(book):
    for trunk in (1, 2):
        assert set(same(book, {**SEATED, "arm_function": 3, "trunk_function": trunk}).values()) == {("insufficient_data", ("leg_function",))}


def test_the_legs_give_class_55_56_or_nothing_when_they_are_normal(book):
    for leg, cls in ((0, 55), (1, 55), (2, 56)):
        row = same(book, {**SEATED, **LEGS, "leg_function": leg})
        assert [c for c, (s, _) in row.items() if s == "meets"] == [cls]
    assert set(same(book, {**SEATED, **LEGS, "leg_function": 4}).values()) == {("not_met", ())}


def test_the_ankle_level_is_class_57_by_one_criterion_with_each_limit_included(book):
    for measure, met, not_met in (("ankle_pf_mrc", 2, 3), ("ankle_rom_deg", 10, 10.01), ("leg_length_diff_cm", 7, 6.99)):
        assert same(book, {**ANKLE, measure: met})[57] == ("meets", ())
        assert same(book, {**ANKLE, measure: not_met})[57] == ("borderline", ())  # measured, and no criterion is met


def test_the_ankle_level_with_no_measure_at_all_is_class_57_and_the_measures_are_not_asked_for(book):
    row = same(book, ANKLE)
    assert row[57] == ("meets", ()) and {m for _, m in row.values()} == {()}


# --- what the engine does that looks odd, reproduced and not corrected ---------------------------------------------------------


def test_an_ankle_level_with_no_measure_documented_is_met_not_borderline_and_nothing_is_asked_for(book):
    # the lack of evidence counts as a class 57 ("ankle CME not documented"); a measure that fails turns it into a borderline
    assert same(book, ANKLE)[57][0] == "meets" and same(book, {**ANKLE, "ankle_rom_deg": 30})[57][0] == "borderline"


def test_partial_and_full_trunk_function_are_not_told_apart_and_none_and_hip_flexors_only_are_one_class(book):
    assert same(book, {**SEATED, **LEGS, "trunk_function": 1, "leg_function": 2}) == same(book, {**SEATED, **LEGS, "leg_function": 2})
    assert same(book, {**SEATED, **LEGS, "leg_function": 0}) == same(book, {**SEATED, **LEGS, "leg_function": 1})


def test_the_four_impairments_are_not_told_apart_so_an_amputation_and_a_strength_deficit_give_the_same_verdict(book):
    probe = {**SEATED, **LEGS, "leg_function": 2}
    assert len({tuple(same(book, probe, (kind,)).items()) for kind in KINDS}) == 1


def test_the_amputation_levels_of_the_limb_groups_are_not_read_so_a_seated_athlete_is_judged_by_function_only(book):
    with_levels = {**SEATED, **LEGS, "leg_function": 2, "lower_left": 3, "lower_right": 3}
    assert rows(book, with_levels)[1] == same(book, {**SEATED, **LEGS, "leg_function": 2})  # item 18 of the coverage: no fields of its own


# --- the same impairments as limb_standing, and the parameters borrowed from it ---------------------------------------------------


def test_the_group_and_limb_standing_both_judge_the_same_profile_each_by_its_own_posture():
    wheel, standing = Rulebook.load("wheelchair"), Rulebook.load("limb_standing")
    assert set(wheel.data["applies_to"]) == set(standing.data["applies_to"])
    measures = {"posture": "seated", "arm_function": 3, "trunk_function": 2, "leg_function": 2, "lower_left": 3, "lower_right": 0, "upper_left": 0, "upper_right": 0}
    seated_row = same(wheel, measures, ("limb_deficiency",))
    assert seated_row[56] == ("meets", ()) and set(same(standing, measures, ("limb_deficiency",)).values()) == {("not_met", ())}
    measures["posture"] = "standing"
    assert set(same(wheel, measures, ("limb_deficiency",)).values()) == {("not_met", ())} and same(standing, measures, ("limb_deficiency",))[42] == ("meets", ())


def test_the_three_limits_of_the_ankle_are_borrowed_from_limb_standing_not_copied(book):
    standing = Rulebook.load("limb_standing")
    on = dt.date(2024, 10, 1)
    raw = yaml.safe_load((DATA / "groups" / "wheelchair.yaml").read_text(encoding="utf-8"))["parameters"]
    for name in ("max_plantar_flexion_mrc", "max_ankle_arc_deg", "min_leg_length_diff_cm"):
        assert raw[name] == {"same_as": "limb_standing"}  # no value, no source: they are the ones of the other file
        assert book.data["parameters"][name] == standing.data["parameters"][name] and book.value(name, on) == standing.value(name, on)
        assert book.data["parameters"][name]["status"] == "provisional"
    assert [book.value(n, on) for n in ("max_plantar_flexion_mrc", "max_ankle_arc_deg", "min_leg_length_diff_cm")] == [2, 10, 7]


def test_one_override_by_name_changes_both_groups_because_the_parameter_is_the_same(book):
    standing = Rulebook.load("limb_standing")
    wheel_input = {**ANKLE, "ankle_rom_deg": 11}
    standing_input = {"posture": "standing", "ankle_rom_deg": 11, "lower_limb_sides_affected": 1}
    assert book.evaluate(wheel_input, {"rom"}).verdicts[57].status == "borderline"
    assert book.evaluate(wheel_input, {"rom"}, overrides={"max_ankle_arc_deg": 12}).verdicts[57].status == "meets"
    assert standing.evaluate(standing_input, {"rom"}).verdicts[44].status == "not_met"
    assert standing.evaluate(standing_input, {"rom"}, overrides={"max_ankle_arc_deg": 12}).verdicts[44].status == "meets"


def test_a_borrowed_parameter_that_the_other_group_does_not_have_is_an_error():
    data = yaml.safe_load((DATA / "groups" / "wheelchair.yaml").read_text(encoding="utf-8"))
    data["parameters"]["no_such_limit"] = {"same_as": "limb_standing"}
    with pytest.raises(RulebookError, match="no such parameter"):
        Rulebook(data)


# --- the numbers and the status -------------------------------------------------------------------------------------------


def test_everything_in_the_group_is_provisional_with_a_note_because_the_engine_calls_it_its_own_reading(book):
    for kind in ("parameters", "flags", "criteria"):
        for name, spec in book.data[kind].items():
            assert spec["status"] == "provisional" and (spec["source"].get("note") or spec["source"].get("page")), (kind, name)
    rows_with_equals = [r for r in book.data["decision"] if "equals" in r.get("when", {})]
    assert rows_with_equals and all(r["status"] == "provisional" and r["source"].get("note") for r in rows_with_equals)
    assert not any(spec["status"] == "implemented" for kind in ("parameters", "flags", "criteria") for spec in book.data[kind].values())


def test_the_pages_of_the_rows_are_the_pages_of_the_classes_in_the_catalog_and_the_classes_are_the_catalogs(book):
    catalog = load_catalog()
    assert book.classes == sorted(c.class_id for c in catalog.group_classes("wheelchair"))
    assert not any(catalog.classes[c].criteria for c in book.classes)
    assert set(book.data["applies_to"]) == {i.value for i in catalog.groups["wheelchair"].impairments}
    for rule in book.data["decision"]:
        if "equals" in rule.get("when", {}) and "classes" in rule["result"]:
            cls = next(c for c, s in rule["result"]["classes"].items() if s == "meets")
            assert rule["source"]["page"] == catalog.classes[cls].source_page, rule["id"]
    assert {p.value for c in book.classes for p in catalog.classes[c].postures} == {"seated"}
