"""The rule book trace is equivalent in content to the study-mode trace (education/trace.py) for the two groups.

Same criterion, same value, same result. Nothing is switched: the study mode and the guide keep their own trace.
"""
import re

import pytest

from para_triage.education import cases, scope
from para_triage.education import texts_pt as T
from para_triage.education.trace import build_trace
from para_triage.rulebook import Rulebook
from para_triage.rulebook.compare import Case, measures_of

NUMBER = re.compile(r"-?\d+(?:,\d+)?")
GROUPS = ("visual", "short_stature")
SHORT_WHAT = {T.SS_WHAT_HEIGHT: "height", T.SS_WHAT_ARM: "arm", T.SS_WHAT_SUM: "sum"}
ANSWER_OF_STATUS = {"borderline": "specialist", "insufficient_data": "insufficient"}


def last_number(text: str) -> float:
    return float(NUMBER.findall(text)[-1].replace(",", "."))


def candidates(group: str, per_level: int = 25):
    for level in scope.DIFFICULTIES:
        yield from cases.bank(group, 0).pools[level][:per_level]


def new_trace(group: str, profile):
    book = Rulebook.load(group)
    measures = measures_of(profile, book.measures)
    evaluation = book.evaluate(measures, {i.value for i in profile.impairments})
    return evaluation, {step.criterion: step for step in evaluation.trace}


def new_answer(evaluation) -> str:
    meets = [c for c, v in evaluation.verdicts.items() if v.status == "meets"]
    statuses = {v.status for v in evaluation.verdicts.values()}
    if statuses == {"insufficient_data"}:
        return "insufficient"
    if "borderline" in statuses:
        return "specialist"
    return f"class:{meets[0]}" if len(meets) == 1 else "none"


@pytest.mark.parametrize("group", GROUPS)
def test_the_final_answer_is_the_same_as_the_study_mode_trace(group):
    checked = 0
    for candidate in candidates(group):
        evaluation, _ = new_trace(group, candidate.profile)
        assert new_answer(evaluation) == build_trace(group, candidate.profile).answer == candidate.answer
        checked += 1
    assert checked >= 50


def test_visual_steps_have_the_same_criterion_value_and_result():
    compared = 0
    for candidate in candidates("visual"):
        old = build_trace("visual", candidate.profile)
        _, new = new_trace("visual", candidate.profile)
        profile = candidate.profile
        for step in old.steps:
            if step.result == "not_assessed":  # the study mode has one step for a missing measure; the book, one per criterion
                prefix = "acuity" if step.criterion.startswith("Acuidade") else "field"
                assert all(s.result == "not_assessed" for name, s in new.items() if name.startswith(prefix))
                continue
            if step.criterion.startswith("Acuidade na faixa"):
                assert new["acuity_gap"].result == step.result == "met"
                continue
            cid = int(re.search(r"classe (\d+)", step.criterion).group(1))
            name = f"acuity_{cid}" if step.criterion.startswith("Acuidade") else f"field_{cid}"
            value = profile.logmar_best_eye if name.startswith("acuity") else profile.visual_field_deg
            assert new[name].result == step.result, (name, step, new[name])
            assert new[name].value == value and last_number(step.value) == round(value, 2 if name.startswith("acuity") else 1)
            compared += 1
    assert compared > 200


def test_the_else_chain_of_the_field_is_kept_as_superseded_and_not_as_a_different_result():
    for candidate in candidates("visual"):
        profile = candidate.profile
        if profile.visual_field_deg is not None and profile.visual_field_deg < 10:
            _, new = new_trace("visual", profile)
            assert new["field_13"].result == "met" and new["field_13"].superseded_by == "field_12"  # as the study mode shows it
            return
    pytest.fail("no visual case with a field below the class 12 limit in the sample")


def test_short_stature_steps_have_the_same_criterion_value_and_result():
    compared = 0
    for candidate in candidates("short_stature"):
        old = build_trace("short_stature", candidate.profile)
        evaluation, new = new_trace("short_stature", candidate.profile)
        profile = candidate.profile
        if any(s.result == "not_assessed" for s in old.steps):  # a missing measure: the criteria that need it are not assessed
            gone = {m for m in ("sex", "height_cm", "longest_arm_cm") if getattr(profile, m) is None}
            unassessed = {name for name, s in new.items() if s.result == "not_assessed"}
            needs = {"height": "height_cm", "arm": "longest_arm_cm", "sum": "total_cm"}
            expected = {n for n in new if n.split("_")[0] in needs and ("sex" in gone or needs[n.split("_")[0]] in gone or (n.startswith("sum") and gone))}
            assert unassessed == expected
            continue
        for step in old.steps:
            cid = int(re.search(r"Classe (\d+)", step.criterion).group(1))
            if step.criterion.endswith("as três condições ao mesmo tempo"):
                assert new[f"class_{cid}"].result == step.result
                continue
            what = next(w for k, w in SHORT_WHAT.items() if step.criterion.endswith(k))
            name = f"{what}_{cid}"
            assert new[name].result == step.result, (name, step, new[name])
            expected = {"height": profile.height_cm, "arm": profile.longest_arm_cm, "sum": profile.height_cm + profile.longest_arm_cm}[what]
            assert new[name].value == expected and last_number(step.value) == round(expected, 1)
            compared += 1
    assert compared > 100


def test_the_new_trace_adds_what_the_study_mode_trace_lacks_a_reason_code_the_tests_and_the_source():
    _, new = new_trace("visual", next(iter(candidates("visual"))).profile)
    step = new["acuity_12"]
    assert step.reason == "ACUITY_IN_CLASS_RANGE" and step.source == {"doc": "cpb-booklet-2024", "page": 14}
    assert step.test.startswith("[") and step.reference == {"logmar_min_12": 1.5, "logmar_max_12": 2.6, "boundary_in_class_11": False}
