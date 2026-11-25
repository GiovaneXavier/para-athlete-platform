"""Samplers for the *true* (noise-free) profile of each rule group.

Values are drawn from a mix of broad ranges and narrow bands around the rule
thresholds, so that borderline cases are well represented. The label is later
computed by the rule engine on the true profile, so the samplers do not need to
know which class a draw falls in.
"""
from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager

import numpy as np

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

Sampler = Callable[[np.random.Generator], Profile]


_EDGE_SCALE = 1.0  # 0 turns off every concentration of values near the rule thresholds (see natural_ranges)


def _edge_p(p: float) -> float:
    return p * _EDGE_SCALE


@contextmanager
def natural_ranges():
    """Draw values from the broad clinical ranges only, without the extra mass near the rule thresholds."""
    global _EDGE_SCALE
    previous, _EDGE_SCALE = _EDGE_SCALE, 0.0
    try:
        yield
    finally:
        _EDGE_SCALE = previous


def _edge_mix(rng, lo, hi, edges, scale, p_edge=0.4) -> float:
    """Uniform on [lo, hi], or with probability p_edge a normal band around a threshold."""
    x = rng.choice(edges) + rng.normal(0, scale) if rng.random() < _edge_p(p_edge) else rng.uniform(lo, hi)
    return float(np.clip(x, lo, hi))


def sample_visual(rng) -> Profile:
    logmar = round(_edge_mix(rng, -0.1, 3.0, [1.0, 1.4, 1.5, 2.6], 0.05), 2)
    if rng.random() < 0.5:
        field = rng.uniform(70, 180)
    else:
        field = _edge_mix(rng, 1, 70, [10, 40], 2.0)
    return Profile(
        impairments=frozenset({Impairment.VISUAL}),
        posture=Posture.STANDING,
        logmar_best_eye=logmar,
        visual_field_deg=round(float(field), 1),
    )


def sample_intellectual(rng) -> Profile:
    iq = rng.normal(75, 3) if rng.random() < _edge_p(0.4) else rng.uniform(45, 120)
    iq = int(round(np.clip(iq, 40, 130)))
    return Profile(
        impairments=frozenset({Impairment.INTELLECTUAL}),
        posture=Posture.STANDING,
        iq=iq,
        adaptive_limitation=bool(rng.random() < (0.92 if iq <= 75 else 0.35)),
        onset_before_22=bool(rng.random() < 0.9),
    )


_SUM_EDGES = {Sex.MALE: (180, 200), Sex.FEMALE: (173, 190)}


def sample_short_stature(rng) -> Profile:
    sex = Sex.MALE if rng.random() < 0.5 else Sex.FEMALE
    ratio = float(np.clip(rng.normal(0.44, 0.03), 0.35, 0.55))  # arm length / height
    if rng.random() < _edge_p(0.5):
        height = (rng.choice(_SUM_EDGES[sex]) + rng.normal(0, 3)) / (1 + ratio)
    else:
        height = rng.uniform(95, 165) if sex is Sex.MALE else rng.uniform(90, 155)
    height = float(np.clip(height, 80, 175))
    return Profile(
        sex=sex,
        impairments=frozenset({Impairment.SHORT_STATURE}),
        posture=Posture.STANDING,
        height_cm=round(height, 1),
        longest_arm_cm=round(height * ratio, 1),
    )


_LOWER_P = [0.40, 0.10, 0.25, 0.25]
_UPPER_P = [0.45, 0.25, 0.30]


def _amputation_levels(rng, mode: str) -> dict:
    lower = [LowerLimbLevel.NONE, LowerLimbLevel.NONE]
    upper = [UpperLimbLevel.NONE, UpperLimbLevel.NONE]
    if mode in ("lower", "both"):
        lower = [LowerLimbLevel(int(rng.choice(4, p=_LOWER_P))) for _ in range(2)]
    if mode in ("upper", "both"):
        upper = [UpperLimbLevel(int(rng.choice(3, p=_UPPER_P))) for _ in range(2)]
    return dict(lower_left=lower[0], lower_right=lower[1], upper_left=upper[0], upper_right=upper[1])


def sample_limb_standing(rng) -> Profile:
    if rng.random() < 0.7:
        mode = ("lower", "upper", "both")[int(rng.choice(3, p=[0.55, 0.35, 0.10]))]
        return Profile(
            impairments=frozenset({Impairment.LIMB_DEFICIENCY}),
            posture=Posture.STANDING,
            **_amputation_levels(rng, mode),
        )

    kinds = (Impairment.MUSCLE_POWER, Impairment.ROM, Impairment.LEG_LENGTH_DIFFERENCE)
    chosen = {kinds[i] for i in rng.choice(3, size=int(rng.integers(1, 4)), replace=False)}
    fields: dict = {}
    if Impairment.MUSCLE_POWER in chosen:
        fields["ankle_pf_mrc"] = int(rng.choice(6, p=[0.10, 0.15, 0.20, 0.20, 0.20, 0.15]))
    if Impairment.ROM in chosen:
        fields["ankle_rom_deg"] = round(_edge_mix(rng, 0, 50, [10], 3.0), 1)
    if Impairment.LEG_LENGTH_DIFFERENCE in chosen:
        fields["leg_length_diff_cm"] = round(_edge_mix(rng, 0, 12, [7], 0.7), 1)
    return Profile(
        impairments=frozenset(chosen),
        posture=Posture.STANDING,
        lower_limb_sides_affected=1 if rng.random() < 0.75 else 2,
        hip_knee_deficit=bool(rng.random() < 0.10),
        **_amputation_levels(rng, "none"),
        **fields,
    )


def sample_limb_prosthesis(rng) -> Profile:
    mode = "lower" if rng.random() < 0.9 else "both"
    return Profile(
        impairments=frozenset({Impairment.LIMB_DEFICIENCY}),
        posture=Posture.PROSTHESIS,
        **_amputation_levels(rng, mode),
    )


# --- Brain impairment ---------------------------------------------------------------------------

_NEURO_SETS = (
    {Impairment.HYPERTONIA},
    {Impairment.ATHETOSIS},
    {Impairment.ATAXIA},
    {Impairment.HYPERTONIA, Impairment.ATHETOSIS},
    {Impairment.HYPERTONIA, Impairment.ATAXIA},
    {Impairment.ATHETOSIS, Impairment.ATAXIA},
    {Impairment.HYPERTONIA, Impairment.ATHETOSIS, Impairment.ATAXIA},
)
_NEURO_SET_P = [0.50, 0.15, 0.05, 0.15, 0.05, 0.05, 0.05]
_DISTRIBUTIONS = tuple(CpDistribution)


def _neuro_types(rng) -> frozenset[Impairment]:
    return frozenset(_NEURO_SETS[int(rng.choice(len(_NEURO_SETS), p=_NEURO_SET_P))])


def _distribution(rng) -> CpDistribution:
    return _DISTRIBUTIONS[int(rng.integers(len(_DISTRIBUTIONS)))]


def sample_neuro_seated(rng) -> Profile:
    return Profile(
        impairments=_neuro_types(rng),
        posture=Posture.SEATED,
        brain_impairment_report=True,
        cp_distribution=_distribution(rng),
        neuro_severity=Severity(int(rng.choice([2, 3], p=[0.4, 0.6]))),
        chair_propulsion=Propulsion(int(rng.integers(1, 5))),
    )


def sample_neuro_standing(rng) -> Profile:
    return Profile(
        impairments=_neuro_types(rng),
        posture=Posture.STANDING,
        brain_impairment_report=True,
        cp_distribution=_distribution(rng),
        neuro_severity=Severity(int(rng.choice([1, 2, 3], p=[0.35, 0.50, 0.15]))),
    )


def sample_frame_runner(rng) -> Profile:
    severity = Severity(int(rng.choice([1, 2, 3], p=[0.15, 0.35, 0.50])))
    transfers = bool(rng.random() < (0.15 if severity is Severity.SEVERE else 0.65))
    return Profile(
        impairments=_neuro_types(rng),
        posture=Posture.FRAME_RUNNER,
        brain_impairment_report=True,
        cp_distribution=_distribution(rng),
        neuro_severity=severity,
        transfers_independently=transfers,
        walks_short_distances=bool(rng.random() < (0.70 if transfers else 0.15)),
        trunk_straps_needed=bool(rng.random() < (0.15 if transfers else 0.80)),
    )


# --- Seated physical classes ---------------------------------------------------------------------
# One entry per neurological / functional band: arm, trunk and leg function typical of it.
_SEATED_BANDS = (
    (ArmFunction.SHOULDER_ELBOW_DEFICIT, TrunkFunction.NONE, LegFunction.NONE),  # C5-C6
    (ArmFunction.FINGER_DEFICIT, TrunkFunction.NONE, LegFunction.NONE),  # C7
    (ArmFunction.INTRINSIC_ONLY, TrunkFunction.NONE, LegFunction.NONE),  # C8
    (ArmFunction.PRESERVED, TrunkFunction.NONE, LegFunction.NONE),  # T1-T7
    (ArmFunction.PRESERVED, TrunkFunction.PARTIAL, LegFunction.HIP_FLEXORS_ONLY),  # T8-L1
    (ArmFunction.PRESERVED, TrunkFunction.FULL, LegFunction.HIP_AND_KNEE),  # L2-L4
    (ArmFunction.PRESERVED, TrunkFunction.FULL, LegFunction.ANKLE_LEVEL),  # ankle level
    (ArmFunction.PRESERVED, TrunkFunction.FULL, LegFunction.NORMAL),  # nothing eligible in the legs
)


def sample_wheelchair(rng) -> Profile:
    arm, trunk, leg = _SEATED_BANDS[int(rng.integers(len(_SEATED_BANDS)))]
    if leg is LegFunction.HIP_FLEXORS_ONLY and rng.random() < 0.4:
        trunk, leg = TrunkFunction.FULL, LegFunction.NONE
    if rng.random() < 0.08:  # atypical combination, e.g. incomplete injuries
        which = int(rng.integers(3))
        if which == 0:
            arm = ArmFunction(int(rng.integers(0, 4)))
        elif which == 1:
            trunk = TrunkFunction(int(rng.integers(0, 3)))
        else:
            leg = LegFunction(int(rng.integers(0, 5)))

    impairments = {Impairment.MUSCLE_POWER}
    if rng.random() < 0.20:
        impairments.add(Impairment.LIMB_DEFICIENCY)
    if rng.random() < 0.10:
        impairments.add(Impairment.ROM)

    ankle: dict = {}
    if leg is LegFunction.ANKLE_LEVEL:
        kind = int(rng.integers(0, 4))  # 3 = measured, but no CME met
        if kind == 0:
            ankle["ankle_pf_mrc"] = int(rng.integers(0, 3))
        elif kind == 1:
            ankle["ankle_rom_deg"] = round(float(rng.uniform(0, 10)), 1)
        elif kind == 2:
            impairments.add(Impairment.LEG_LENGTH_DIFFERENCE)
            ankle["leg_length_diff_cm"] = round(float(rng.uniform(7, 12)), 1)
        else:
            ankle["ankle_pf_mrc"] = int(rng.integers(3, 6))
    return Profile(
        impairments=frozenset(impairments),
        posture=Posture.SEATED,
        arm_function=arm,
        trunk_function=trunk,
        leg_function=leg,
        **ankle,
    )


SAMPLERS: dict[str, Sampler] = {
    "visual": sample_visual,
    "intellectual": sample_intellectual,
    "short_stature": sample_short_stature,
    "limb_standing": sample_limb_standing,
    "limb_prosthesis": sample_limb_prosthesis,
    "neuro_seated": sample_neuro_seated,
    "neuro_standing": sample_neuro_standing,
    "frame_runner": sample_frame_runner,
    "wheelchair": sample_wheelchair,
}

# Labels each group is balanced on: class id, 0 = no eligible class, -1 = ambiguous.
TARGETS: dict[str, tuple[int, ...]] = {
    "visual": (0, 11, 12, 13, -1),
    "intellectual": (0, 20),
    "short_stature": (0, 40, 41),
    "limb_standing": (0, 42, 43, 44, 45, 46, 47, -1),
    "limb_prosthesis": (61, 62, 63, 64, -1),
    "neuro_seated": (31, 32, 33, 34, -1),
    "neuro_standing": (35, 36, 37, 38, -1),
    "frame_runner": (0, 71, 72, -1),
    "wheelchair": (0, 51, 52, 53, 54, 55, 56, 57, -1),
}
