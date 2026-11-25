"""PROVISIONAL evaluators for classes defined by functional profiles.

Covers brain impairment (31-38, 71-72) and seated physical classes (51-57). The
booklet describes these classes qualitatively, so the decision tables below are my
reading of it, expressed through a few ordinal descriptors. They are meant to be
replaced or refined with the criteria matrix from the domain specialist; every
choice that is not literally in the booklet is listed in docs/rules_coverage.md.
"""
from __future__ import annotations

from collections.abc import Sequence

from ..catalog import ClassSpec
from ..schema import (
    ArmFunction,
    CpDistribution,
    Impairment,
    LegFunction,
    Posture,
    Profile,
    Propulsion,
    Severity,
    Status,
    TrunkFunction,
    Verdict,
)
from .base import resolve, uniform
from .limb import ANKLE_MEASURES, ankle_cmes

_NEURO_TYPES = {Impairment.HYPERTONIA, Impairment.ATAXIA, Impairment.ATHETOSIS}


def _brain_gate(profile: Profile, specs: Sequence[ClassSpec]) -> dict[int, Verdict] | None:
    if profile.brain_impairment_report is None:
        return uniform(
            specs, Status.INSUFFICIENT_DATA, "neurological report status not provided", ("brain_impairment_report",)
        )
    if not profile.brain_impairment_report:
        return uniform(specs, Status.NOT_MET, "a neurological report proving brain impairment is required")
    return None


# --- brain impairment, classes 31-38 ---------------------------------------------------------


def evaluate_neuro(profile: Profile, specs: Sequence[ClassSpec]) -> dict[int, Verdict]:
    if profile.posture is None:
        return uniform(specs, Status.INSUFFICIENT_DATA, "competition posture not provided", ("posture",))
    seated = [s for s in specs if Posture.SEATED in s.postures]
    standing = [s for s in specs if Posture.STANDING in s.postures]
    if profile.posture not in (Posture.SEATED, Posture.STANDING):
        return uniform(specs, Status.NOT_MET, "classes 31-38 compete seated or standing")
    gate = _brain_gate(profile, specs)
    if gate is not None:
        return gate

    types = profile.impairments & _NEURO_TYPES
    if profile.posture is Posture.SEATED:
        out = _neuro_seated(profile, seated, types)
        out.update(uniform(standing, Status.NOT_MET, "classes 35-38 compete standing"))
    else:
        out = _neuro_standing(profile, standing, types)
        out.update(uniform(seated, Status.NOT_MET, "classes 31-34 compete seated"))
    return out


def _neuro_seated(profile: Profile, specs: Sequence[ClassSpec], types: set[Impairment]) -> dict[int, Verdict]:
    prop = profile.chair_propulsion
    if prop is None:
        return uniform(specs, Status.INSUFFICIENT_DATA, "racing-wheelchair propulsion not described", ("chair_propulsion",))
    if profile.neuro_severity is Severity.NONE:
        return uniform(specs, Status.NOT_MET, "no functional impact recorded")
    if profile.neuro_severity is Severity.MILD:
        return uniform(specs, Status.NEEDS_REVIEW, "mild impairment but competing seated")

    if prop is Propulsion.FEET:
        return resolve(specs, {31: "propels the racing wheelchair with the feet"})
    if prop is Propulsion.ARMS_IMPAIRED:
        return resolve(specs, {32: "propels with the arms despite severe to moderate upper-limb impairment"})
    if prop is Propulsion.ARMS_ASYMMETRIC:
        return resolve(specs, {33: "asymmetric or low-power arm propulsion"})

    # symmetric, powerful propulsion: class 34 is described for spastic diplegia only
    if types == {Impairment.HYPERTONIA}:
        dist = profile.cp_distribution
        if dist is CpDistribution.DIPLEGIA:
            return resolve(specs, {34: "symmetric propulsion with spastic diplegia"})
        note = "symmetric propulsion with hypertonia, but the distribution is not diplegia"
        if dist is None:
            return resolve(specs, borderline={34: note + " (not provided)"}, missing=("cp_distribution",))
        return resolve(specs, borderline={33: note, 34: note})
    note = "symmetric propulsion is atypical with athetosis/ataxia; the booklet describes class 34 for hypertonia only"
    return resolve(specs, borderline={33: note})


def _neuro_standing(profile: Profile, specs: Sequence[ClassSpec], types: set[Impairment]) -> dict[int, Verdict]:
    severity, dist = profile.neuro_severity, profile.cp_distribution
    if severity is None:
        return uniform(specs, Status.INSUFFICIENT_DATA, "functional severity not provided", ("neuro_severity",))
    if severity is Severity.NONE:
        return uniform(specs, Status.NOT_MET, "no functional impact recorded")
    if severity is Severity.SEVERE:
        return uniform(specs, Status.NEEDS_REVIEW, "severe impairment while standing; seated classes may apply")

    hypertonia = Impairment.HYPERTONIA in types
    movement = bool(types & {Impairment.ATAXIA, Impairment.ATHETOSIS})
    if severity is Severity.MILD:
        if types == {Impairment.HYPERTONIA} and dist is CpDistribution.DIPLEGIA:
            note = "mild diplegia sits between class 35 and class 38"
            return resolve(specs, borderline={35: note, 38: note})
        return resolve(specs, {38: "minimal functional impact"})

    # moderate
    if not hypertonia:
        return resolve(specs, {36: "athetosis/ataxia with moderate functional impact"})
    if dist is None:
        return uniform(specs, Status.INSUFFICIENT_DATA, "distribution of hypertonia not provided", ("cp_distribution",))
    by_distribution = {CpDistribution.HEMIPLEGIA: 37, CpDistribution.DIPLEGIA: 35}
    cls = by_distribution.get(dist)
    if cls is None:
        return uniform(specs, Status.NEEDS_REVIEW, f"{dist.value} while standing; seated classes may apply")
    text = f"hypertonia with {dist.value}"
    if movement:
        note = text + " mixed with athetosis/ataxia"
        return resolve(specs, borderline={cls: note, 36: note})
    return resolve(specs, {cls: text})


# --- Petra, classes 71-72 -----------------------------------------------------------------------


def evaluate_frame_runner(profile: Profile, specs: Sequence[ClassSpec]) -> dict[int, Verdict]:
    if profile.posture is None:
        return uniform(specs, Status.INSUFFICIENT_DATA, "competition posture not provided", ("posture",))
    if profile.posture is not Posture.FRAME_RUNNER:
        return uniform(specs, Status.NOT_MET, "classes 71-72 compete with the Petra (frame runner)")
    gate = _brain_gate(profile, specs)
    if gate is not None:
        return gate
    if profile.neuro_severity is None:
        return uniform(specs, Status.INSUFFICIENT_DATA, "functional severity not provided", ("neuro_severity",))
    if profile.neuro_severity < Severity.MODERATE:
        return uniform(specs, Status.NOT_MET, "gait impairment is not severe enough for the Petra classes")
    if profile.transfers_independently is None:
        return uniform(
            specs, Status.INSUFFICIENT_DATA, "independent transfer to the Petra not recorded", ("transfers_independently",)
        )

    if not profile.transfers_independently:
        if profile.walks_short_distances:
            note = "cannot transfer independently but walks short distances"
            return resolve(specs, borderline={71: note, 72: note})
        return resolve(specs, {71: "cannot transfer to the Petra independently"})
    if profile.trunk_straps_needed:
        note = "transfers independently but needs trunk straps"
        return resolve(specs, borderline={71: note, 72: note})
    return resolve(specs, {72: "transfers to the Petra independently"})


# --- seated physical classes, 51-57 -----------------------------------------------------------------

_ARM_CLASS = {
    ArmFunction.SHOULDER_ELBOW_DEFICIT: (51, "deficit at shoulder, elbow extensors, wrist flexors and fingers"),
    ArmFunction.FINGER_DEFICIT: (52, "shoulder, elbow and wrist preserved; finger flexion and extension deficit"),
    ArmFunction.INTRINSIC_ONLY: (53, "only the intrinsic hand muscles are impaired"),
}


def evaluate_seated(profile: Profile, specs: Sequence[ClassSpec]) -> dict[int, Verdict]:
    if profile.posture is None:
        return uniform(specs, Status.INSUFFICIENT_DATA, "competition posture not provided", ("posture",))
    if profile.posture is not Posture.SEATED:
        return uniform(specs, Status.NOT_MET, "classes 51-57 compete seated")
    arm, trunk = profile.arm_function, profile.trunk_function
    missing = tuple(n for n, v in (("arm_function", arm), ("trunk_function", trunk)) if v is None)
    if missing:
        return uniform(specs, Status.INSUFFICIENT_DATA, "upper-limb or trunk function not provided", missing)

    if arm in _ARM_CLASS:
        cls, text = _ARM_CLASS[arm]
        if trunk is not TrunkFunction.NONE:
            return uniform(specs, Status.NEEDS_REVIEW, "arm-function deficit combined with trunk function is not described")
        return resolve(specs, {cls: f"{text}; no trunk function"})

    if trunk is TrunkFunction.NONE:
        return resolve(specs, {54: "arms preserved, no trunk function"})

    leg = profile.leg_function
    if leg is None:
        return uniform(specs, Status.INSUFFICIENT_DATA, "lower-limb function not provided", ("leg_function",))
    if leg in (LegFunction.NONE, LegFunction.HIP_FLEXORS_ONLY):
        return resolve(specs, {55: "trunk function present; legs limited to hip flexors at most"})
    if leg is LegFunction.HIP_AND_KNEE:
        return resolve(specs, {56: "active hip flexion/adduction and knee extension"})
    if leg is LegFunction.ANKLE_LEVEL:
        cmes = ankle_cmes(profile)
        if cmes:
            return resolve(specs, {57: "ankle-level impairment; CME met: " + "; ".join(cmes)})
        measured = [m for m in ANKLE_MEASURES if getattr(profile, m) is not None]
        if measured:
            return resolve(specs, borderline={57: "ankle-level impairment, but no ankle CME met on the provided measures"})
        return resolve(specs, {57: "ankle-level impairment (ankle CME not documented)"})
    return uniform(specs, Status.NOT_MET, "normal lower-limb function: no minimum eligibility criterion")
