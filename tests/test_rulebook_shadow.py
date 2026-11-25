"""The whole engine of the rule books, in shadow (step 6): eight books that answer like `RuleEngine`.

The current engine is still the default; this one is used by nothing. Here it is compared with the current engine over the whole
engine (the 33 classes at once, `meets`, `primary_class`, `candidates`), also for profiles with the impairments of several groups.
"""
import ast
import random
from pathlib import Path

import pytest

from para_triage.rulebook import interpreter
from para_triage.rulebook.compare import (
    engine_diff,
    format_engine_report,
    group_items,
    reasons_summary,
    reasons_table,
    regress_engine,
    timing,
)
from para_triage.rulebook.engine import GROUPS, ShadowEngine, ShadowResult, onset_age, onset_flag
from para_triage.rulebook.interpreter import Rulebook, RulebookError, Verdict
from para_triage.rules import ArmFunction, Impairment, LegFunction, LowerLimbLevel, Posture, Profile, RuleEngine, Severity, Status, TrunkFunction
from para_triage.rules.catalog import load_catalog

ENGINE_FILE = Path(__file__).resolve().parents[1] / "src" / "para_triage" / "rulebook" / "engine.py"


@pytest.fixture(scope="module")
def shadow():
    return ShadowEngine()


@pytest.fixture(scope="module")
def current():
    return RuleEngine()


def some(items, share: float, seed: int = 1):
    """A pseudo-random share of the items (not every n-th: the cases come in runs of one profile with each measure hidden), and every mixed one."""
    chosen = random.Random(seed)
    return [item for item in items if chosen.random() < share or item[0].startswith("mixed")]  # the mixed ones are few: all of them


def profile(*impairments, **fields):
    return Profile(impairments=frozenset(Impairment(i) for i in impairments), **fields)


# --- who is each book ----------------------------------------------------------------------------------------------------------


def test_the_classes_of_the_eight_books_are_exactly_the_classes_of_the_catalog_with_no_repetition_and_the_same_group():
    catalog = load_catalog()
    books = {name: Rulebook.load(name) for name in GROUPS}
    classes = [c for book in books.values() for c in book.classes]
    assert len(classes) == len(set(classes)) == len(catalog.classes) == 33 and set(classes) == set(catalog.classes)
    for name, book in books.items():
        assert {catalog.classes[c].group for c in book.classes} == {name}  # the group of each class is the same
        assert set(book.data["applies_to"]) == {i.value for i in catalog.groups[name].impairments}  # and so is the set of impairments
    assert set(GROUPS) == set(catalog.groups) and len(GROUPS) == 8


# --- the shape of the result -------------------------------------------------------------------------------------------------------


def test_the_result_has_the_shape_of_the_eligibility_result_and_the_verdicts_come_out_sorted_by_class(shadow):
    result = shadow.evaluate(profile("visual", logmar_best_eye=2.0, visual_field_deg=120))
    assert isinstance(result, ShadowResult) and list(result.verdicts) == sorted(result.verdicts) and len(result.verdicts) == 33
    verdict = result.verdicts[12]
    assert isinstance(verdict, Verdict) and verdict.status == "meets" and verdict.reasons == ("ACUITY_IN_CLASS_RANGE",) and verdict.missing == ()
    assert result.meets == [12] and result.primary_class == 12 and result.candidates == [12]
    assert {v.status for c, v in result.verdicts.items() if c not in (11, 12, 13)} == {"not_applicable"}


def test_the_questions_of_the_result_follow_the_current_one_meets_primary_class_candidates_and_with_status():
    def verdict(cid, status):
        return Verdict(cid, status)

    one = ShadowResult({1: verdict(1, "borderline"), 2: verdict(2, "meets"), 3: verdict(3, "not_met")})
    two = ShadowResult({1: verdict(1, "meets"), 2: verdict(2, "meets"), 3: verdict(3, "borderline")})
    none = ShadowResult({1: verdict(1, "not_met")})
    assert (one.meets, one.primary_class, one.candidates) == ([2], 2, [2, 1])  # met first, then borderline
    assert (two.meets, two.primary_class, two.candidates) == ([1, 2], None, [1, 2, 3])  # several met: no primary class
    assert (none.meets, none.primary_class, none.candidates) == ([], None, [])
    assert two.with_status("borderline", "not_met") == [3] and two.with_status(Status.MEETS) == [1, 2]  # `Status` is a str enum


def test_the_statuses_are_strings_and_the_current_status_is_a_string_enum_so_the_comparison_by_value_is_safe(shadow, current):
    assert Status.MEETS == "meets" and Status.MEETS.value == "meets" and isinstance(Status.MEETS, str)
    probe = profile("short_stature", sex="F", height_cm=120.0, longest_arm_cm=50.0)
    expected, got = current.evaluate(probe), shadow.evaluate(probe)
    assert {type(v.status) for v in expected.verdicts.values()} == {Status} and {type(v.status) for v in got.verdicts.values()} == {str}
    assert engine_diff(expected, got) is None


def test_the_shadow_engine_does_not_import_the_current_engine():
    imported = [n for node in ast.walk(ast.parse(ENGINE_FILE.read_text(encoding="utf-8"))) if isinstance(node, ast.ImportFrom) for n in [("." * node.level) + (node.module or "")]]
    assert not any(m.startswith("..") or "rules" in m.split(".") for m in imported), imported  # only the regression (compare.py) does


# --- loaded once, options -------------------------------------------------------------------------------------------------------


def test_the_books_and_the_variant_are_loaded_once_and_not_again_for_each_profile(monkeypatch):
    engine = ShadowEngine()

    def forbidden(*args, **kwargs):
        raise AssertionError("a file was read while evaluating a profile")

    monkeypatch.setattr(interpreter, "_read", forbidden)
    monkeypatch.setattr(Rulebook, "load", classmethod(lambda cls, name: forbidden()))
    for _ in range(3):
        result = engine.evaluate(profile("intellectual", iq=70, adaptive_limitation=True, onset_before_22=True))
    assert result.verdicts[20].status == "meets"


def test_the_variant_and_the_overrides_are_options_and_an_override_reaches_every_book_that_has_the_parameter(current):
    probe = profile("intellectual", iq=70, adaptive_limitation=True, onset_before_22=True)
    assert ShadowEngine().evaluate(probe).verdicts[20].status == "meets"
    assert ShadowEngine(variant="wpa-2023").evaluate(probe).verdicts[20].status == "not_met"  # the onset is read as 21, the WPA says before 18
    assert ShadowEngine(overrides={"onset_age_limit": 18}).evaluate(probe).verdicts[20].status == "not_met"
    ankle = profile("rom", posture=Posture.SEATED, arm_function=ArmFunction.PRESERVED, trunk_function=TrunkFunction.FULL, leg_function=LegFunction.ANKLE_LEVEL, ankle_rom_deg=11.0)
    assert ShadowEngine().evaluate(ankle).verdicts[57].status == "borderline"
    assert ShadowEngine(overrides={"max_ankle_arc_deg": 12}).evaluate(ankle).verdicts[57].status == "meets"  # the parameter is shared with limb_standing
    with pytest.raises(RulebookError, match="unknown parameter"):
        ShadowEngine(overrides={"no_such_parameter": 1})


def test_the_onset_is_the_age_of_the_adapter_and_its_missing_field_has_the_name_of_the_book(shadow):
    assert (onset_age(True), onset_age(False), onset_age(None)) == (21, 22, None)
    assert (onset_flag(21), onset_flag(22), onset_flag(None)) == (True, False, None)
    result = shadow.evaluate(profile("intellectual", iq=70, adaptive_limitation=True))
    assert result.verdicts[20].status == "insufficient_data" and result.verdicts[20].missing == ("onset_age",)  # the engine calls it onset_before_22


# --- the regression of the whole engine ----------------------------------------------------------------------------------------------


def test_the_whole_engine_agrees_with_the_current_one_on_a_sample_of_everything_the_per_group_regression_builds_and_on_mixed_impairments(shadow, current):
    items = some(group_items(mixed_per_subset=4), 1 / 6)
    report = regress_engine(items, current, shadow)
    sources = set(report.total)
    assert report.clean, format_engine_report(report)
    assert len(items) > 15000 and {f"{g}:k2" for g in GROUPS} <= sources and {f"mixed-{n}" for n in range(2, 9)} <= sources


def test_profiles_with_the_impairments_of_different_groups_at_the_same_time_agree_with_the_current_engine(shadow, current):
    combos = [("visual", "intellectual"), ("limb_deficiency", "hypertonia"), ("hypertonia", "ataxia", "athetosis", "limb_deficiency"), ("short_stature", "visual", "muscle_power")]
    fields = {"posture": Posture.STANDING, "logmar_best_eye": 1.5, "visual_field_deg": 30.0, "iq": 70, "adaptive_limitation": True, "onset_before_22": True, "sex": None,
              "lower_left": LowerLimbLevel.THROUGH_OR_ABOVE_KNEE, "lower_right": LowerLimbLevel.NONE, "upper_left": 0, "upper_right": 0, "neuro_severity": Severity.MODERATE, "brain_impairment_report": True}
    for kinds in combos:
        for posture in (Posture.STANDING, Posture.SEATED, Posture.PROSTHESIS, Posture.FRAME_RUNNER, None):
            probe = profile(*kinds, **{**fields, "posture": posture})
            assert engine_diff(current.evaluate(probe), shadow.evaluate(probe)) is None, (kinds, posture)


def test_the_regression_of_the_whole_engine_sees_a_wrong_shadow_engine_and_a_wrong_shadow_variant(current):
    items = some(group_items(mixed_per_subset=2), 1 / 20)
    assert not regress_engine(items, current, ShadowEngine(overrides={"iq_max": 74})).clean
    assert not regress_engine(items, current, ShadowEngine(overrides={"max_ankle_arc_deg": 11})).clean
    assert not regress_engine(items, current, ShadowEngine(variant="wpa-2023")).clean  # the adapter's 21 is before 22 and not before 18


# --- the reasons and the time: reports, not tests of equality ---------------------------------------------------------------------


def test_the_sentences_of_the_engine_and_the_codes_of_the_books_pair_up_in_the_same_position_of_almost_every_verdict(shadow, current):
    items = some(group_items(mixed_per_subset=2), 1 / 25)
    summary = reasons_summary(reasons_table(items, current, shadow))
    assert summary["verdicts"] > 100000 and summary["misaligned_verdicts"] / summary["verdicts"] < 0.01
    assert summary["sentences"] > summary["templates"] > 0 and summary["with_values"] > 0 and summary["one_to_one"] > 0


def test_the_time_per_profile_is_measured_for_a_typical_profile_of_each_group():
    seconds = timing(repeat=5)
    assert set(seconds) == set(GROUPS) and all(current > 0 and shadow > 0 for current, shadow in seconds.values())
