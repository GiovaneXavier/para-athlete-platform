from para_triage.rules import (
    Impairment as I,
    LowerLimbLevel as L,
    Posture,
    Profile,
    RuleEngine,
    Sex,
    Status,
    UpperLimbLevel as U,
)
from para_triage.rules.catalog import load_catalog

engine = RuleEngine()


def run(*impairments, **fields):
    return engine.evaluate(Profile(impairments=frozenset(impairments), **fields))


# --- catalog -----------------------------------------------------------------


def test_catalog_has_33_classes_with_known_evaluators():
    from para_triage.rules.evaluators import EVALUATORS

    catalog = load_catalog()
    assert len(catalog.classes) == 33
    assert {g.evaluator for g in catalog.groups.values()} <= set(EVALUATORS)
    assert all(c.group in catalog.groups for c in catalog.classes.values())


def test_class_codes():
    assert engine.class_codes(44) == ("T44", "F44")
    assert engine.class_codes(40) == ("F40",)
    assert engine.class_codes(47) == ("T47",)
    assert engine.class_codes(57) == ("T54", "F57")  # seated classes: F number differs from T
    assert engine.class_codes(54) == ("T53", "F54")


def test_no_impairment_declared_means_nothing_applicable():
    result = run()
    assert result.candidates == []
    assert {v.status for v in result.verdicts.values()} == {Status.NOT_APPLICABLE}


# --- visual -----------------------------------------------------------------


def test_visual_by_acuity():
    assert run(I.VISUAL, logmar_best_eye=2.8, visual_field_deg=90).primary_class == 11
    assert run(I.VISUAL, logmar_best_eye=2.6, visual_field_deg=90).primary_class == 12
    assert run(I.VISUAL, logmar_best_eye=1.5, visual_field_deg=90).primary_class == 12
    assert run(I.VISUAL, logmar_best_eye=1.0, visual_field_deg=90).primary_class == 13


def test_visual_worst_measure_wins():
    assert run(I.VISUAL, logmar_best_eye=1.1, visual_field_deg=5).primary_class == 12


def test_visual_gap_is_borderline():
    result = run(I.VISUAL, logmar_best_eye=1.45, visual_field_deg=90)
    assert result.primary_class is None
    assert result.verdicts[12].status is Status.BORDERLINE
    assert result.verdicts[13].status is Status.BORDERLINE


def test_visual_above_limits_is_not_eligible():
    result = run(I.VISUAL, logmar_best_eye=0.3, visual_field_deg=90)
    assert result.candidates == []
    assert result.verdicts[13].status is Status.NOT_MET


def test_visual_one_measure_missing():
    assert run(I.VISUAL).verdicts[11].status is Status.INSUFFICIENT_DATA
    only_field = run(I.VISUAL, visual_field_deg=30)
    assert only_field.primary_class == 13
    assert "logmar_best_eye" in only_field.verdicts[13].missing
    assert run(I.VISUAL, logmar_best_eye=0.3).verdicts[11].status is Status.INSUFFICIENT_DATA


# --- intellectual --------------------------------------------------------------


def test_intellectual():
    full = dict(iq=70, adaptive_limitation=True, onset_before_22=True)
    assert run(I.INTELLECTUAL, **full).primary_class == 20
    assert run(I.INTELLECTUAL, **{**full, "iq": 76}).verdicts[20].status is Status.NOT_MET
    assert run(I.INTELLECTUAL, iq=70).verdicts[20].status is Status.INSUFFICIENT_DATA


# --- short stature ---------------------------------------------------------------


def test_short_stature_sum_is_the_binding_limit():
    male = dict(sex=Sex.MALE, posture=Posture.STANDING)
    assert run(I.SHORT_STATURE, height_cm=125, longest_arm_cm=55, **male).primary_class == 40  # sum 180
    assert run(I.SHORT_STATURE, height_cm=126, longest_arm_cm=55, **male).primary_class == 41  # sum 181
    assert run(I.SHORT_STATURE, height_cm=146, longest_arm_cm=50, **male).candidates == []


def test_short_stature_female_limits():
    female = dict(sex=Sex.FEMALE)
    assert run(I.SHORT_STATURE, height_cm=120, longest_arm_cm=53, **female).primary_class == 40  # sum 173
    assert run(I.SHORT_STATURE, height_cm=120, longest_arm_cm=54, **female).primary_class == 41  # sum 174


def test_short_stature_requires_all_measures():
    result = run(I.SHORT_STATURE, sex=Sex.MALE, height_cm=120)
    assert result.verdicts[40].status is Status.INSUFFICIENT_DATA
    assert result.verdicts[40].missing == ("longest_arm_cm",)


# --- limb deficiency, standing -----------------------------------------------------


def standing(lower=(L.NONE, L.NONE), upper=(U.NONE, U.NONE), **fields):
    return run(
        I.LIMB_DEFICIENCY,
        posture=Posture.STANDING,
        lower_left=lower[0],
        lower_right=lower[1],
        upper_left=upper[0],
        upper_right=upper[1],
        **fields,
    )


def test_standing_lower_limb_classes():
    assert standing(lower=(L.THROUGH_OR_ABOVE_KNEE, L.NONE)).primary_class == 42
    assert standing(lower=(L.BELOW_KNEE, L.BELOW_KNEE)).primary_class == 43
    assert standing(lower=(L.NONE, L.BELOW_KNEE)).primary_class == 44


def test_standing_upper_limb_classes():
    assert standing(upper=(U.ELBOW_OR_ABOVE, U.ELBOW_OR_ABOVE)).primary_class == 45
    assert standing(upper=(U.NONE, U.ELBOW_OR_ABOVE)).primary_class == 46
    assert standing(upper=(U.WRIST, U.WRIST)).primary_class == 46
    assert standing(upper=(U.WRIST, U.NONE)).primary_class == 47


def test_standing_mixed_patterns_are_borderline_or_review():
    mixed = standing(lower=(L.BELOW_KNEE, L.PARTIAL_FOOT))
    assert mixed.primary_class is None
    assert mixed.candidates == [43, 44]
    both = standing(lower=(L.BELOW_KNEE, L.NONE), upper=(U.WRIST, U.NONE))
    assert both.verdicts[44].status is Status.NEEDS_REVIEW


def test_standing_requires_levels_for_all_limbs():
    result = run(I.LIMB_DEFICIENCY, posture=Posture.STANDING, lower_left=L.BELOW_KNEE)
    assert result.verdicts[44].status is Status.INSUFFICIENT_DATA
    assert "upper_left" in result.verdicts[44].missing


def test_standing_ankle_cme_pathway():
    base = dict(posture=Posture.STANDING, lower_limb_sides_affected=1)
    assert run(I.MUSCLE_POWER, ankle_pf_mrc=2, **base).primary_class == 44
    assert run(I.ROM, ankle_rom_deg=10, **base).primary_class == 44
    assert run(I.LEG_LENGTH_DIFFERENCE, leg_length_diff_cm=7, **base).primary_class == 44
    assert run(I.LEG_LENGTH_DIFFERENCE, leg_length_diff_cm=6.9, **base).candidates == []
    bilateral = run(I.MUSCLE_POWER, ankle_pf_mrc=1, posture=Posture.STANDING, lower_limb_sides_affected=2)
    assert bilateral.verdicts[43].status is Status.NEEDS_REVIEW


def test_standing_classes_exclude_other_postures():
    result = run(
        I.LIMB_DEFICIENCY,
        posture=Posture.PROSTHESIS,
        lower_left=L.BELOW_KNEE,
        lower_right=L.NONE,
        upper_left=U.NONE,
        upper_right=U.NONE,
    )
    assert result.verdicts[44].status is Status.NOT_MET
    assert result.primary_class == 64


# --- limb deficiency, prosthesis -------------------------------------------------------


def prosthesis(lower):
    return run(
        I.LIMB_DEFICIENCY,
        posture=Posture.PROSTHESIS,
        lower_left=lower[0],
        lower_right=lower[1],
        upper_left=U.NONE,
        upper_right=U.NONE,
    )


def test_prosthesis_classes():
    above, below, none = L.THROUGH_OR_ABOVE_KNEE, L.BELOW_KNEE, L.NONE
    assert prosthesis((above, above)).primary_class == 61
    assert prosthesis((below, below)).primary_class == 62
    assert prosthesis((above, none)).primary_class == 63
    assert prosthesis((none, below)).primary_class == 64


def test_prosthesis_mixed_above_and_below_knee_is_borderline():
    result = prosthesis((L.THROUGH_OR_ABOVE_KNEE, L.BELOW_KNEE))
    assert result.primary_class is None
    assert result.candidates == [61, 62]


def test_prosthesis_requires_posture():
    result = run(I.LIMB_DEFICIENCY, lower_left=L.BELOW_KNEE)
    assert result.verdicts[64].status is Status.INSUFFICIENT_DATA
    assert result.verdicts[64].missing == ("posture",)
