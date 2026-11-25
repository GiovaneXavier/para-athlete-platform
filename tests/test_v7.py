"""V7: observed missing fields and band-conditional outputs."""
import dataclasses

import numpy as np
import pandas as pd

from para_triage.rules import Impairment, Profile



# --- V7: observed missing fields -----------------------------------------------------------------------------


def test_observed_missing_count_uses_the_form_of_the_impairment_set_not_the_true_row():
    from para_triage.experiments import v7

    full = Profile(impairments=frozenset({Impairment.VISUAL}), logmar_best_eye=1.0, visual_field_deg=30.0)
    other = Profile(impairments=frozenset({Impairment.SHORT_STATURE}), height_cm=120.0, longest_arm_cm=50.0)
    expected = v7.expected_fields([full, other, full], [0, 1, 2])
    assert expected[("visual",)] == {"logmar_best_eye", "visual_field_deg"}
    seen_visual = dataclasses.replace(full, visual_field_deg=None)
    seen_stature = dataclasses.replace(other, height_cm=None, longest_arm_cm=None)
    counts = v7.observed_missing([full, seen_visual, seen_stature], expected)
    assert list(counts) == [0, 1, 2]
    # a field that does not apply to the set is never counted as missing
    assert v7.observed_missing([Profile(impairments=frozenset({Impairment.VISUAL}), logmar_best_eye=1.0, visual_field_deg=2.0)], expected)[0] == 0


def test_band_temperatures_only_reshape_the_bands_they_are_fitted_on():
    from para_triage.experiments import v7

    p = np.array([[0.9, 0.1], [0.8, 0.2], [0.7, 0.3], [0.6, 0.4]])
    bands = np.array(["0", "0", "1", "2+"])
    out = v7.apply_temperatures(p, bands, {"0": 1.0, "1+": 2.0})
    np.testing.assert_allclose(out[:2], p[:2])  # temperature 1 changes nothing
    assert (out[2:].max(1) < p[2:].max(1)).all()  # a larger temperature softens


def test_v7_smoke_writes_band_conditional_outputs(tiny_e1, monkeypatch):
    from para_triage.experiments import v7

    v7.run_seed(0, tiny_e1 / "v7", tiny_e1 / "e1", 40, 2, False)
    d = tiny_e1 / "v7" / "seed_0"
    marginal = pd.read_csv(d / "marginal.csv")
    assert set(marginal.method) == set(v7.METHODS) and set(marginal.model) == {"mlp", "gb"}
    by_band = pd.read_csv(d / "by_band.csv")
    assert {"observed", "true_profile"} <= set(by_band.by)
    agree = pd.read_csv(d / "agreement.csv")
    assert agree.agreement_observed_true_count.between(0, 1).all()
