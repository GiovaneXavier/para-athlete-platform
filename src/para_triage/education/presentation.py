"""Profile -> the case text the learner reads (summary and facts), in Portuguese. Read-only."""
from __future__ import annotations

from dataclasses import dataclass

from ..rules import Profile
from . import texts_pt as T


@dataclass(frozen=True)
class Fact:
    label: str
    value: str


@dataclass(frozen=True)
class Presentation:
    summary: str
    facts: tuple[Fact, ...]


def _level(value, labels: dict[int, str]) -> str:
    return T.NOT_MEASURED if value is None else labels[int(value)]


def _visual(profile: Profile) -> Presentation:
    logmar = T.NOT_MEASURED if profile.logmar_best_eye is None else f"{T.fmt(profile.logmar_best_eye, 2)} logMAR"
    field = T.NOT_MEASURED if profile.visual_field_deg is None else f"{T.fmt(profile.visual_field_deg, 1)} graus de diâmetro"
    return Presentation(
        T.SUMMARY_VISUAL,
        (Fact(T.FACT_LABELS["logmar"], logmar), Fact(T.FACT_LABELS["field"], field)),
    )


def _short_stature(profile: Profile) -> Presentation:
    sex = T.NOT_MEASURED if profile.sex is None else T.SEX_LABELS[profile.sex.value]
    height = T.NOT_MEASURED if profile.height_cm is None else f"{T.fmt(profile.height_cm, 1)} cm"
    arm = T.NOT_MEASURED if profile.longest_arm_cm is None else f"{T.fmt(profile.longest_arm_cm, 1)} cm"
    return Presentation(
        T.SUMMARY_SHORT_STATURE,
        (
            Fact(T.FACT_LABELS["sex"], sex),
            Fact(T.FACT_LABELS["height"], height),
            Fact(T.FACT_LABELS["arm"], arm),
        ),
    )


def _limbs(profile: Profile, summary: str) -> Presentation:
    posture = T.POSTURE_LABELS[profile.posture.value]
    return Presentation(
        summary,
        (
            Fact(T.FACT_LABELS["posture"], posture),
            Fact(T.FACT_LABELS["lower_left"], _level(profile.lower_left, T.LOWER_LEVEL_LABELS)),
            Fact(T.FACT_LABELS["lower_right"], _level(profile.lower_right, T.LOWER_LEVEL_LABELS)),
            Fact(T.FACT_LABELS["upper_left"], _level(profile.upper_left, T.UPPER_LEVEL_LABELS)),
            Fact(T.FACT_LABELS["upper_right"], _level(profile.upper_right, T.UPPER_LEVEL_LABELS)),
        ),
    )


def present(group: str, profile: Profile) -> Presentation:
    if group == "visual":
        return _visual(profile)
    if group == "short_stature":
        return _short_stature(profile)
    if group == "limb_standing":
        return _limbs(profile, T.SUMMARY_LIMB_STANDING)
    if group == "limb_prosthesis":
        return _limbs(profile, T.SUMMARY_LIMB_PROSTHESIS)
    raise KeyError(f"group outside the study mode: {group}")
