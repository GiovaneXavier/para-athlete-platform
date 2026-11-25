"""E-MNAR: missing-not-at-random mechanisms and the E-MNAR smoke run."""
import json

import numpy as np
import pandas as pd
import pytest

from para_triage.data import NoiseConfig
from para_triage.data.generator import observe_samples, sample_true_profiles
from para_triage.data.missingness import MissingMechanism, MissingReport, apply_mechanism, case_multipliers
from para_triage.experiments import protocol as P
from para_triage.experiments.baselines import GbConfig
from para_triage.rules import Impairment, Profile



def heights(n=4000, seed=0):
    rng = np.random.default_rng(seed)
    values = rng.uniform(80, 170, n)
    profiles = [Profile(impairments=frozenset({Impairment.SHORT_STATURE}), height_cm=float(v)) for v in values]
    return profiles, values


# --- missing not at random ------------------------------------------------------------------------------------


def test_mechanism_rejects_unknown_kind_and_bad_strength():
    with pytest.raises(ValueError):
        MissingMechanism("sometimes", 0.5)
    with pytest.raises(ValueError):
        MissingMechanism("label", 1.5)


def test_label_mechanism_hides_fields_of_clear_cases_and_keeps_the_marginal_rate():
    profiles, _ = heights()
    labels = np.where(np.arange(len(profiles)) % 5 == 0, -1, 41)  # 20% borderline
    rng = np.random.default_rng(1)
    out = apply_mechanism(profiles, profiles, labels, {"height_cm": 0.3}, MissingMechanism("label", 0.9), rng)
    missing = np.array([p.height_cm is None for p in out])
    assert abs(missing.mean() - 0.3) < 0.02  # the marginal rate is the MCAR one
    assert missing[labels == -1].mean() < 0.4 * missing[labels != -1].mean()


def test_value_mechanisms_go_in_opposite_directions_and_keep_the_marginal_rate():
    profiles, values = heights()
    labels = np.full(len(profiles), 41)
    high = values > np.quantile(values, 0.75)
    low = values < np.quantile(values, 0.25)
    for kind, sign in (("value_up", 1), ("value_down", -1)):
        out = apply_mechanism(profiles, profiles, labels, {"height_cm": 0.3}, MissingMechanism(kind, 0.9), np.random.default_rng(2))
        missing = np.array([p.height_cm is None for p in out])
        assert abs(missing.mean() - 0.3) < 0.02
        assert sign * (missing[high].mean() - missing[low].mean()) > 0.2


def test_strength_zero_is_mcar_and_unordered_fields_are_left_alone():
    profiles = [Profile(impairments=frozenset({Impairment.VISUAL}), posture=None) for _ in range(10)]
    m = case_multipliers(MissingMechanism("value_up", 0.9), ["standing"] * 5, np.zeros(5))
    np.testing.assert_allclose(m, 1.0)  # posture has no natural order
    z = case_multipliers(MissingMechanism("value_up", 0.0), [1.0, 2.0, 3.0], np.zeros(3))
    np.testing.assert_allclose(z, 1.0)
    assert len(profiles) == 10


def test_the_report_shows_when_the_cap_breaks_the_marginal_rate():
    profiles, _ = heights(2000)
    labels = np.where(np.arange(len(profiles)) % 5 == 0, -1, 41)
    report = MissingReport()
    apply_mechanism(profiles, profiles, labels, {"height_cm": 0.9}, MissingMechanism("label", 0.9), np.random.default_rng(3), report)
    row = report.frame().iloc[0]
    assert row["clipped_share"] > 0.5 and row["mean_probability"] < row["target"] - 0.05
    assert row["realized"] < row["target"]


def test_mnar_views_are_reproducible_and_leave_the_labels_alone():
    true = sample_true_profiles(n_per_label=6, seed=5)
    mech = MissingMechanism("label", 0.9)
    a, _ = P.make_mnar_view(true, 5, mech, 1, 2.0)
    b, _ = P.make_mnar_view(true, 5, mech, 1, 2.0)
    pd.testing.assert_frame_equal(a.df, b.df)
    mcar = P.make_view(true, 5, (1.0, 2.0))
    assert (a.df["label"] == mcar.df["label"]).all()
    assert not a.df.equals(mcar.df)


def test_the_mcar_path_is_unchanged_by_the_mechanism_option():
    true = sample_true_profiles(n_per_label=4, seed=7)
    cfg = NoiseConfig()
    _, plain = observe_samples(true, cfg, np.random.default_rng(0))
    _, again = observe_samples(true, cfg, np.random.default_rng(0), mechanism=None)
    pd.testing.assert_frame_equal(plain, again)


def test_emnar_smoke(tiny_e1, monkeypatch):
    from para_triage.experiments import emnar

    monkeypatch.setattr(emnar, "REGIMES", (("mcar", None), ("label_0.9", MissingMechanism("label", 0.9))))
    monkeypatch.setattr(emnar, "MULTIPLIERS", (1.0, 2.0))
    monkeypatch.setattr(emnar, "MASK_GB", GbConfig(max_iter=3))
    emnar.run_seed(0, tiny_e1 / "emnar", tiny_e1 / "e1", 40, False)
    d = tiny_e1 / "emnar" / "seed_0"
    res = pd.read_csv(d / "results.csv")
    assert set(res.training) == {"matched", "mcar_1x"} and set(res.regime) == {"mcar", "label_0.9"}
    rates = pd.read_csv(d / "missing_rates.csv")
    assert {"target", "realized", "clipped_share"} <= set(rates.columns)
    mask = pd.read_csv(d / "mask_only.csv")
    assert set(mask.predictor) == {"group_only", "group_and_mask"}
    sanity = json.loads((d / "sanity.json").read_text())
    assert sanity["matches_e1"]  # the MCAR cell at (1, 1) reproduces E1
