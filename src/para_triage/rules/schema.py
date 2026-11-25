"""Input profile and verdict types for the rule engine.

Every Profile field defaults to None, meaning "not measured"; evaluators report
INSUFFICIENT_DATA instead of guessing.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, IntEnum


class Sex(str, Enum):
    MALE = "M"
    FEMALE = "F"


class Posture(str, Enum):
    STANDING = "standing"  # standing, no prosthesis
    SEATED = "seated"
    PROSTHESIS = "prosthesis"
    FRAME_RUNNER = "frame_runner"  # Petra


class Impairment(str, Enum):
    VISUAL = "visual"
    INTELLECTUAL = "intellectual"
    SHORT_STATURE = "short_stature"
    LIMB_DEFICIENCY = "limb_deficiency"
    MUSCLE_POWER = "muscle_power"
    ROM = "rom"  # impaired passive range of motion
    LEG_LENGTH_DIFFERENCE = "leg_length_difference"
    HYPERTONIA = "hypertonia"
    ATAXIA = "ataxia"
    ATHETOSIS = "athetosis"


class LowerLimbLevel(IntEnum):
    NONE = 0
    PARTIAL_FOOT = 1  # e.g. Lisfranc
    BELOW_KNEE = 2
    THROUGH_OR_ABOVE_KNEE = 3


class UpperLimbLevel(IntEnum):
    NONE = 0
    WRIST = 1  # through or above the wrist, below the elbow joint
    ELBOW_OR_ABOVE = 2  # through or above the elbow


class Severity(IntEnum):
    NONE = 0
    MILD = 1
    MODERATE = 2
    SEVERE = 3


class CpDistribution(str, Enum):
    QUADRIPLEGIA = "quadriplegia"
    TRIPLEGIA = "triplegia"
    HEMIPLEGIA = "hemiplegia"
    DIPLEGIA = "diplegia"


class Propulsion(IntEnum):
    """How the athlete propels a racing wheelchair (classes 31-34)."""

    FEET = 1
    ARMS_IMPAIRED = 2
    ARMS_ASYMMETRIC = 3
    ARMS_SYMMETRIC = 4


class ArmFunction(IntEnum):
    """Seated classes 51-54, from the booklet's upper-limb borderline descriptions."""

    SHOULDER_ELBOW_DEFICIT = 0  # deficits at shoulder, elbow extensors, wrist flexors, fingers
    FINGER_DEFICIT = 1  # shoulder, elbow, wrist preserved; finger flexion/extension at most grade 3
    INTRINSIC_ONLY = 2  # only the intrinsic hand muscles are impaired
    PRESERVED = 3


class TrunkFunction(IntEnum):
    NONE = 0
    PARTIAL = 1
    FULL = 2


class LegFunction(IntEnum):
    NONE = 0
    HIP_FLEXORS_ONLY = 1
    HIP_AND_KNEE = 2  # hip flexion/adduction, knee extension, knee flexors up to grade 3
    ANKLE_LEVEL = 3  # impairment limited to the ankle/foot level
    NORMAL = 4


@dataclass(frozen=True)
class Profile:
    sex: Sex | None = None
    age: int | None = None
    impairments: frozenset[Impairment] = frozenset()
    posture: Posture | None = None

    # Vision (best eye, best correction)
    logmar_best_eye: float | None = None
    visual_field_deg: float | None = None  # diameter, in degrees, as in the CPB booklet

    # Intellectual
    iq: int | None = None
    adaptive_limitation: bool | None = None
    onset_before_22: bool | None = None

    # Short stature
    height_cm: float | None = None
    longest_arm_cm: float | None = None  # acromion to longest finger, longest arm

    # Brain impairment (classes 31-38 and 71-72 require a neurological report)
    brain_impairment_report: bool | None = None
    neuro_severity: Severity | None = None  # overall functional impact on the sport movements
    cp_distribution: CpDistribution | None = None
    chair_propulsion: Propulsion | None = None  # seated neuro classes
    transfers_independently: bool | None = None  # Petra classes
    walks_short_distances: bool | None = None
    trunk_straps_needed: bool | None = None

    # Seated physical classes 51-57 (spinal cord injury, amputation, strength deficit...)
    arm_function: ArmFunction | None = None
    trunk_function: TrunkFunction | None = None
    leg_function: LegFunction | None = None

    # Limb deficiency, per side
    lower_left: LowerLimbLevel | None = None
    lower_right: LowerLimbLevel | None = None
    upper_left: UpperLimbLevel | None = None
    upper_right: UpperLimbLevel | None = None

    # Strength / ROM / length-difference pathway (lower limbs, worst affected side)
    ankle_pf_mrc: int | None = None  # plantar flexion strength, MRC 0-5
    ankle_rom_deg: float | None = None  # passive arc between dorsi- and plantar flexion
    leg_length_diff_cm: float | None = None
    hip_knee_deficit: bool | None = None
    lower_limb_sides_affected: int | None = None  # 1 or 2


class Status(str, Enum):
    MEETS = "meets"
    BORDERLINE = "borderline"
    NEEDS_REVIEW = "needs_review"  # rules cannot decide; expert judgement required
    INSUFFICIENT_DATA = "insufficient_data"
    NOT_MET = "not_met"
    NOT_APPLICABLE = "not_applicable"
    NOT_IMPLEMENTED = "not_implemented"


@dataclass(frozen=True)
class Verdict:
    class_id: int
    status: Status
    reasons: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()
