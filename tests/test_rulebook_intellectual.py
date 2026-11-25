"""The rule book of the intellectual impairment group (class 20, step 4): the age of onset as a parameter, and two variants.

The current engine knows the onset only as a boolean (`onset_before_22`). The regression translates it with the adapter of
compare.py, which cannot represent the ages between 18 and 21 or the boundary: these are tested by hand, below.
"""
import copy
import datetime as dt

import pytest

from para_triage.rulebook import Rulebook
from para_triage.rulebook.__main__ import main
from para_triage.rulebook.compare import (
    ENGINE_NAME,
    Case,
    book_row,
    diff_variants,
    domain_cases,
    engine_row,
    format_report,
    profile_of,
    regress,
    sample_cases,
)
from para_triage.rulebook.engine import onset_age, onset_flag
from para_triage.rulebook.interpreter import load_variant, sources
from para_triage.rules import RuleEngine
from para_triage.rules.catalog import load_catalog

ENGINE = RuleEngine()
GROUP = ("intellectual",)


@pytest.fixture(scope="module")
def book():
    return Rulebook.load("intellectual")


def status(book, age, variant="cpb-2024", **extra):
    given = {"iq": 70, "adaptive_limitation": True, **({} if age is None else {"onset_age": age}), **extra}
    verdict = book.evaluate(given, set(GROUP), variant=variant).verdicts[20]
    return verdict.status, verdict.missing


# --- the regression against the current engine ----------------------------------------------------------------------------


def test_the_whole_product_of_the_domains_with_every_set_of_impairments_agrees_with_the_current_engine(book):
    cases = domain_cases(book, every_impairment_set=True)
    report = regress(book, cases)
    assert len(cases) == 4 * 6 * 3 * 3 and report.clean, format_report(report)  # IQ, adaptive limitation and onset, each also missing


def test_the_study_mode_sample_with_each_measure_hidden_agrees_with_the_current_engine(book):
    cases = sample_cases(book, range(3))
    report = regress(book, cases)
    assert len(cases) > 1000 and report.clean and {"k2-no-iq", "k2-no-adaptive_limitation", "k2-no-onset_age", "k2-nothing"} <= set(report.total), format_report(report)


def test_every_state_the_group_can_give_is_given_by_some_profile(book):
    seen = {v.status for case in domain_cases(book, True) for v in book.evaluate(case.measures, set(case.impairments)).verdicts.values()}
    assert seen == {"meets", "not_met", "insufficient_data", "not_applicable"}  # no borderline, review or not_implemented in this group


def test_the_regression_detects_a_wrong_limit_and_a_wrong_decision_order(book):
    cases = domain_cases(book)
    assert not regress(book, cases, overrides={"iq_max": 74}).clean
    wrong = copy.deepcopy(book.data)
    wrong["decision"][0], wrong["decision"][3] = wrong["decision"][3], wrong["decision"][0]  # asking for what is missing before looking at a failed criterion
    assert not regress(Rulebook(wrong), cases).clean


def test_the_probes_of_the_engine_a_failed_criterion_wins_over_a_missing_one_and_the_missing_fields_keep_the_engine_order(book):
    def both(measures):
        case = Case("p", "p", measures, GROUP)
        engine, got = engine_row(ENGINE, profile_of(case, book), book.classes), book_row(book, case)
        assert engine == got
        return got[20]

    assert both({"iq": 90}) == ("not_met", ())  # IQ above the limit: nothing is asked for although two measures are missing
    assert both({"adaptive_limitation": False}) == ("not_met", ())
    assert both({"onset_age": 22}) == ("not_met", ())
    assert both({"iq": 70, "adaptive_limitation": True}) == ("insufficient_data", ("onset_before_22",))  # the name the engine knows
    assert both({}) == ("insufficient_data", ("iq", "adaptive_limitation", "onset_before_22"))
    assert both({"iq": 75, "adaptive_limitation": True, "onset_age": 21}) == ("meets", ())


# --- the adapter ------------------------------------------------------------------------------------------------------------


def test_the_adapter_turns_the_flag_into_a_representative_age_and_back(book):
    assert (onset_age(True), onset_age(False), onset_age(None)) == (21, 22, None)
    assert (onset_flag(21), onset_flag(22), onset_flag(None)) == (True, False, None)
    assert [onset_flag(a) for a in (17, 18, 19, 21, 22, 23)] == [True, True, True, True, False, False]  # the engine's reading of "before 22"
    assert ENGINE_NAME == {"onset_age": "onset_before_22"}
    profile = profile_of(Case("p", "p", {"iq": 70, "onset_age": 19}, GROUP), book)
    assert profile.onset_before_22 is True and not hasattr(profile, "onset_age")


# --- the ages the regression cannot prove: written by hand, in both variants ------------------------------------------------


def test_the_ages_in_the_cpb_variant_before_22_count_and_22_does_not(book):
    expected = {17: "meets", 18: "meets", 19: "meets", 21: "meets", 22: "not_met", 23: "not_met"}
    assert {age: status(book, age)[0] for age in expected} == expected
    assert status(book, None) == ("insufficient_data", ("onset_age",))


def test_the_ages_in_the_wpa_variant_before_18_count_and_18_does_not(book):
    expected = {17: "meets", 18: "not_met", 19: "not_met", 21: "not_met", 22: "not_met", 23: "not_met"}
    assert {age: status(book, age, "wpa-2023")[0] for age in expected} == expected
    assert status(book, None, "wpa-2023") == ("insufficient_data", ("onset_age",))
    assert status(book, 17, "wpa-2023", iq=90) == ("not_met", ())  # the IQ criterion is the same in both variants


def test_the_boundary_is_a_parameter_if_the_age_itself_counted_22_would_meet_and_so_would_18_in_the_wpa_variant(book):
    included = {"onset_limit_is_late": False}
    assert book.evaluate({"iq": 70, "adaptive_limitation": True, "onset_age": 22}, set(GROUP), overrides=included).verdicts[20].status == "meets"
    assert book.evaluate({"iq": 70, "adaptive_limitation": True, "onset_age": 23}, set(GROUP), overrides=included).verdicts[20].status == "not_met"
    assert book.evaluate({"iq": 70, "adaptive_limitation": True, "onset_age": 18}, set(GROUP), variant="wpa-2023", overrides=included).verdicts[20].status == "meets"


def test_the_trace_says_which_limit_the_age_was_compared_with(book):
    steps = {s.criterion: s for s in book.evaluate({"iq": 70, "adaptive_limitation": True, "onset_age": 19}, set(GROUP), variant="wpa-2023").trace}
    assert steps["onset_too_late"].reference == {"onset_age_limit": 18, "onset_limit_is_late": True} and steps["onset_too_late"].result == "met"
    assert steps["onset_too_late"].source == {"doc": "cpb-booklet-2024", "page": 16}


# --- the variant -----------------------------------------------------------------------------------------------------------


def test_the_wpa_variant_changes_only_the_age_limit_and_cites_its_document_as_provisional():
    variant = load_variant("wpa-2023")
    assert variant["overrides"] == {"onset_age_limit": 18} and variant["status"] == "provisional"
    assert variant["source"] in sources() and variant["reference_date"] == load_variant("cpb-2024")["reference_date"]
    assert "Virtus" in sources()["wpa-2023"]["note"] and sources()["wpa-2023"]["date"] == dt.date(2023, 2, 17)


def test_the_parameters_of_the_age_are_provisional_and_the_iq_limit_is_the_one_of_the_catalog(book):
    on = dt.date(2024, 10, 1)
    catalog = load_catalog().classes[20].criteria
    assert book.value("iq_max", on) == catalog["iq_max"] and book.value("onset_age_limit", on) == catalog["onset_before_age"] == 22
    for name in ("onset_age_limit", "onset_limit_is_late"):
        assert book.data["parameters"][name]["status"] == "provisional"
    assert "not confirmed" in book.data["parameters"]["onset_limit_is_late"]["source"]["note"]
    assert set(book.data["applies_to"]) == {i.value for i in load_catalog().groups["intellectual"].impairments}


def test_the_variant_diff_changes_only_by_the_age_the_whole_product_has_eight_profiles_that_change(book):
    diff = diff_variants(book, domain_cases(book), "cpb-2024", "wpa-2023")
    assert diff.changed == 8 and set(diff.transitions) == {(20, "meets", "not_met"), (20, "insufficient_data", "not_met")}
    assert diff.transitions[(20, "meets", "not_met")] == 3 and diff.transitions[(20, "insufficient_data", "not_met")] == 5
    assert diff.examples and all(measures.get("onset_age") == 21 for measures, _, _ in diff.examples)  # only the age can be the reason


def test_on_complete_profiles_of_the_sample_every_change_is_a_meets_that_stops_and_the_number_depends_on_the_age_assumed(book):
    complete = [c for c in sample_cases(book, range(3)) if c.source == "k2"]
    meets = sum(book.evaluate(c.measures, set(c.impairments)).verdicts[20].status == "meets" for c in complete)
    diff = diff_variants(book, complete, "cpb-2024", "wpa-2023")
    # "before 22" is read as 21, so every profile that meets in the CPB variant fails the WPA one: the largest number there can be
    assert meets > 100 and diff.changed == meets and set(diff.transitions) == {(20, "meets", "not_met")}
    # read as 17 (before 18) it is the smallest: none
    lowered = [Case(c.id, c.source, {**c.measures, "onset_age": 17 if c.measures.get("onset_age") == 21 else c.measures.get("onset_age")}, c.impairments) for c in complete]
    assert diff_variants(book, lowered, "cpb-2024", "wpa-2023").changed == 0


def test_the_commands_work_for_the_group_and_report_through_the_exit_code(capsys):
    assert main(["test", "--group", "intellectual"]) == 0
    assert main(["regress", "--group", "intellectual", "--seeds", "1"]) == 0
    assert main(["diff", "--group", "intellectual", "--seeds", "1", "--a", "cpb-2024", "--b", "wpa-2023"]) == 0
    out = capsys.readouterr().out
    assert "0 divergences" in out and "class 20: meets -> not_met" in out
