"""Synthetic profiles of the core contract test (see make_core_contract.py).

Each entry is (name, group, raw profile). Raw profiles use the JSON-friendly spelling of the
API: enum values for strings, integers for the IntEnum fields.
"""
from __future__ import annotations

from dataclasses import fields

from para_triage.rules import (
    ArmFunction,
    CpDistribution,
    Impairment,
    LegFunction,
    LowerLimbLevel,
    Posture,
    Profile,
    Propulsion,
    Severity,
    Sex,
    TrunkFunction,
    UpperLimbLevel,
)

_ENUM_FIELDS = {
    "sex": Sex,
    "posture": Posture,
    "neuro_severity": Severity,
    "cp_distribution": CpDistribution,
    "chair_propulsion": Propulsion,
    "arm_function": ArmFunction,
    "trunk_function": TrunkFunction,
    "leg_function": LegFunction,
    "lower_left": LowerLimbLevel,
    "lower_right": LowerLimbLevel,
    "upper_left": UpperLimbLevel,
    "upper_right": UpperLimbLevel,
}


def build_profile(raw: dict) -> Profile:
    """Raw JSON-friendly dict -> Profile (unknown keys raise)."""
    known = {f.name for f in fields(Profile)}
    unknown = set(raw) - known
    if unknown:
        raise KeyError(f"unknown profile fields: {sorted(unknown)}")
    data = dict(raw)
    data["impairments"] = frozenset(Impairment(v) for v in raw.get("impairments", []))
    for key, enum in _ENUM_FIELDS.items():
        if data.get(key) is not None:
            data[key] = enum(data[key])
    return Profile(**data)


def _limbs(posture: str, lower_left: int, lower_right: int, upper_left: int, upper_right: int) -> dict:
    return {
        "impairments": ["limb_deficiency"],
        "posture": posture,
        "lower_left": lower_left,
        "lower_right": lower_right,
        "upper_left": upper_left,
        "upper_right": upper_right,
    }


def _neuro(posture: str, severity: int, **extra) -> dict:
    return {
        "impairments": ["hypertonia"],
        "posture": posture,
        "brain_impairment_report": True,
        "neuro_severity": severity,
        **extra,
    }


def _petra(transfers: bool, walks: bool, straps: bool) -> dict:
    return _neuro(
        "frame_runner", 3, transfers_independently=transfers, walks_short_distances=walks, trunk_straps_needed=straps
    )


def _chair(trunk: int) -> dict:
    return {"impairments": ["muscle_power"], "posture": "seated", "arm_function": 3, "trunk_function": trunk, "leg_function": 0}


PROFILES: list[tuple[str, str, dict]] = [
    ("visual_clear", "visual", {"impairments": ["visual"], "logmar_best_eye": 2.8, "visual_field_deg": 90}),
    ("visual_gap_borderline", "visual", {"impairments": ["visual"], "logmar_best_eye": 1.45, "visual_field_deg": 90}),
    ("visual_missing_field", "visual", {"impairments": ["visual"], "logmar_best_eye": 1.2}),
    (
        "intellectual_meets",
        "intellectual",
        {"impairments": ["intellectual"], "iq": 65, "adaptive_limitation": True, "onset_before_22": True},
    ),
    (
        "short_stature_meets",
        "short_stature",
        {"impairments": ["short_stature"], "sex": "M", "height_cm": 125, "longest_arm_cm": 50},
    ),
    ("short_stature_incomplete", "short_stature", {"impairments": ["short_stature"], "sex": "F", "height_cm": 130}),
    ("standing_below_knee_unilateral", "limb_standing", _limbs("standing", 2, 0, 0, 0)),
    ("standing_upper_limbs_both_elbow", "limb_standing", _limbs("standing", 0, 0, 2, 2)),
    ("standing_combined_upper_and_lower", "limb_standing", _limbs("standing", 2, 0, 2, 0)),
    ("prosthesis_below_knee", "limb_prosthesis", _limbs("prosthesis", 2, 0, 0, 0)),
    ("prosthesis_bilateral_above_knee", "limb_prosthesis", _limbs("prosthesis", 3, 3, 0, 0)),
    ("neuro_standing_hemiplegia", "neuro", _neuro("standing", 2, cp_distribution="hemiplegia")),
    ("neuro_seated_arms_symmetric", "neuro", _neuro("seated", 2, cp_distribution="diplegia", chair_propulsion=4)),
    ("petra_transfers_independently", "frame_runner", _petra(True, False, False)),
    ("petra_cannot_transfer", "frame_runner", _petra(False, False, True)),
    ("wheelchair_arms_preserved_no_trunk", "wheelchair", _chair(0)),
    ("wheelchair_arms_preserved_partial_trunk", "wheelchair", _chair(1)),
    ("no_impairment_declared", "none", {}),
]
