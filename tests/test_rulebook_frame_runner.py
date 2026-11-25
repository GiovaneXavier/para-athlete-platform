"""The rule book of the frame running group, the Petra (classes 71 and 72, step 5a): a provisional group reproduced as it is.

Every probe is compared with the current engine, which stays the default. Nothing is corrected: the behaviours that look
odd are tested as the engine gives them.
"""
import copy
import itertools

import pytest

from para_triage.rulebook import Rulebook
from para_triage.rulebook.compare import Case, book_row, domain_cases, engine_row, format_report, profile_of, regress, sample_cases
from para_triage.rules import RuleEngine
from para_triage.rules.catalog import load_catalog

ENGINE = RuleEngine()
TYPES = ("hypertonia", "ataxia", "athetosis")
BASE = {"posture": "frame_runner", "brain_impairment_report": True, "neuro_severity": 2}


@pytest.fixture(scope="module")
def book():
    return Rulebook.load("frame_runner")


def rows(book, measures, impairments=TYPES):
    case = Case("probe", "probe", measures, tuple(impairments))
    return engine_row(ENGINE, profile_of(case, book), book.classes), book_row(book, case)


def same(book, measures, impairments=TYPES):
    engine, got = rows(book, measures, impairments)
    assert engine == got, (measures, engine, got)
    return got


# --- the regression ----------------------------------------------------------------------------------------------------


def test_the_whole_product_of_the_domains_with_every_set_of_impairments_agrees_with_the_current_engine(book):
    cases = domain_cases(book, every_impairment_set=True)
    report = regress(book, cases)
    assert len(cases) == 4 * 5 * 3 * 5 * 3 * 3 * 3 and report.clean, format_report(report)


def test_any_one_of_the_three_types_alone_makes_the_group_applicable_like_the_engine(book):
    cases = [Case(f"t-{i}-{n}", "type", c.measures, (kind,)) for n, c in enumerate(domain_cases(book)) for i, kind in enumerate(TYPES)]
    assert regress(book, cases).clean and len(cases) == 3 * 2025


def test_the_study_mode_sample_with_each_measure_hidden_agrees_with_the_current_engine(book):
    cases = sample_cases(book, range(2))
    report = regress(book, cases)
    assert len(cases) > 1000 and report.clean and {"k2-no-posture", "k2-no-neuro_severity", "k2-nothing"} <= set(report.total), format_report(report)


def test_every_branch_of_the_engine_is_reached_by_some_profile_so_none_is_left_out(book):
    reached = {book.evaluate(c.measures, set(c.impairments)).decision for c in domain_cases(book)}
    assert reached == {rule["id"] for rule in book.data["decision"]}  # eleven rules, eleven branches of evaluate_frame_runner


def test_the_regression_detects_a_moved_severity_a_wrong_walk_rule_and_a_wrong_order(book):
    cases = domain_cases(book)
    assert not regress(book, cases, overrides={"min_severity": 3}).clean
    wrong = copy.deepcopy(book.data)
    wrong["decision"][7]["result"] = {"classes": {71: "meets"}, "rest": "not_met"}
    assert not regress(Rulebook(wrong), cases).clean
    wrong = copy.deepcopy(book.data)
    wrong["decision"][2], wrong["decision"][4] = wrong["decision"][4], wrong["decision"][2]  # the severity before the neurological report
    assert not regress(Rulebook(wrong), cases).clean


# --- one named probe for each branch of the engine ------------------------------------------------------------------------


def test_the_posture_comes_first_and_is_the_only_thing_asked_for_when_it_is_missing(book):
    assert set(same(book, {"brain_impairment_report": True}).values()) == {("insufficient_data", ("posture",))}


def test_another_posture_is_not_met_and_asks_for_nothing_even_with_everything_else_missing(book):
    for posture in ("standing", "seated", "prosthesis"):
        assert set(same(book, {"posture": posture}).values()) == {("not_met", ())}


def test_the_neurological_report_is_asked_for_and_without_it_the_group_is_not_met(book):
    assert set(same(book, {"posture": "frame_runner"}).values()) == {("insufficient_data", ("brain_impairment_report",))}
    assert set(same(book, {"posture": "frame_runner", "brain_impairment_report": False}).values()) == {("not_met", ())}


def test_the_severity_is_asked_for_and_below_moderate_is_not_met(book):
    given = {"posture": "frame_runner", "brain_impairment_report": True}
    assert set(same(book, given).values()) == {("insufficient_data", ("neuro_severity",))}
    for severity in (0, 1):
        assert set(same(book, {**given, "neuro_severity": severity}).values()) == {("not_met", ())}


def test_the_transfer_is_asked_for_once_the_severity_is_moderate_or_severe(book):
    for severity in (2, 3):
        assert set(same(book, {**BASE, "neuro_severity": severity}).values()) == {("insufficient_data", ("transfers_independently",))}


def test_not_transferring_alone_is_class_71_and_transferring_alone_is_class_72(book):
    assert same(book, {**BASE, "transfers_independently": False}) == {71: ("meets", ()), 72: ("not_met", ())}
    assert same(book, {**BASE, "transfers_independently": True}) == {71: ("not_met", ()), 72: ("meets", ())}


def test_a_contradiction_makes_both_classes_borderline_and_asks_for_nothing(book):
    walks = same(book, {**BASE, "transfers_independently": False, "walks_short_distances": True})
    straps = same(book, {**BASE, "transfers_independently": True, "trunk_straps_needed": True})
    assert walks == straps == {71: ("borderline", ()), 72: ("borderline", ())}


# --- what the engine does that looks odd, reproduced and not corrected ---------------------------------------------------------


def test_an_answer_not_given_about_walking_or_straps_is_read_as_no_and_is_not_asked_for(book):
    # walks_short_distances and trunk_straps_needed are never listed as missing: a missing one is the same as false.
    assert same(book, {**BASE, "transfers_independently": False}) == same(book, {**BASE, "transfers_independently": False, "walks_short_distances": False})
    assert same(book, {**BASE, "transfers_independently": True}) == same(book, {**BASE, "transfers_independently": True, "trunk_straps_needed": False})


def test_severe_is_read_like_moderate_and_the_straps_are_ignored_when_the_athlete_does_not_transfer_alone(book):
    assert same(book, {**BASE, "neuro_severity": 3, "transfers_independently": True}) == same(book, {**BASE, "transfers_independently": True})
    assert same(book, {**BASE, "transfers_independently": False, "trunk_straps_needed": True}) == {71: ("meets", ()), 72: ("not_met", ())}


def test_the_three_types_of_impairment_are_not_told_apart(book):
    results = {tuple(same(book, {**BASE, "transfers_independently": True}, (kind,)).items()) for kind in TYPES}
    assert len(results) == 1


# --- the numbers and the status -------------------------------------------------------------------------------------------


def test_everything_in_the_group_is_provisional_with_a_note_because_the_engine_calls_it_its_own_reading(book):
    for kind in ("parameters", "flags"):
        for name, spec in book.data[kind].items():
            assert spec["status"] == "provisional" and spec["source"].get("note"), (kind, name)
    assert not any(spec["status"] == "implemented" for kind in ("parameters", "flags") for spec in book.data[kind].values())


def test_the_classes_and_the_impairments_are_the_ones_of_the_catalog_and_the_group_has_no_numeric_criteria_to_copy(book):
    catalog = load_catalog()
    assert book.classes == sorted(c.class_id for c in catalog.group_classes("frame_runner"))
    assert not any(catalog.classes[c].criteria for c in book.classes)
    assert set(book.data["applies_to"]) == {i.value for i in catalog.groups["frame_runner"].impairments}
    assert {p.value for p in catalog.classes[71].postures} == {"frame_runner"} == {p.value for p in catalog.classes[72].postures}  # the posture of the gate
