"""Profile <-> flat record (dict / CSV row)."""
from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from enum import Enum

import pandas as pd

from ..rules import (
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

_INT_FIELDS = {"age", "iq", "ankle_pf_mrc", "lower_limb_sides_affected"}
_BOOL_FIELDS = {
    "adaptive_limitation",
    "onset_before_22",
    "hip_knee_deficit",
    "brain_impairment_report",
    "transfers_independently",
    "walks_short_distances",
    "trunk_straps_needed",
}
_FLOAT_FIELDS = {
    "logmar_best_eye",
    "visual_field_deg",
    "height_cm",
    "longest_arm_cm",
    "ankle_rom_deg",
    "leg_length_diff_cm",
}
_ENUM_FIELDS = {
    "sex": Sex,
    "posture": Posture,
    "lower_left": LowerLimbLevel,
    "lower_right": LowerLimbLevel,
    "upper_left": UpperLimbLevel,
    "upper_right": UpperLimbLevel,
    "neuro_severity": Severity,
    "cp_distribution": CpDistribution,
    "chair_propulsion": Propulsion,
    "arm_function": ArmFunction,
    "trunk_function": TrunkFunction,
    "leg_function": LegFunction,
}
PROFILE_COLUMNS = tuple(f.name for f in dataclasses.fields(Profile))


def profile_to_record(profile: Profile) -> dict:
    record = {}
    for name in PROFILE_COLUMNS:
        value = getattr(profile, name)
        if name == "impairments":
            value = "|".join(sorted(i.value for i in value))
        elif isinstance(value, Enum):
            value = value.value
        record[name] = value
    return record


def _to_bool(value) -> bool:
    return value == "True" if isinstance(value, str) else bool(value)


def record_to_profile(record: Mapping) -> Profile:
    kwargs = {}
    for name in PROFILE_COLUMNS:
        value = record.get(name)
        if name == "impairments":
            text = "" if pd.isna(value) else value
            kwargs[name] = frozenset(Impairment(i) for i in text.split("|") if i)
        elif value is None or pd.isna(value):
            kwargs[name] = None
        elif name in _ENUM_FIELDS:
            enum_cls = _ENUM_FIELDS[name]
            kwargs[name] = enum_cls(int(value)) if issubclass(enum_cls, int) else enum_cls(value)
        elif name in _INT_FIELDS:
            kwargs[name] = int(value)
        elif name in _BOOL_FIELDS:
            kwargs[name] = _to_bool(value)
        elif name in _FLOAT_FIELDS:
            kwargs[name] = float(value)
    return Profile(**kwargs)
