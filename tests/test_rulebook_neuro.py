"""The rule book of the brain impairment group (classes 31-38, step 5c): a provisional group reproduced as it is.

Two postures that decide different classes, an ordinal severity, the distribution of the paralysis and the SET of impairments
the athlete declares. Every probe is compared with the current engine, which stays the default. Nothing is corrected.
"""
import copy

import pytest

from para_triage.rulebook import Rulebook
from para_triage.rulebook.compare import Case, book_row, domain_cases, engine_row, format_report, profile_of, regress, sample_cases
from para_triage.rules import RuleEngine
from para_triage.rules.catalog import load_catalog

ENGINE = RuleEngine()
SEATED, STANDING = [31, 32, 33, 34], [35, 36, 37, 38]
H, A, T = "hypertonia", "ataxia", "athetosis"
SETS = [(H,), (A,), (T,), (H, A), (H, T), (A, T), (H, A, T)]
BASE = {"brain_impairment_report": True}
SEAT = {**BASE, "posture": "seated"}
STAND = {**BASE, "posture": "standing"}


@pytest.fixture(scope="module")
def book():
    return Rulebook.load("neuro")


def rows(book, measures, impairments=(H,)):
    case = Case("probe", "probe", measures, tuple(impairments))
    return engine_row(ENGINE, profile_of(case, book), book.classes), book_row(book, case)


def same(book, measures, impairments=(H,)):
    engine, got = rows(book, measures, impairments)
    assert engine == got, (measures, impairments, engine, got)
    return got


def statuses(row, classes=None):
    return {c: s for c, (s, _) in row.items() if classes is None or c in classes}


# --- the regression ----------------------------------------------------------------------------------------------------


def test_the_whole_product_with_every_combination_of_the_three_types_and_with_other_impairments_agrees_with_the_engine(book):
    cases = domain_cases(book, every_impairment_set=True)
    report = regress(book, cases)
    assert len(cases) == 13 * 5 * 3 * 5 * 5 * 5 and report.clean, format_report(report)  # ten sets of types, three others, each descriptor also missing


def test_the_study_mode_samples_of_both_postures_with_each_measure_hidden_agree_with_the_engine(book):
    cases = sample_cases(book, range(2))
    report = regress(book, cases)
    assert len(cases) > 1500 and report.clean and {"k2-no-chair_propulsion", "k2-no-cp_distribution", "k2-no-posture", "k2-nothing"} <= set(report.total), format_report(report)
    assert {c.measures.get("posture") for c in cases} >= {"seated", "standing"}


def test_every_branch_of_the_engine_is_reached_by_some_profile_so_none_is_left_out(book):
    reached = {book.evaluate(c.measures, set(c.impairments)).decision for c in domain_cases(book)}
    assert reached == {rule["id"] for rule in book.data["decision"]}  # twenty-six rules for the branches of evaluate_neuro


def test_the_regression_detects_a_wrong_class_a_wrong_scope_and_a_wrong_order(book):
    cases = domain_cases(book)[::3]  # a third of the product is enough to see each mistake
    wrong = copy.deepcopy(book.data)
    next(r for r in wrong["decision"] if r["id"] == "standing_hemiplegia")["result"] = {"classes": {35: "meets"}, "rest": "not_met"}
    assert not regress(Rulebook(wrong), cases).clean
    wrong = copy.deepcopy(book.data)
    next(r for r in wrong["decision"] if r["id"] == "seated_propulsion_missing").pop("scope")  # the standing classes would ask for the propulsion too
    assert not regress(Rulebook(wrong), cases).clean
    wrong = copy.deepcopy(book.data)
    ids = [r["id"] for r in wrong["decision"]]
    i, j = ids.index("standing_mild"), ids.index("standing_mild_diplegia")
    wrong["decision"][i], wrong["decision"][j] = wrong["decision"][j], wrong["decision"][i]  # the mild diplegia would never be borderline
    assert not regress(Rulebook(wrong), cases).clean


# --- the gate and the two postures -----------------------------------------------------------------------------------------


def test_the_posture_comes_first_and_another_posture_is_not_met_without_asking_for_anything(book):
    assert set(same(book, {"brain_impairment_report": True}).values()) == {("insufficient_data", ("posture",))}
    for posture in ("prosthesis", "frame_runner"):
        assert set(same(book, {"posture": posture}).values()) == {("not_met", ())}


def test_the_neurological_report_is_asked_for_in_both_postures_and_without_it_nothing_is_met(book):
    for posture in ("seated", "standing"):
        assert set(same(book, {"posture": posture}).values()) == {("insufficient_data", ("brain_impairment_report",))}
        assert set(same(book, {"posture": posture, "brain_impairment_report": False}).values()) == {("not_met", ())}


# --- seated, classes 31 to 34 ------------------------------------------------------------------------------------------------


def test_the_propulsion_is_asked_for_only_by_the_seated_classes_and_the_standing_ones_ask_for_nothing(book):
    row = same(book, SEAT)
    assert {c: m for c, (_, m) in row.items()} == {**dict.fromkeys(SEATED, ("chair_propulsion",)), **dict.fromkeys(STANDING, ())}
    assert statuses(row) == {**dict.fromkeys(SEATED, "insufficient_data"), **dict.fromkeys(STANDING, "not_met")}


def test_seated_no_impact_is_not_met_and_mild_needs_review_in_the_seated_classes_only(book):
    none = same(book, {**SEAT, "chair_propulsion": 1, "neuro_severity": 0})
    mild = same(book, {**SEAT, "chair_propulsion": 1, "neuro_severity": 1})
    assert set(none.values()) == {("not_met", ())}
    assert statuses(mild) == {**dict.fromkeys(SEATED, "needs_review"), **dict.fromkeys(STANDING, "not_met")}


def test_the_propulsion_gives_class_31_32_or_33_whatever_the_type_of_impairment(book):
    for prop, cls in ((1, 31), (2, 32), (3, 33)):
        for types in SETS:
            row = same(book, {**SEAT, "chair_propulsion": prop, "neuro_severity": 2}, types)
            assert [c for c, s in statuses(row).items() if s == "meets"] == [cls], (prop, types)


def test_symmetric_propulsion_is_class_34_only_for_hypertonia_alone_with_diplegia(book):
    given = {**SEAT, "chair_propulsion": 4, "neuro_severity": 2}
    assert statuses(same(book, {**given, "cp_distribution": "diplegia"}, (H,)))[34] == "meets"
    for types in ((H, A), (H, T), (A,), (T,), (H, A, T)):
        assert statuses(same(book, {**given, "cp_distribution": "diplegia"}, types), SEATED) == {31: "not_met", 32: "not_met", 33: "borderline", 34: "not_met"}


def test_symmetric_propulsion_with_hypertonia_asks_for_the_distribution_in_every_seated_class_and_otherwise_is_borderline(book):
    given = {**SEAT, "chair_propulsion": 4, "neuro_severity": 2}
    unknown = same(book, given, (H,))
    assert {unknown[c] for c in SEATED[:3]} == {("not_met", ("cp_distribution",))} and unknown[34] == ("borderline", ("cp_distribution",))
    assert {unknown[c] for c in STANDING} == {("not_met", ())}  # the standing classes do not ask
    for dist in ("hemiplegia", "quadriplegia", "triplegia"):
        assert statuses(same(book, {**given, "cp_distribution": dist}, (H,)), SEATED) == {31: "not_met", 32: "not_met", 33: "borderline", 34: "borderline"}


# --- standing, classes 35 to 38 ----------------------------------------------------------------------------------------------


def test_the_severity_is_asked_for_only_by_the_standing_classes(book):
    row = same(book, STAND)
    assert {c: m for c, (_, m) in row.items()} == {**dict.fromkeys(SEATED, ()), **dict.fromkeys(STANDING, ("neuro_severity",))}
    assert statuses(row) == {**dict.fromkeys(SEATED, "not_met"), **dict.fromkeys(STANDING, "insufficient_data")}


def test_standing_none_is_not_met_and_severe_needs_review_before_looking_at_the_types(book):
    assert set(same(book, {**STAND, "neuro_severity": 0}).values()) == {("not_met", ())}
    for types in SETS:
        assert set(statuses(same(book, {**STAND, "neuro_severity": 3}, types), STANDING).values()) == {"needs_review"}


def test_standing_mild_is_class_38_and_hypertonia_alone_with_diplegia_is_borderline_35_and_38(book):
    assert statuses(same(book, {**STAND, "neuro_severity": 1}, (A,)), STANDING) == {35: "not_met", 36: "not_met", 37: "not_met", 38: "meets"}
    diplegia = {**STAND, "neuro_severity": 1, "cp_distribution": "diplegia"}
    assert statuses(same(book, diplegia, (H,)), STANDING) == {35: "borderline", 36: "not_met", 37: "not_met", 38: "borderline"}
    assert statuses(same(book, diplegia, (H, A)), STANDING)[38] == "meets"  # mixed types with diplegia: no borderline


def test_standing_moderate_without_hypertonia_is_class_36_and_does_not_ask_for_the_distribution(book):
    row = same(book, {**STAND, "neuro_severity": 2}, (A, T))
    assert statuses(row, STANDING)[36] == "meets" and {m for _, m in row.values()} == {()}


def test_standing_moderate_hypertonia_asks_for_the_distribution_and_then_gives_35_or_37(book):
    given = {**STAND, "neuro_severity": 2}
    assert {v for c, v in same(book, given).items() if c in STANDING} == {("insufficient_data", ("cp_distribution",))}
    assert statuses(same(book, {**given, "cp_distribution": "diplegia"}), STANDING)[35] == "meets"
    assert statuses(same(book, {**given, "cp_distribution": "hemiplegia"}), STANDING)[37] == "meets"
    for dist in ("quadriplegia", "triplegia"):
        assert set(statuses(same(book, {**given, "cp_distribution": dist}), STANDING).values()) == {"needs_review"}


def test_standing_moderate_hypertonia_mixed_with_ataxia_or_athetosis_is_borderline_with_class_36(book):
    for mix in ((H, A), (H, T), (H, A, T)):
        diplegia = statuses(same(book, {**STAND, "neuro_severity": 2, "cp_distribution": "diplegia"}, mix), STANDING)
        hemiplegia = statuses(same(book, {**STAND, "neuro_severity": 2, "cp_distribution": "hemiplegia"}, mix), STANDING)
        assert diplegia == {35: "borderline", 36: "borderline", 37: "not_met", 38: "not_met"}
        assert hemiplegia == {35: "not_met", 36: "borderline", 37: "borderline", 38: "not_met"}


# --- the set of impairments --------------------------------------------------------------------------------------------------


def test_only_the_three_types_count_so_another_impairment_next_to_them_changes_nothing(book):
    probe = {**STAND, "neuro_severity": 2, "cp_distribution": "diplegia"}
    assert same(book, probe, (H, "visual")) == same(book, probe, (H,))
    assert same(book, probe, (A, "visual", "intellectual")) == same(book, probe, (A,))
    assert set(same(book, probe, ("visual",)).values()) == {("not_applicable", ())}


def test_every_non_empty_combination_of_the_three_types_is_a_distinct_input_of_the_group(book):
    probe = {**SEAT, "chair_propulsion": 4, "neuro_severity": 2, "cp_distribution": "diplegia"}
    answers = {types: tuple(statuses(same(book, probe, types), SEATED).items()) for types in SETS}
    assert answers[(H,)] != answers[(H, A)] and answers[(H, A)] == answers[(A,)]  # hypertonia alone is the only one that gives class 34


# --- what the engine does that looks odd, reproduced and not corrected -----------------------------------------------------------


def test_a_severity_not_provided_in_a_seated_athlete_is_read_as_moderate_or_more_and_is_not_asked_for(book):
    row = same(book, {**SEAT, "chair_propulsion": 1})
    assert row[31] == ("meets", ()) and {m for _, m in row.values()} == {()}


def test_the_propulsion_is_asked_for_before_the_severity_is_looked_at(book):
    assert statuses(same(book, {**SEAT, "neuro_severity": 0}), SEATED) == dict.fromkeys(SEATED, "insufficient_data")
    assert set(statuses(same(book, {**SEAT, "chair_propulsion": 1, "neuro_severity": 0}), SEATED).values()) == {"not_met"}


def test_symmetric_propulsion_with_athetosis_alone_is_borderline_33_and_the_type_is_only_read_never_asked_for(book):
    given = {**SEAT, "chair_propulsion": 4, "neuro_severity": 2}
    assert statuses(same(book, given, (T,)), SEATED)[33] == "borderline"  # the type is only ever read, never asked for


def test_a_quadriplegia_or_triplegia_standing_needs_review_even_when_mixed_with_other_types(book):
    probe = {**STAND, "neuro_severity": 2, "cp_distribution": "quadriplegia"}
    assert set(statuses(same(book, probe, (H, A)), STANDING).values()) == {"needs_review"}


# --- the numbers and the status -------------------------------------------------------------------------------------------


def test_everything_in_the_group_is_provisional_with_a_note_because_the_engine_calls_it_its_own_reading(book):
    for kind in ("parameters", "flags"):
        for name, spec in book.data[kind].items():
            assert spec["status"] == "provisional" and spec["source"].get("note"), (kind, name)


def test_the_classes_the_postures_and_the_impairments_are_the_ones_of_the_catalog_and_the_two_groups_of_classes_are_the_postures(book):
    catalog = load_catalog()
    assert book.classes == sorted(c.class_id for c in catalog.group_classes("neuro"))
    assert not any(catalog.classes[c].criteria for c in book.classes)
    assert set(book.data["applies_to"]) == {i.value for i in catalog.groups["neuro"].impairments}
    for name, postures in (("seated", "seated"), ("standing", "standing")):
        classes = book.data["class_groups"][name]["classes"]
        assert {p.value for c in classes for p in catalog.classes[c].postures} == {postures}
    assert sorted(book.data["class_groups"]["seated"]["classes"] + book.data["class_groups"]["standing"]["classes"]) == book.classes


def test_the_neurological_report_rules_are_the_same_as_the_ones_of_the_frame_runner_on_purpose(book):
    petra = Rulebook.load("frame_runner")
    for rule_id in ("brain_report_missing", "no_brain_report"):
        a = next(r for r in book.data["decision"] if r["id"] == rule_id)
        b = next(r for r in petra.data["decision"] if r["id"] == rule_id)
        assert a == b, rule_id  # the format has no reuse across files: the duplicate is kept equal by this test
    assert book.data["flags"]["no_brain_report"]["test"] == petra.data["flags"]["no_brain_report"]["test"]
    assert book.data["flags"]["no_brain_report"]["reason"] == petra.data["flags"]["no_brain_report"]["reason"]
