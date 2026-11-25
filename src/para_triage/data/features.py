"""Numeric encoding of profiles for the models: values plus an observed-mask."""
from __future__ import annotations

from collections.abc import Iterable

import numpy as np

from ..rules import CpDistribution, Impairment, Posture, Profile, Sex

NUMERIC = (
    "logmar_best_eye",
    "visual_field_deg",
    "iq",
    "height_cm",
    "longest_arm_cm",
    "ankle_pf_mrc",
    "ankle_rom_deg",
    "leg_length_diff_cm",
    "lower_limb_sides_affected",
    # ordinal functional descriptors
    "neuro_severity",
    "chair_propulsion",
    "arm_function",
    "trunk_function",
    "leg_function",
)
FLAGS = (
    "adaptive_limitation",
    "onset_before_22",
    "hip_knee_deficit",
    "brain_impairment_report",
    "transfers_independently",
    "walks_short_distances",
    "trunk_straps_needed",
)
LEVELS = ("lower_hi", "lower_lo", "upper_hi", "upper_lo")  # sorted per pair: left/right is irrelevant

FEATURE_NAMES: tuple[str, ...] = (
    *NUMERIC,
    *FLAGS,
    "sex_male",
    *LEVELS,
    *(f"posture_{p.value}" for p in Posture),
    *(f"cp_{d.value}" for d in CpDistribution),
    *(f"impairment_{i.value}" for i in Impairment),
)


def encode_profile(profile: Profile) -> tuple[list[float], list[float]]:
    """Returns (values, mask). Missing values are 0 with mask 0."""
    values: list[float] = []
    mask: list[float] = []

    def put(value, observed: bool) -> None:
        values.append(float(value) if observed else 0.0)
        mask.append(1.0 if observed else 0.0)

    for name in (*NUMERIC, *FLAGS):
        v = getattr(profile, name)
        put(0 if v is None else v, v is not None)
    put(profile.sex is Sex.MALE, profile.sex is not None)

    for pair in ((profile.lower_left, profile.lower_right), (profile.upper_left, profile.upper_right)):
        known = None not in pair
        hi, lo = sorted((int(x) for x in pair), reverse=True) if known else (0, 0)
        put(hi, known)
        put(lo, known)

    for p in Posture:
        put(profile.posture is p, profile.posture is not None)
    for d in CpDistribution:
        put(profile.cp_distribution is d, profile.cp_distribution is not None)
    for i in Impairment:
        put(i in profile.impairments, True)
    return values, mask


def encode_profiles(profiles: Iterable[Profile]) -> tuple[np.ndarray, np.ndarray]:
    pairs = [encode_profile(p) for p in profiles]
    x = np.array([v for v, _ in pairs], dtype=np.float32).reshape(-1, len(FEATURE_NAMES))
    m = np.array([m for _, m in pairs], dtype=np.float32).reshape(-1, len(FEATURE_NAMES))
    return x, m
