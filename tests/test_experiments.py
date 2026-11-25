import dataclasses
import json

import numpy as np
import pandas as pd
import pytest

from para_triage.data import NoiseConfig, generate_dataset
from para_triage.data.generator import ABSTAIN, sample_true_profiles
from para_triage.experiments import protocol as P
from para_triage.experiments.baselines import GbConfig, RuleImputer, fit_gb, gb_proba, imputed_rule_labels
from para_triage.experiments.evaluate import evaluate
from para_triage.rules import Impairment, Profile


@pytest.fixture(scope="module")
def true():
    return sample_true_profiles(n_per_label=8, seed=5)


@pytest.fixture(scope="module")
def true_big():
    return sample_true_profiles(n_per_label=40, seed=5)  # enough rows per stratum for a 60/10/15/15 split


def test_scaled_noise_keeps_default_and_none_as_special_cases():
    base = NoiseConfig()
    assert base.scaled(1, 1) == base
    clean = base.scaled(0, 0)
    assert set(clean.missing_p.values()) == {0.0}
    assert dataclasses.replace(clean, missing_p={}) == NoiseConfig.none()


def test_scaled_noise_multiplies_scales_and_caps_probabilities():
    cfg = NoiseConfig().scaled(noise=2, missing=2)
    assert cfg.logmar_sd == pytest.approx(0.10)
    assert cfg.mrc_shift_p == pytest.approx(0.16)
    assert cfg.missing_p["ankle_rom_deg"] == pytest.approx(0.40)
    assert max(NoiseConfig().scaled(missing=100).missing_p.values()) == 1.0
    with pytest.raises(ValueError):
        NoiseConfig().scaled(-1, 1)


def test_noise_and_missing_axes_are_independent():
    only_missing = NoiseConfig().scaled(noise=0, missing=1)
    assert only_missing.logmar_sd == 0 and only_missing.missing_p == NoiseConfig().missing_p


def test_true_profiles_depend_only_on_the_seed(true):
    again = sample_true_profiles(n_per_label=8, seed=5)
    assert again.profiles == true.profiles
    assert (again.labels == true.labels).all()
    assert not (sample_true_profiles(n_per_label=8, seed=6).labels == true.labels).all()


def test_views_share_profiles_and_labels_whatever_the_noise(true):
    a = P.make_view(true, seed=5, cell=(0.0, 0.0))
    b = P.make_view(true, seed=5, cell=(2.0, 2.0))
    assert (a.df["label"] == b.df["label"]).all() and (a.df["group"] == b.df["group"]).all()
    assert (a.df["impairments"] == b.df["impairments"]).all()
    assert not a.df.equals(b.df)


def test_a_view_is_reproducible_and_cells_have_their_own_stream(true):
    one = P.make_view(true, seed=5, cell=(1.0, 1.0)).df
    two = P.make_view(true, seed=5, cell=(1.0, 1.0)).df
    pd.testing.assert_frame_equal(one, two)
    other_cell = P.make_view(true, seed=5, cell=(1.0, 2.0)).df
    assert not one.equals(other_cell)


def test_clean_view_has_nothing_missing_and_the_rules_are_exact(true):
    clean = P.make_view(true, seed=5, cell=P.CLEAN_CELL)
    assert (clean.df["rule_label"] == clean.df["label"]).all()


def test_more_missing_fields_mean_more_rule_abstentions(true):
    abstain = {
        mult: (P.make_view(true, 5, (0.0, mult)).df["rule_label"] == ABSTAIN).mean() for mult in (0.0, 1.0, 2.0)
    }
    assert abstain[0.0] == 0 and abstain[1.0] < abstain[2.0]


def test_split4_is_a_stratified_partition_with_the_stated_sizes(true_big):
    true = true_big
    split = P.split4(true.groups, true.labels, seed=0)
    n = len(true)
    assert sum(len(v) for v in split.values()) == n
    assert len(set().union(*map(set, split.values()))) == n
    for name, share in zip(("train", "val", "cal", "test"), P.SPLIT):
        assert abs(len(split[name]) / n - share) < 0.03
    assert set(true.labels[split["test"]]) == set(true.labels[split["train"]])


def test_split_depends_only_on_groups_labels_and_seed(true_big):
    true = true_big
    a = P.split4(true.groups, true.labels, seed=1)
    b = P.split4(list(true.groups), list(true.labels), seed=1)
    assert all((a[k] == b[k]).all() for k in a)


def test_imputer_fills_only_missing_fields_of_the_same_impairment_set(true):
    view = P.make_view(true, seed=5, cell=(0.0, 2.0))
    imputer = RuleImputer().fit(view.profiles)
    for seen in view.profiles:
        filled = imputer.transform(seen)
        for name in ("logmar_best_eye", "height_cm", "iq", "arm_function"):
            if getattr(seen, name) is not None:
                assert getattr(filled, name) == getattr(seen, name)
    visual = Profile(impairments=frozenset({Impairment.VISUAL}), logmar_best_eye=None)
    assert imputer.transform(visual).logmar_best_eye is not None
    assert imputer.transform(visual).height_cm is None  # does not apply to visual profiles


def test_imputed_rules_abstain_less_than_plain_rules(true):
    view = P.make_view(true, seed=5, cell=(0.0, 2.0))
    imputer = RuleImputer().fit(view.profiles)
    imputed = imputed_rule_labels(imputer, view.profiles)
    assert (imputed == ABSTAIN).mean() < (view.df["rule_label"] == ABSTAIN).mean()


def test_gradient_boosting_returns_probabilities_over_all_classes(true):
    view = P.make_view(true, seed=5, cell=(1.0, 1.0))
    classes = np.unique(true.labels)
    y = np.searchsorted(classes, true.labels)
    model = fit_gb(view.x, view.m, y, GbConfig(max_iter=5), seed=0)
    proba = gb_proba(model, view.x, view.m, len(classes))
    assert proba.shape == (len(view.x), len(classes))
    np.testing.assert_allclose(proba.sum(1), 1.0, atol=1e-6)


def test_evaluate_scores_each_system_and_the_hybrid_falls_back_to_the_model():
    classes = np.array([11, 12])
    y = np.array([11, 12, 12, 11])
    rules = np.array([11, ABSTAIN, 11, 11])
    p_mlp = np.array([[0.9, 0.1], [0.2, 0.8], [0.3, 0.7], [0.6, 0.4]])
    rows, extras, by_group = evaluate(y, np.array(["a", "a", "b", "b"]), classes, rules, rules, p_mlp, p_mlp)
    by_name = {r["system"]: r for r in rows}
    assert by_name["rules"]["accuracy"] == 0.5 and by_name["rules"]["coverage"] == 0.75
    assert by_name["rules"]["accuracy_decided"] == pytest.approx(2 / 3)
    assert by_name["mlp"]["accuracy"] == 1.0 and by_name["hybrid"]["accuracy"] == 0.75
    assert extras["mlp_accuracy_rules_abstain"] == 1.0
    assert {g["group"] for g in by_group} == {"a", "b"}


def test_legacy_generator_is_unchanged_by_the_new_streams():
    a = generate_dataset(n_per_label=3, seed=9)
    b = generate_dataset(n_per_label=3, seed=9)
    pd.testing.assert_frame_equal(a, b)


def test_e1_smoke_writes_results_for_matched_and_mismatched_cells(tmp_path, monkeypatch):
    from para_triage.experiments import e1
    from para_triage.models.mlp import TrainConfig

    monkeypatch.setattr(e1, "MLP_GRID", (TrainConfig(hidden=(16,), epochs=2), TrainConfig(hidden=(8,), epochs=2)))
    monkeypatch.setattr(e1, "GB_GRID", (GbConfig(max_iter=3),))
    cells = [(0.0, 0.0), (1.0, 1.0), (1.0, 2.0)]
    e1.run_seed(0, tmp_path, cells, n_per_label=40)

    res = pd.read_csv(tmp_path / "seed_0" / "results.csv")
    keys = res[["train_noise", "train_missing", "test_noise", "test_missing"]].drop_duplicates()
    assert len(keys) == 3 + 3 + 1  # trained at (0,0) and (1,1): all three test cells; (1,2): itself only
    assert set(res.system) == {"rules", "rules_imp", "gb", "mlp", "hybrid"}
    clean = res[(res.test_noise == 0) & (res.test_missing == 0) & (res.system == "rules")]
    assert (clean.accuracy == 1.0).all()  # built-in ceiling: no noise, nothing missing
    assert (tmp_path / "seed_0" / "mlp_default.pt").exists() and (tmp_path / "seed_0" / "tuning.json").exists()


def test_e7_smoke_reuses_e1_and_writes_selective_and_conformal_outputs(tmp_path, monkeypatch):
    from para_triage.experiments import e1, e7
    from para_triage.models.mlp import TrainConfig

    monkeypatch.setattr(e1, "MLP_GRID", (TrainConfig(hidden=(16,), epochs=2),))
    monkeypatch.setattr(e1, "GB_GRID", (GbConfig(max_iter=3),))
    monkeypatch.setattr(e7, "GB_GRID", e1.GB_GRID)
    cells = [(0.0, 0.0), (1.0, 1.0), (1.0, 2.0)]
    e1.run_seed(0, tmp_path / "e1", cells, n_per_label=40)
    e1.aggregate(tmp_path / "e1", [0])
    e7.run_seed(0, tmp_path / "e1", tmp_path / "e7", n_splits=2, n_per_label=40, cells=cells)

    seed_dir = tmp_path / "e7" / "seed_0"
    sanity = json.loads((seed_dir / "sanity.json").read_text())
    assert all(v["match"] for v in sanity.values())  # the same models as E1
    marginal = pd.read_csv(seed_dir / "marginal.csv")
    assert set(marginal.model) == {"mlp", "gb"} and {"LAC", "APS", "LAC_Mondrian"} <= set(marginal.method)
    main_cell = marginal[(marginal.cal_noise == 1) & (marginal.cal_missing == 1) & (marginal.test_noise == 1) & (marginal.test_missing == 1)]
    assert len(main_cell) > 0 and main_cell.coverage.between(0, 1).all()
    shifted = marginal[(marginal.test_missing == 2) & (marginal.cal_missing == 1)]
    assert len(shifted) > 0  # calibrated at (1, 1), tested elsewhere
    summary = pd.read_csv(seed_dir / "selective_summary.csv")
    assert set(summary.method) == {"mlp_maxprob", "mlp_margin", "gb_maxprob", "gb_margin"}
    cond = pd.read_csv(seed_dir / "conditional.csv")
    assert {"group", "class", "missing_fields"} <= set(cond.by)
