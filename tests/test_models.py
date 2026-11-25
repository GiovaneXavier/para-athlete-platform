import numpy as np
import pytest

from para_triage.data import generate_dataset
from para_triage.eval import metrics
from para_triage.eval.compare import compare
from para_triage.models import Standardizer, TrainConfig, fit_temperature, softmax
from para_triage.models.train import aggregate, prepare, run_once, split


@pytest.fixture(scope="module")
def small_df():
    return generate_dataset(n_per_label=24, seed=7)


def test_standardizer_keeps_missing_entries_at_zero():
    x = np.array([[1.0, 5.0], [3.0, 0.0], [5.0, 9.0]], dtype=np.float32)
    m = np.array([[1, 1], [1, 0], [1, 1]], dtype=np.float32)
    out = Standardizer().fit(x, m).transform(x, m)
    assert out[1, 1] == 0.0
    assert abs(out[:, 0].mean()) < 1e-6  # fitted on observed entries only


def test_split_is_stratified_and_disjoint(small_df):
    train, val, test = split(small_df, seed=0)
    assert len(set(train) | set(val) | set(test)) == len(small_df)
    assert not (set(train) & set(test)) and not (set(val) & set(test))
    for part in (train, val, test):
        assert set(small_df.iloc[part]["label"]) == set(small_df["label"])


def test_metrics_on_toy_cases():
    proba = np.array([[0.9, 0.1], [0.6, 0.4], [0.2, 0.8]])
    y = np.array([0, 1, 1])
    assert metrics.accuracy(y, proba.argmax(1)) == pytest.approx(2 / 3)
    assert metrics.top_k_accuracy(proba, y, 2) == 1.0
    assert metrics.brier(proba, y) > 0
    assert 0 <= metrics.ece(proba, y) <= 1


def test_temperature_softens_an_overconfident_model():
    rng = np.random.default_rng(0)
    y = rng.integers(0, 3, 600)
    logits = rng.normal(size=(600, 3)) * 3
    logits[np.arange(600), y] += 3.0  # right about 80% of the time but very sharp
    t = fit_temperature(logits.astype(np.float32), y)
    assert t > 1.0
    assert metrics.nll(softmax(logits, t), y) < metrics.nll(softmax(logits), y)


def test_pipeline_end_to_end_beats_chance_and_returns_valid_probabilities(small_df):
    prepared = prepare(small_df)
    result, artifacts = run_once(small_df, TrainConfig(epochs=15, seed=1), prepared)
    n_classes = len(artifacts["classes"])
    assert result["overall"]["mlp"]["accuracy"] > 3 / n_classes
    assert 0.2 < result["temperature"] < 5.0
    for key in ("rules", "mlp", "hybrid"):
        assert 0 <= result["overall"][key]["accuracy"] <= 1


def test_compare_hybrid_falls_back_to_mlp_when_rules_abstain(small_df):
    classes = np.sort(small_df["label"].unique())
    proba = np.zeros((len(small_df), len(classes)))
    proba[np.arange(len(small_df)), np.searchsorted(classes, small_df["label"])] = 1.0  # oracle MLP
    result = compare(small_df, proba, classes)
    assert result["overall"]["mlp"]["accuracy"] == 1.0
    assert result["overall"]["hybrid"]["accuracy"] >= result["overall"]["rules"]["accuracy"]


def test_aggregate_reports_mean_and_std():
    agg = aggregate([{"a": {"x": 1.0}}, {"a": {"x": 3.0}}])
    assert agg["a"]["x"]["mean"] == 2.0
    assert agg["a"]["x"]["std"] == pytest.approx(2 ** 0.5)
