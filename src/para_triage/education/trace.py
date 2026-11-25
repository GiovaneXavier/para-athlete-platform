"""Criterion-by-criterion trace of a case, rebuilt from the catalog criteria. Read-only.

The trace is an explanation. The answer key always comes from the rule engine (cases.engine_answer);
the trace reaches a conclusion of its own, and tests (and the case bank at run time) compare the two.

Visual and short stature use the numeric `criteria` of rules/classes.yaml. The limb groups have no
numeric criteria in the catalog: their rules are a table of amputation levels in
rules/evaluators/limb.py, repeated below as DECISION_ROWS and checked exhaustively against the engine.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..rules import Profile
from ..rules.catalog import Catalog, load_catalog
from . import texts_pt as T
from .scope import OPTION_INSUFFICIENT, OPTION_NONE, OPTION_SPECIALIST, class_option_id

MET, NOT_MET, NOT_ASSESSED = "met", "not_met", "not_assessed"
NONE_SHOWN = "—"


@dataclass(frozen=True)
class Step:
    criterion: str
    reference: str
    value: str
    result: str  # MET, NOT_MET or NOT_ASSESSED
    explanation: str


@dataclass(frozen=True)
class Trace:
    steps: tuple[Step, ...]
    answer: str  # option id the trace concludes: "class:<id>", "none", "specialist" or "insufficient"
    conclusion: str
    source_pages: tuple[int, ...]
    limits: tuple[str, ...]


# --- visual -------------------------------------------------------------------------------------------


def _visual(profile: Profile, criteria: dict[int, dict]) -> tuple[list[Step], str, str]:
    c11, c12, c13 = criteria[11], criteria[12], criteria[13]
    acuity, field = profile.logmar_best_eye, profile.visual_field_deg
    steps: list[Step] = []
    hits: set[int] = set()
    gap = False
    missing: list[str] = []

    if acuity is None:
        missing.append(T.VIS_MISSING_NAMES["acuity"])
        steps.append(Step("Acuidade do melhor olho", NONE_SHOWN, T.NOT_MEASURED, NOT_ASSESSED, T.VIS_MISSING_ACUITY))
    else:
        value = T.VIS_ACUITY_VALUE.format(value=T.fmt(acuity, 2))
        ranges = (
            (11, T.VIS_ACUITY_REF_11.format(limit=T.fmt(c11["logmar_gt"], 2)), acuity > c11["logmar_gt"]),
            (
                12,
                T.VIS_ACUITY_REF_RANGE.format(low=T.fmt(c12["logmar_min"], 2), high=T.fmt(c12["logmar_max"], 2)),
                c12["logmar_min"] <= acuity <= c12["logmar_max"],
            ),
            (
                13,
                T.VIS_ACUITY_REF_RANGE.format(low=T.fmt(c13["logmar_min"], 2), high=T.fmt(c13["logmar_max"], 2)),
                c13["logmar_min"] <= acuity <= c13["logmar_max"],
            ),
        )
        for cid, reference, inside in ranges:
            if inside:
                hits.add(cid)
            steps.append(
                Step(
                    T.VIS_ACUITY_CRITERION.format(cid=cid),
                    reference,
                    value,
                    MET if inside else NOT_MET,
                    (T.VIS_MET if inside else T.VIS_NOT_MET).format(cid=cid),
                )
            )
        gap = c13["logmar_max"] < acuity < c12["logmar_min"]
        if gap:
            high, low = T.fmt(c13["logmar_max"], 2), T.fmt(c12["logmar_min"], 2)
            steps.append(
                Step(
                    "Acuidade na faixa que o livreto deixa sem classe",
                    f"entre {high} e {low} logMAR",
                    value,
                    MET,
                    T.VIS_GAP.format(high=high, low=low),
                )
            )

    if field is None:
        missing.append(T.VIS_MISSING_NAMES["field"])
        steps.append(Step("Campo visual", NONE_SHOWN, T.NOT_MEASURED, NOT_ASSESSED, T.VIS_MISSING_FIELD))
    else:
        value = T.VIS_FIELD_VALUE.format(value=T.fmt(field, 1))
        below12, below13 = field < c12["field_lt_deg"], field < c13["field_lt_deg"]
        if below12:
            hits.add(12)
        elif below13:
            hits.add(13)
        for cid, limit, inside in ((12, c12["field_lt_deg"], below12), (13, c13["field_lt_deg"], below13)):
            steps.append(
                Step(
                    T.VIS_FIELD_CRITERION.format(cid=cid),
                    T.VIS_FIELD_REF.format(limit=T.fmt(limit, 0)),
                    value,
                    MET if inside else NOT_MET,
                    (T.VIS_MET if inside else T.VIS_NOT_MET).format(cid=cid),
                )
            )

    high, low = T.fmt(c13["logmar_max"], 2), T.fmt(c12["logmar_min"], 2)
    if hits:
        primary = min(hits)
        if gap and primary > 12:
            return steps, OPTION_SPECIALIST, T.VIS_CONCLUSION_SPECIALIST.format(high=high, low=low)
        return steps, class_option_id(primary), T.VIS_CONCLUSION_CLASS.format(cid=primary)
    if gap:
        return steps, OPTION_SPECIALIST, T.VIS_CONCLUSION_SPECIALIST.format(high=high, low=low)
    if missing:
        return steps, OPTION_INSUFFICIENT, T.VIS_CONCLUSION_INSUFFICIENT.format(missing=" e ".join(missing))
    return steps, OPTION_NONE, T.VIS_CONCLUSION_NONE


# --- short stature ------------------------------------------------------------------------------------


def _short_stature(profile: Profile, criteria: dict[int, dict]) -> tuple[list[Step], str, str]:
    missing = [
        T.SS_MISSING_NAMES[key]
        for key, value in (("sex", profile.sex), ("height", profile.height_cm), ("arm", profile.longest_arm_cm))
        if value is None
    ]
    if missing:
        steps = [
            Step(T.SS_CRITERION.format(cid="40 e 41", what=name), NONE_SHOWN, T.NOT_MEASURED, NOT_ASSESSED, T.SS_MISSING.format(what=name))
            for name in missing
        ]
        return steps, OPTION_INSUFFICIENT, T.SS_CONCLUSION_INSUFFICIENT.format(missing=" e ".join(missing))

    height, arm = profile.height_cm, profile.longest_arm_cm
    total = height + arm
    key = "male" if profile.sex.value == "M" else "female"
    steps: list[Step] = []
    winner: int | None = None
    for cid in (40, 41):
        limit = criteria[cid][key]
        checks = (
            (T.SS_WHAT_HEIGHT, limit["max_height_cm"], T.SS_VALUE.format(value=T.fmt(height, 1)), height <= limit["max_height_cm"]),
            (T.SS_WHAT_ARM, limit["max_arm_cm"], T.SS_VALUE.format(value=T.fmt(arm, 1)), arm <= limit["max_arm_cm"]),
            (
                T.SS_WHAT_SUM,
                limit["max_sum_cm"],
                T.SS_VALUE_SUM.format(height=T.fmt(height, 1), arm=T.fmt(arm, 1), total=T.fmt(total, 1)),
                total <= limit["max_sum_cm"],
            ),
        )
        for what, bound, value, inside in checks:
            steps.append(
                Step(
                    T.SS_CRITERION.format(cid=cid, what=what),
                    T.SS_REF.format(limit=T.fmt(bound, 0)),
                    value,
                    MET if inside else NOT_MET,
                    T.SS_MET if inside else T.SS_NOT_MET,
                )
            )
        count = sum(1 for *_, inside in checks if inside)
        all_met = count == 3
        steps.append(
            Step(
                T.SS_ALL_CRITERION.format(cid=cid),
                T.SS_ALL_REF,
                T.SS_ALL_VALUE.format(count=count),
                MET if all_met else NOT_MET,
                (T.SS_ALL_MET if all_met else T.SS_ALL_NOT_MET).format(cid=cid),
            )
        )
        if all_met and winner is None:
            winner = cid
    if winner is not None:
        return steps, class_option_id(winner), T.SS_CONCLUSION_CLASS.format(cid=winner)
    return steps, OPTION_NONE, T.SS_CONCLUSION_NONE


# --- limb groups: decision table of amputation levels -----------------------------------------------
# Each row: (pair (most affected, least affected) or a predicate name, answer, row id). Mirrors the
# tables in rules/evaluators/limb.py; tests compare every combination with the engine.

LowerRow = tuple[str, str]  # (answer option id, row id)


def _lower_standing(hi: int, lo: int) -> LowerRow:
    if (hi, lo) == (3, 0):
        return class_option_id(42), "unilateral_above"
    if (hi, lo) == (3, 1):
        return OPTION_SPECIALIST, "unilateral_above_plus_foot"
    if hi == 3:
        return OPTION_SPECIALIST, "bilateral_with_above"
    if (hi, lo) == (2, 2):
        return class_option_id(43), "bilateral_below"
    if (hi, lo) == (2, 0):
        return class_option_id(44), "unilateral_below"
    if (hi, lo) == (2, 1):
        return OPTION_SPECIALIST, "below_plus_foot"
    if (hi, lo) == (1, 0):
        return OPTION_SPECIALIST, "unilateral_foot"
    return OPTION_SPECIALIST, "bilateral_foot"


def _upper_standing(hi: int, lo: int) -> LowerRow:
    if (hi, lo) == (2, 2):
        return class_option_id(45), "bilateral_elbow"
    if (hi, lo) == (2, 0):
        return class_option_id(46), "unilateral_elbow"
    if (hi, lo) == (1, 1):
        return class_option_id(46), "bilateral_wrist"
    if (hi, lo) == (2, 1):
        return OPTION_SPECIALIST, "elbow_plus_wrist"
    return class_option_id(47), "unilateral_wrist"


def _lower_prosthesis(hi: int, lo: int) -> LowerRow:
    if (hi, lo) == (3, 3):
        return class_option_id(61), "bilateral_above"
    if (hi, lo) == (2, 2):
        return class_option_id(62), "bilateral_below"
    if (hi, lo) == (3, 0):
        return class_option_id(63), "unilateral_above"
    if (hi, lo) == (2, 0):
        return class_option_id(64), "unilateral_below"
    if (hi, lo) == (3, 2):
        return OPTION_SPECIALIST, "above_plus_below"
    return OPTION_SPECIALIST, "foot_involved"


_LEVEL_FIELDS = ("lower_left", "lower_right", "upper_left", "upper_right")


def _level_text(field: str, value: int) -> str:
    return (T.LOWER_LEVEL_LABELS if field.startswith("lower") else T.UPPER_LEVEL_LABELS)[value]


def _limbs(group: str, profile: Profile) -> tuple[list[Step], str, str]:
    steps: list[Step] = []
    missing = []
    for name in _LEVEL_FIELDS:
        value = getattr(profile, name)
        criterion = T.LIMB_LEVEL_CRITERION.format(where=T.LIMB_LEVEL_WHERE[name])
        if value is None:
            missing.append(name)
            steps.append(Step(criterion, T.LIMB_LEVEL_REF, T.NOT_MEASURED, NOT_ASSESSED, T.LIMB_LEVEL_MISSING))
        else:
            steps.append(Step(criterion, T.LIMB_LEVEL_REF, _level_text(name, int(value)), MET, T.LIMB_LEVEL_MET))
    if missing:
        return steps, OPTION_INSUFFICIENT, T.LIMB_CONCLUSION_INSUFFICIENT

    lower = tuple(sorted((int(profile.lower_left), int(profile.lower_right)), reverse=True))
    upper = tuple(sorted((int(profile.upper_left), int(profile.upper_right)), reverse=True))

    def pair_step(kind: str, which: str, pair: tuple[int, int], row: tuple[str, str]) -> Step:
        labels = T.LOWER_LEVEL_LABELS if which == "lower" else T.UPPER_LEVEL_LABELS
        return Step(
            T.LIMB_PAIR_CRITERION.format(which=T.LIMB_PAIR_WHICH[which]),
            T.LIMB_PAIR_REF,
            T.LIMB_PAIR_VALUE.format(high=labels[pair[0]], low=labels[pair[1]]),
            MET,
            T.LIMB_ROWS[(kind, row[1])],
        )

    def finish(row: tuple[str, str]) -> tuple[list[Step], str, str]:
        answer = row[0]
        if answer == OPTION_SPECIALIST:
            return steps, answer, T.LIMB_CONCLUSION_SPECIALIST
        return steps, answer, T.LIMB_CONCLUSION_CLASS.format(cid=answer.split(":")[1])

    if group == "limb_standing":
        both = bool(lower[0] and upper[0])
        steps.append(
            Step(
                T.LIMB_BOTH_CRITERION,
                T.LIMB_GATE_REF,
                T.LIMB_BOTH_VALUE_YES if both else T.LIMB_BOTH_VALUE_NO,
                MET if both else NOT_MET,
                T.LIMB_BOTH_EXPLANATION_YES if both else T.LIMB_BOTH_EXPLANATION_NO,
            )
        )
        if both:
            return steps, OPTION_SPECIALIST, T.LIMB_CONCLUSION_SPECIALIST
        if lower[0]:
            row = _lower_standing(*lower)
            steps.append(pair_step("lower_standing", "lower", lower, row))
            return finish(row)
        if upper[0]:
            row = _upper_standing(*upper)
            steps.append(pair_step("upper_standing", "upper", upper, row))
            return finish(row)
        steps.append(Step(T.LIMB_NONE_CRITERION, NONE_SHOWN, T.LIMB_NONE_VALUE, NOT_MET, T.LIMB_NONE_EXPLANATION))
        return steps, OPTION_NONE, T.LIMB_CONCLUSION_NONE

    # limb_prosthesis
    has_upper = bool(upper[0])
    steps.append(
        Step(
            T.LIMB_UPPER_PROSTHESIS_CRITERION,
            T.LIMB_GATE_REF,
            T.LIMB_BOTH_VALUE_YES if has_upper else T.LIMB_BOTH_VALUE_NO,
            MET if has_upper else NOT_MET,
            T.LIMB_UPPER_PROSTHESIS_YES if has_upper else T.LIMB_UPPER_PROSTHESIS_NO,
        )
    )
    if has_upper:
        return steps, OPTION_SPECIALIST, T.LIMB_CONCLUSION_SPECIALIST
    if not lower[0]:
        steps.append(Step(T.LIMB_NO_LOWER_CRITERION, NONE_SHOWN, T.LIMB_NONE_VALUE, NOT_MET, T.LIMB_NO_LOWER_EXPLANATION))
        return steps, OPTION_NONE, T.LIMB_CONCLUSION_NONE
    row = _lower_prosthesis(*lower)
    steps.append(pair_step("lower_prosthesis", "lower", lower, row))
    return finish(row)


# --- entry point --------------------------------------------------------------------------------------


def build_trace(group: str, profile: Profile, catalog: Catalog | None = None) -> Trace:
    catalog = catalog or load_catalog()
    criteria = {cid: spec.criteria for cid, spec in catalog.classes.items()}
    if group == "visual":
        steps, answer, conclusion = _visual(profile, criteria)
    elif group == "short_stature":
        steps, answer, conclusion = _short_stature(profile, criteria)
    elif group in ("limb_standing", "limb_prosthesis"):
        steps, answer, conclusion = _limbs(group, profile)
    else:
        raise KeyError(f"group outside the study mode: {group}")

    group_pages = sorted({s.source_page for s in catalog.group_classes(group) if s.source_page is not None})
    if answer.startswith("class:"):
        spec = catalog.classes[int(answer.split(":")[1])]
        pages = (spec.source_page,) if spec.source_page is not None else ()
    else:
        pages = tuple(group_pages)
    return Trace(tuple(steps), answer, conclusion, pages, (*T.LIMITS[group], T.LIMITS_COMMON))
