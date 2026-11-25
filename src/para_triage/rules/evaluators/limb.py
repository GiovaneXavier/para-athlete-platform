"""Limb-deficiency evaluators for standing (42-47) and prosthesis (61-64) classes.

Both work from amputation levels per side. The standing group also has a
strength / ROM / leg-length pathway limited to the ankle CMEs named in the booklet.
"""
from __future__ import annotations

from collections.abc import Sequence

from ..catalog import ClassSpec
from ..schema import Impairment, Posture, Profile, Status, Verdict
from .base import merge, posture_gate, resolve, uniform

Outcome = tuple[dict[int, str], dict[int, str], str | None]  # meets, borderline, review reason

_MCE_IMPAIRMENTS = {Impairment.MUSCLE_POWER, Impairment.ROM, Impairment.LEG_LENGTH_DIFFERENCE}
_LEVEL_FIELDS = ("lower_left", "lower_right", "upper_left", "upper_right")


def _levels(profile: Profile) -> tuple[tuple[int, int] | None, tuple[int, int] | None, tuple[str, ...]]:
    missing = tuple(f for f in _LEVEL_FIELDS if getattr(profile, f) is None)
    if missing:
        return None, None, missing
    lower = tuple(sorted((int(profile.lower_left), int(profile.lower_right)), reverse=True))
    upper = tuple(sorted((int(profile.upper_left), int(profile.upper_right)), reverse=True))
    return lower, upper, ()


def _lower_standing(hi: int, lo: int) -> Outcome:
    if (hi, lo) == (3, 0):
        return {42: "unilateral amputation through or above the knee"}, {}, None
    if (hi, lo) == (3, 1):
        return {}, {42: "unilateral above-knee amputation with partial foot on the other side; verify"}, None
    if hi == 3:
        return {}, {}, "bilateral involvement including above-knee while standing without prosthesis"
    if (hi, lo) == (2, 2):
        return {43: "bilateral below-knee amputation"}, {}, None
    if (hi, lo) == (2, 0):
        return {44: "unilateral below-knee amputation"}, {}, None
    if (hi, lo) == (2, 1):
        note = "below-knee amputation with partial foot on the other side"
        return {}, {43: note, 44: note}, None
    if (hi, lo) == (1, 0):
        return {}, {44: "partial foot (Lisfranc) is listed as a CME for F57; confirm it applies to class 44"}, None
    return {}, {}, "bilateral partial-foot deficiency"


def _upper_standing(hi: int, lo: int) -> Outcome:
    if (hi, lo) == (2, 2):
        return {45: "bilateral amputation through or above the elbow"}, {}, None
    if (hi, lo) == (2, 0):
        return {46: "unilateral amputation through or above the elbow"}, {}, None
    if (hi, lo) == (1, 1):
        return {46: "bilateral wrist-level deficiency"}, {}, None
    if (hi, lo) == (2, 1):
        note = "elbow-level deficiency on one side and wrist-level on the other, between classes 45 and 46"
        return {}, {45: note, 46: note}, None
    return {47: "unilateral wrist-level deficiency"}, {}, None  # (1, 0)


def _lower_prosthesis(hi: int, lo: int) -> Outcome:
    if (hi, lo) == (3, 3):
        return {61: "bilateral above-knee amputation"}, {}, None
    if (hi, lo) == (2, 2):
        return {62: "bilateral below-knee amputation"}, {}, None
    if (hi, lo) == (3, 0):
        return {63: "unilateral amputation through or above the knee"}, {}, None
    if (hi, lo) == (2, 0):
        return {64: "unilateral below-knee amputation"}, {}, None
    if (hi, lo) == (3, 2):
        note = "above-knee on one side and below-knee on the other; classifier decides between 61 and 62"
        return {}, {61: note, 62: note}, None
    return {}, {}, "partial-foot involvement combined with prosthesis use"


def _from_outcome(specs: Sequence[ClassSpec], outcome: Outcome, default_reason: str) -> dict[int, Verdict]:
    meets, borderline, review = outcome
    if review:
        return uniform(specs, Status.NEEDS_REVIEW, review)
    return resolve(specs, meets, borderline, default_reason)


def _standing_amputation(profile: Profile, specs: Sequence[ClassSpec]) -> dict[int, Verdict]:
    lower, upper, missing = _levels(profile)
    if missing:
        return uniform(specs, Status.INSUFFICIENT_DATA, "amputation levels incomplete", missing)
    if lower[0] and upper[0]:
        return uniform(specs, Status.NEEDS_REVIEW, "combined upper and lower limb deficiency")
    if lower[0]:
        outcome = _lower_standing(*lower)
    elif upper[0]:
        outcome = _upper_standing(*upper)
    else:
        return uniform(specs, Status.NOT_MET, "no amputation level recorded on any limb")
    return _from_outcome(specs, outcome, "amputation pattern does not match this class")


ANKLE_MEASURES = ("ankle_pf_mrc", "ankle_rom_deg", "leg_length_diff_cm")


def ankle_cmes(profile: Profile) -> list[str]:
    """Minimum eligibility criteria for the ankle / leg-length pathway that the profile meets."""
    cmes = []
    if profile.ankle_pf_mrc is not None and profile.ankle_pf_mrc <= 2:
        cmes.append(f"plantar flexion strength grade {profile.ankle_pf_mrc} (<= 2)")
    if profile.ankle_rom_deg is not None and profile.ankle_rom_deg <= 10:
        cmes.append(f"ankle passive arc of {profile.ankle_rom_deg} degrees (<= 10)")
    if profile.leg_length_diff_cm is not None and profile.leg_length_diff_cm >= 7:
        cmes.append(f"leg length difference of {profile.leg_length_diff_cm} cm (>= 7)")
    return cmes


def _standing_strength_rom(profile: Profile, specs: Sequence[ClassSpec]) -> dict[int, Verdict]:
    cmes = ankle_cmes(profile)
    measures = ANKLE_MEASURES
    missing = tuple(m for m in measures if getattr(profile, m) is None)
    borderline = {}
    if profile.hip_knee_deficit:
        borderline[42] = "hip/knee deficit needs technical assessment (running, jumping tests)"

    if cmes:
        sides = profile.lower_limb_sides_affected
        text = "CME met: " + "; ".join(cmes)
        if sides == 2:
            return uniform(specs, Status.NEEDS_REVIEW, text + "; bilateral involvement")
        if sides == 1:
            return resolve(specs, {44: text}, borderline)
        borderline[44] = text + "; number of affected sides not provided"
        return resolve(specs, borderline=borderline, missing=("lower_limb_sides_affected",))
    if borderline:
        return resolve(specs, borderline=borderline)
    if len(missing) == len(measures):
        return uniform(specs, Status.INSUFFICIENT_DATA, "no ankle or leg-length measure provided", missing)
    return uniform(specs, Status.NOT_MET, "no minimum eligibility criterion met on the provided measures", missing)


def evaluate_limb_standing(profile: Profile, specs: Sequence[ClassSpec]) -> dict[int, Verdict]:
    gate = posture_gate(
        profile, specs, Posture.STANDING, "classes 42-47 compete standing and without prosthesis"
    )
    if gate is not None:
        return gate
    results = []
    if Impairment.LIMB_DEFICIENCY in profile.impairments:
        results.append(_standing_amputation(profile, specs))
    if profile.impairments & _MCE_IMPAIRMENTS:
        results.append(_standing_strength_rom(profile, specs))
    return merge(results)


def evaluate_limb_prosthesis(profile: Profile, specs: Sequence[ClassSpec]) -> dict[int, Verdict]:
    gate = posture_gate(
        profile, specs, Posture.PROSTHESIS, "classes 61-64 compete standing with a prosthesis"
    )
    if gate is not None:
        return gate
    lower, upper, missing = _levels(profile)
    if missing:
        return uniform(specs, Status.INSUFFICIENT_DATA, "amputation levels incomplete", missing)
    if upper[0]:
        return uniform(specs, Status.NEEDS_REVIEW, "upper limb deficiency combined with prosthesis use")
    if not lower[0]:
        return uniform(specs, Status.NOT_MET, "classes 61-64 require a lower limb deficiency")
    return _from_outcome(specs, _lower_prosthesis(*lower), "amputation pattern does not match this class")
