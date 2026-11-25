from para_triage.rules import (
    ArmFunction as A,
    CpDistribution as D,
    Impairment as I,
    LegFunction as Leg,
    Posture,
    Profile,
    Propulsion as P,
    RuleEngine,
    Severity as S,
    Status,
    TrunkFunction as T,
)

engine = RuleEngine()


def run(*impairments, **fields):
    return engine.evaluate(Profile(impairments=frozenset(impairments), **fields))


def neuro(*impairments, posture, **fields):
    return run(*impairments, posture=posture, brain_impairment_report=True, **fields)


# --- brain impairment, seated -------------------------------------------------------------------


def test_seated_neuro_follows_the_propulsion_pattern():
    base = dict(posture=Posture.SEATED, neuro_severity=S.SEVERE, cp_distribution=D.QUADRIPLEGIA)
    assert neuro(I.HYPERTONIA, chair_propulsion=P.FEET, **base).primary_class == 31
    assert neuro(I.ATHETOSIS, chair_propulsion=P.ARMS_IMPAIRED, **base).primary_class == 32
    assert neuro(I.HYPERTONIA, chair_propulsion=P.ARMS_ASYMMETRIC, **base).primary_class == 33


def test_class_34_is_for_spastic_diplegia_with_symmetric_propulsion():
    base = dict(posture=Posture.SEATED, neuro_severity=S.MODERATE, chair_propulsion=P.ARMS_SYMMETRIC)
    assert neuro(I.HYPERTONIA, cp_distribution=D.DIPLEGIA, **base).primary_class == 34
    other = neuro(I.HYPERTONIA, cp_distribution=D.TRIPLEGIA, **base)
    assert other.candidates == [33, 34]
    athetoid = neuro(I.ATHETOSIS, cp_distribution=D.DIPLEGIA, **base)
    assert athetoid.candidates == [33]


def test_neuro_requires_report_and_posture():
    no_report = run(I.HYPERTONIA, posture=Posture.SEATED, brain_impairment_report=False, chair_propulsion=P.FEET)
    assert no_report.verdicts[31].status is Status.NOT_MET
    unknown = run(I.HYPERTONIA, posture=Posture.SEATED, chair_propulsion=P.FEET)
    assert unknown.verdicts[31].status is Status.INSUFFICIENT_DATA
    assert unknown.verdicts[31].missing == ("brain_impairment_report",)
    assert run(I.HYPERTONIA, brain_impairment_report=True).verdicts[31].missing == ("posture",)


# --- brain impairment, standing -------------------------------------------------------------------


def standing(*impairments, **fields):
    return neuro(*impairments, posture=Posture.STANDING, **fields)


def test_standing_neuro_classes():
    assert standing(I.ATHETOSIS, neuro_severity=S.MODERATE).primary_class == 36
    assert standing(I.ATAXIA, I.ATHETOSIS, neuro_severity=S.MODERATE).primary_class == 36
    assert standing(I.HYPERTONIA, neuro_severity=S.MODERATE, cp_distribution=D.HEMIPLEGIA).primary_class == 37
    assert standing(I.HYPERTONIA, neuro_severity=S.MODERATE, cp_distribution=D.DIPLEGIA).primary_class == 35
    assert standing(I.ATHETOSIS, neuro_severity=S.MILD).primary_class == 38
    assert standing(I.HYPERTONIA, neuro_severity=S.MILD, cp_distribution=D.HEMIPLEGIA).primary_class == 38


def test_standing_neuro_ambiguous_and_review_cases():
    mild_diplegia = standing(I.HYPERTONIA, neuro_severity=S.MILD, cp_distribution=D.DIPLEGIA)
    assert mild_diplegia.candidates == [35, 38]
    mixed = standing(I.HYPERTONIA, I.ATHETOSIS, neuro_severity=S.MODERATE, cp_distribution=D.HEMIPLEGIA)
    assert mixed.candidates == [36, 37]
    assert standing(I.HYPERTONIA, neuro_severity=S.SEVERE).verdicts[37].status is Status.NEEDS_REVIEW
    quad = standing(I.HYPERTONIA, neuro_severity=S.MODERATE, cp_distribution=D.QUADRIPLEGIA)
    assert quad.verdicts[35].status is Status.NEEDS_REVIEW
    missing = standing(I.HYPERTONIA, neuro_severity=S.MODERATE)
    assert missing.verdicts[35].missing == ("cp_distribution",)


# --- Petra --------------------------------------------------------------------------------------------


def petra(**fields):
    return neuro(I.HYPERTONIA, posture=Posture.FRAME_RUNNER, neuro_severity=S.SEVERE, **fields)


def test_petra_classes_depend_on_independent_transfer():
    assert petra(transfers_independently=False, walks_short_distances=False).primary_class == 71
    assert petra(transfers_independently=True, trunk_straps_needed=False).primary_class == 72


def test_petra_contradictory_answers_are_borderline():
    assert petra(transfers_independently=False, walks_short_distances=True).candidates == [71, 72]
    assert petra(transfers_independently=True, trunk_straps_needed=True).candidates == [71, 72]


def test_petra_needs_a_severe_gait_impairment():
    mild = neuro(I.ATHETOSIS, posture=Posture.FRAME_RUNNER, neuro_severity=S.MILD, transfers_independently=True)
    assert mild.candidates == []
    assert mild.verdicts[72].status is Status.NOT_MET
    assert petra().verdicts[71].missing == ("transfers_independently",)


# --- seated physical classes --------------------------------------------------------------------------


def seated(arm, trunk, leg=None, impairment=I.MUSCLE_POWER, **fields):
    return run(impairment, posture=Posture.SEATED, arm_function=arm, trunk_function=trunk, leg_function=leg, **fields)


def test_seated_classes_follow_arm_trunk_and_leg_function():
    assert seated(A.SHOULDER_ELBOW_DEFICIT, T.NONE).primary_class == 51
    assert seated(A.FINGER_DEFICIT, T.NONE).primary_class == 52
    assert seated(A.INTRINSIC_ONLY, T.NONE).primary_class == 53
    assert seated(A.PRESERVED, T.NONE).primary_class == 54
    assert seated(A.PRESERVED, T.PARTIAL, Leg.HIP_FLEXORS_ONLY).primary_class == 55
    assert seated(A.PRESERVED, T.FULL, Leg.NONE).primary_class == 55
    assert seated(A.PRESERVED, T.FULL, Leg.HIP_AND_KNEE).primary_class == 56
    assert seated(A.PRESERVED, T.FULL, Leg.ANKLE_LEVEL).primary_class == 57


def test_seated_class_57_checks_the_ankle_criteria():
    assert seated(A.PRESERVED, T.FULL, Leg.ANKLE_LEVEL, ankle_pf_mrc=2).primary_class == 57
    no_cme = seated(A.PRESERVED, T.FULL, Leg.ANKLE_LEVEL, ankle_pf_mrc=4)
    assert no_cme.verdicts[57].status is Status.BORDERLINE
    assert seated(A.PRESERVED, T.FULL, Leg.NORMAL).candidates == []


def test_seated_inconsistent_or_incomplete_inputs():
    assert seated(A.FINGER_DEFICIT, T.FULL).verdicts[52].status is Status.NEEDS_REVIEW
    assert seated(A.PRESERVED, T.FULL).verdicts[56].missing == ("leg_function",)
    assert run(I.MUSCLE_POWER, posture=Posture.SEATED).verdicts[51].status is Status.INSUFFICIENT_DATA


def test_seated_classes_exclude_other_postures():
    standing_athlete = run(
        I.MUSCLE_POWER, posture=Posture.STANDING, arm_function=A.PRESERVED, trunk_function=T.NONE
    )
    assert standing_athlete.verdicts[54].status is Status.NOT_MET
