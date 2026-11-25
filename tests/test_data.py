import numpy as np
import pandas as pd

from para_triage.data import (
    FEATURE_NAMES,
    NoiseConfig,
    encode_profiles,
    generate_dataset,
    observe,
    profile_to_record,
    record_to_profile,
)
from para_triage.data.sampling import SAMPLERS, TARGETS
from para_triage.rules import (
    Impairment,
    LowerLimbLevel,
    Posture,
    Profile,
    Sex,
    UpperLimbLevel,
)


def test_balanced_rows_per_label():
    df = generate_dataset(n_per_label=15, seed=1)
    counts = df.groupby(["group", "label"]).size()
    for group, targets in TARGETS.items():
        for label in targets:
            assert counts[(group, label)] == 15


def test_generation_is_deterministic():
    a = generate_dataset(n_per_label=5, seed=3)
    b = generate_dataset(n_per_label=5, seed=3)
    pd.testing.assert_frame_equal(a, b)


def test_without_noise_the_rules_recover_every_label():
    df = generate_dataset(n_per_label=20, seed=2, noise=NoiseConfig.none())
    assert (df.rule_label == df.label).all()


def test_with_noise_the_rules_baseline_is_imperfect_and_may_abstain():
    df = generate_dataset(n_per_label=40, seed=2)
    assert (df.rule_label != df.label).any()
    assert (df.rule_label == -2).any()


def test_ambiguous_rows_list_candidates():
    df = generate_dataset(n_per_label=10, seed=4, groups=["limb_prosthesis"])
    mixed = df[df.label == -1]
    assert len(mixed) == 10
    assert set(mixed.candidates) <= {"61|62", ""}


def test_missing_fields_are_none_after_observation():
    cfg = NoiseConfig(missing_p={"height_cm": 1.0})
    profile = SAMPLERS["short_stature"](np.random.default_rng(0))
    assert observe(profile, np.random.default_rng(0), cfg).height_cm is None


def test_visual_form_never_loses_both_measures():
    cfg = NoiseConfig(missing_p={"logmar_best_eye": 1.0, "visual_field_deg": 1.0})
    rng = np.random.default_rng(0)
    for _ in range(20):
        seen = observe(SAMPLERS["visual"](rng), rng, cfg)
        assert seen.logmar_best_eye is not None or seen.visual_field_deg is not None


def test_record_round_trip_through_csv(tmp_path):
    df = generate_dataset(n_per_label=8, seed=5)
    path = tmp_path / "d.csv"
    df.to_csv(path, index=False)
    back = pd.read_csv(path)
    original = [record_to_profile(r) for r in df.to_dict("records")]
    restored = [record_to_profile(r) for r in back.to_dict("records")]
    assert original == restored


def test_record_round_trip_in_memory():
    p = Profile(
        sex=Sex.FEMALE,
        impairments=frozenset({Impairment.LIMB_DEFICIENCY}),
        posture=Posture.PROSTHESIS,
        lower_left=LowerLimbLevel.BELOW_KNEE,
        lower_right=LowerLimbLevel.NONE,
        upper_left=UpperLimbLevel.WRIST,
        upper_right=UpperLimbLevel.NONE,
        hip_knee_deficit=False,
    )
    assert record_to_profile(profile_to_record(p)) == p


def test_encoding_shapes_and_masks():
    p = Profile(impairments=frozenset({Impairment.VISUAL}), logmar_best_eye=1.2)
    x, m = encode_profiles([p, p])
    assert x.shape == m.shape == (2, len(FEATURE_NAMES))
    names = list(FEATURE_NAMES)
    assert m[0, names.index("logmar_best_eye")] == 1
    assert m[0, names.index("visual_field_deg")] == 0
    assert x[0, names.index("impairment_visual")] == 1
    assert (x[m == 0] == 0).all()


def test_level_features_ignore_left_right_order():
    a = Profile(lower_left=LowerLimbLevel.BELOW_KNEE, lower_right=LowerLimbLevel.NONE,
                upper_left=UpperLimbLevel.NONE, upper_right=UpperLimbLevel.NONE)
    b = Profile(lower_left=LowerLimbLevel.NONE, lower_right=LowerLimbLevel.BELOW_KNEE,
                upper_left=UpperLimbLevel.NONE, upper_right=UpperLimbLevel.NONE)
    xa, _ = encode_profiles([a])
    xb, _ = encode_profiles([b])
    assert (xa == xb).all()
