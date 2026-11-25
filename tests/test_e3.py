"""E3: natural sampler, prevalence scenarios and the E3 smoke run."""

import numpy as np
import pandas as pd
import pytest

from para_triage.data.generator import sample_natural_profiles
from para_triage.data.sampling import SAMPLERS, natural_ranges
from para_triage.experiments import e3



# --- natural sampler ------------------------------------------------------------------------------------------


def test_natural_ranges_switch_is_scoped_and_removes_the_mass_near_the_thresholds():
    def share_near_75(n=3000):
        rng = np.random.default_rng(0)
        return np.mean([abs(SAMPLERS["intellectual"](rng).iq - 75) <= 3 for _ in range(n)])

    default = share_near_75()
    with natural_ranges():
        natural = share_near_75()
    assert natural < 0.5 * default
    assert share_near_75() == pytest.approx(default)  # restored after the block


def test_natural_samples_are_not_balanced_and_are_reproducible():
    a, dropped = sample_natural_profiles(120, groups=["visual", "limb_standing"], seed=3)
    b, _ = sample_natural_profiles(120, groups=["visual", "limb_standing"], seed=3)
    assert a.profiles == b.profiles and dropped >= 0
    counts = pd.Series(a.labels[np.asarray(a.groups) == "visual"]).value_counts()
    assert counts.max() > 1.5 * counts.min()  # frequencies are whatever the rules give


# --- prevalence scenarios -------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def cells_df():
    groups = np.array(["a"] * 30 + ["b"] * 20)
    labels = np.array([0] * 10 + [11] * 10 + [-1] * 10 + [0] * 10 + [51] * 10)
    return groups, labels


@pytest.mark.parametrize("scenario", list(e3.SCENARIOS))
def test_target_weights_form_a_distribution(cells_df, scenario):
    groups, labels = cells_df
    groups = np.array(["limb_standing"] * 30 + ["visual"] * 20)
    w = e3.target_weights(groups, labels, scenario)
    assert sum(w.values()) == pytest.approx(1.0) and all(v > 0 for v in w.values())


def test_balanced_scenario_is_the_sampling_distribution_and_screening_favours_none(cells_df):
    groups, labels = cells_df
    groups = np.array(["limb_standing"] * 30 + ["visual"] * 20)
    np.testing.assert_allclose(e3.row_weights(groups, labels, "balanced"), 1.0)
    w = e3.row_weights(groups, labels, "screening")
    none_rows, other_rows = labels == 0, labels == 11
    assert w[none_rows & (groups == "limb_standing")].mean() == pytest.approx(5 * w[other_rows].mean())
    assert w.mean() == pytest.approx(1.0)


def test_reweighted_mean_matches_the_target_share(cells_df):
    groups, labels = cells_df
    groups = np.array(["limb_standing"] * 30 + ["visual"] * 20)
    for scenario in ("screening", "skewed_groups"):
        target = e3.target_weights(groups, labels, scenario)
        w = e3.row_weights(groups, labels, scenario)
        for (g, l), share in target.items():
            sel = (groups == g) & (labels == l)
            assert e3.wmean(sel.astype(float), w) == pytest.approx(share)


def test_e3_smoke(tiny_e1, monkeypatch):
    monkeypatch.setattr(e3, "NATURAL_ROWS_PER_GROUP", 25)
    e3.run_seed(0, tiny_e1 / "e3", tiny_e1 / "e1", 40, False)
    scenarios = pd.read_csv(tiny_e1 / "e3" / "seed_0" / "scenarios.csv")
    assert set(scenarios.scenario) == set(e3.SCENARIOS) and set(scenarios.system) == {"rules", "rules_imp", "gb", "mlp", "hybrid"}
    balanced = scenarios[(scenarios.scenario == "balanced") & (scenarios.system == "mlp")].accuracy.iloc[0]
    e1_res = pd.read_csv(tiny_e1 / "e1" / "results.csv")
    e1_acc = e1_res[(e1_res.train_noise == 1) & (e1_res.train_missing == 1) & (e1_res.test_noise == 1) & (e1_res.test_missing == 1) & (e1_res.system == "mlp")].accuracy.iloc[0]
    assert balanced == pytest.approx(e1_acc)  # the balanced scenario weights every row by 1
    natural = pd.read_csv(tiny_e1 / "e3" / "seed_0" / "natural.csv")
    assert "all" in set(natural.scope)
