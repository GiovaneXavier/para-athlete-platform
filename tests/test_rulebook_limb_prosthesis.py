"""The rule book of the limb deficiency group with prosthesis (classes 61-64, step 3a): a table of levels as data.

Every combination of levels and postures is compared with the current engine, which stays the default.
"""
import copy
import datetime as dt
import itertools

import pytest

from para_triage.education import texts_pt as T
from para_triage.education.trace import _lower_prosthesis as k2_row
from para_triage.education.trace import build_trace
from para_triage.rulebook import Rulebook
from para_triage.rulebook.compare import Case, domain_cases, format_report, regress, sample_cases
from para_triage.rules import Impairment, Posture, Profile
from para_triage.rules.catalog import load_catalog

LOWER, UPPER = (0, 1, 2, 3), (0, 1, 2)
POSTURES = ("standing", "prosthesis")


@pytest.fixture(scope="module")
def book():
    return Rulebook.load("limb_prosthesis")


def levels(ll, lr, ul, ur, posture="prosthesis", **extra):
    return {"posture": posture, "lower_left": ll, "lower_right": lr, "upper_left": ul, "upper_right": ur, **extra}


def test_the_whole_product_of_the_domains_with_every_set_of_impairments_agrees_with_the_current_engine(book):
    cases = domain_cases(book, every_impairment_set=True)
    report = regress(book, cases)
    assert len(cases) == 4 * 5 * 5 * 5 * 4 * 4 and report.clean, format_report(report)  # four sets; each measure also missing


def test_the_144_combinations_of_levels_in_both_postures_agree_with_the_current_engine(book):
    cases = [
        Case(f"{posture}-{c}", "levels", levels(*c, posture=posture), ("limb_deficiency",))
        for posture in POSTURES
        for c in itertools.product(LOWER, LOWER, UPPER, UPPER)
    ]
    report = regress(book, cases)
    assert len(cases) == 2 * 144 and report.clean, format_report(report)


def test_the_study_mode_sample_with_each_measure_hidden_agrees_with_the_current_engine(book):
    cases = sample_cases(book, range(3))
    report = regress(book, cases)
    assert len(cases) > 3000 and report.clean and any(s.startswith("k2-no-") for s in report.total), format_report(report)


@pytest.mark.parametrize("low", (-1, 4))
def test_levels_outside_the_domain_are_read_like_the_current_engine(book, low):
    cases = [Case(f"x-{i}", "outside", levels(a, b, c, d), ("limb_deficiency",)) for i, (a, b, c, d) in enumerate(itertools.product((low, 0, 3), (low, 0, 2), (low, 0), (0, low)))]
    assert regress(book, cases).clean


def test_every_state_the_group_can_give_is_given_by_some_profile(book):
    seen = {v.status for case in domain_cases(book, True) for v in book.evaluate(case.measures, set(case.impairments)).verdicts.values()}
    assert seen == {"meets", "borderline", "needs_review", "insufficient_data", "not_met", "not_applicable"}  # only not_implemented is left


def test_the_regression_detects_a_wrong_row_of_the_table(book):
    wrong = copy.deepcopy(book.data)
    next(rule for rule in wrong["decision"] if rule["id"] == "unilateral_below")["result"] = {"classes": {63: "meets"}, "rest": "not_met"}
    report = regress(Rulebook(wrong), domain_cases(book))
    assert report.divergences["domain"] == 2  # (below, none) and (none, below), with no upper amputation, in the prosthesis posture


# --- the probes of the current engine: what each rule reports as missing --------------------------------------------


def verdicts(book, impairments=("limb_deficiency",), **measures):
    return book.evaluate(measures, set(impairments)).verdicts


def test_without_the_posture_everything_is_insufficient_and_only_the_posture_is_asked_for(book):
    for v in verdicts(book, lower_left=3).values():
        assert (v.status, v.missing) == ("insufficient_data", ("posture",))


def test_another_posture_rules_the_group_out_even_when_levels_are_missing_and_asks_for_nothing(book):
    for posture in ("standing", "seated", "frame_runner"):
        for v in verdicts(book, posture=posture).values():
            assert (v.status, v.missing) == ("not_met", ())


def test_missing_levels_come_after_the_posture_and_are_listed_in_the_order_of_the_fields(book):
    for v in verdicts(book, posture="prosthesis", lower_right=3, upper_left=0).values():
        assert (v.status, v.missing) == ("insufficient_data", ("lower_left", "upper_right"))


def test_an_upper_limb_amputation_is_reviewed_before_the_table_and_no_lower_amputation_is_not_met(book):
    assert {v.status for v in verdicts(book, **levels(3, 3, 0, 1)).values()} == {"needs_review"}
    assert {v.status for v in verdicts(book, **levels(0, 0, 0, 0)).values()} == {"not_met"}


def test_the_rows_of_the_table_tell_which_row_decided(book):
    row = lambda *c: book.evaluate(levels(*c), {"limb_deficiency"}).decision  # noqa: E731
    assert [row(3, 3, 0, 0), row(2, 2, 0, 0), row(0, 3, 0, 0), row(2, 0, 0, 0), row(3, 2, 0, 0), row(1, 0, 0, 0)] == [
        "bilateral_above", "bilateral_below", "unilateral_above", "unilateral_below", "above_plus_below", "foot_involved",
    ]


# --- the study mode explains the same table ----------------------------------------------------------------------------


def k2_profile(ll, lr):
    return Profile(impairments=frozenset({Impairment.LIMB_DEFICIENCY}), posture=Posture.PROSTHESIS, lower_left=ll, lower_right=lr, upper_left=0, upper_right=0)


def test_the_rows_of_the_table_are_the_rows_of_the_study_mode_with_the_same_conclusion(book):
    checked = 0
    for ll, lr in itertools.product(LOWER, LOWER):
        trace = build_trace("limb_prosthesis", k2_profile(ll, lr))
        evaluation = book.evaluate(levels(ll, lr, 0, 0), {"limb_deficiency"})
        meets = [c for c, v in evaluation.verdicts.items() if v.status == "meets"]
        if not max(ll, lr):  # no lower amputation: the study mode concludes that no class applies
            assert evaluation.decision == "no_lower" and trace.answer == "none"
            continue
        answer = f"class:{meets[0]}" if meets else "specialist"
        assert trace.answer == answer
        assert evaluation.decision == k2_row(max(ll, lr), min(ll, lr))[1]  # the id of the row is the id of the study mode
        assert trace.steps[-1].explanation == T.LIMB_ROWS[("lower_prosthesis", evaluation.decision)]
        checked += 1
    assert checked == 15


def test_the_upper_limb_gate_ends_in_the_specialist_in_both(book):
    trace = build_trace("limb_prosthesis", Profile(impairments=frozenset({Impairment.LIMB_DEFICIENCY}), posture=Posture.PROSTHESIS, lower_left=3, lower_right=3, upper_left=2, upper_right=0))
    assert trace.answer == "specialist" and book.evaluate(levels(3, 3, 2, 0), {"limb_deficiency"}).decision == "upper_with_prosthesis"


# --- the numbers ---------------------------------------------------------------------------------------------------------


def test_the_classes_of_the_group_are_the_ones_of_the_catalog_and_have_no_numeric_criteria_to_copy(book):
    catalog = load_catalog()
    assert book.classes == sorted(c.class_id for c in catalog.group_classes("limb_prosthesis"))
    assert not any(catalog.classes[c].criteria for c in book.classes)  # the table is the only copy
    assert set(book.data["applies_to"]) == {i.value for i in catalog.groups["limb_prosthesis"].impairments}


def test_the_posture_value_starts_on_the_first_day_of_the_booklet_year(book):
    assert book.value("required_posture", dt.date(2024, 1, 1)) == "prosthesis"
    with pytest.raises(Exception, match="no value in force"):
        book.value("required_posture", dt.date(2023, 12, 31))
    assert book.value("required_posture", dt.date(2024, 10, 1), overrides={"required_posture": "standing"}) == "standing"
