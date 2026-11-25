import numpy as np
import pytest

from para_triage.experiments import conformal as C


def calibrated_draws(n, n_classes=6, seed=0):
    """Probabilities and labels drawn from those probabilities: a perfectly calibrated model."""
    rng = np.random.default_rng(seed)
    p = rng.dirichlet(np.full(n_classes, 0.3), size=n)
    y = np.array([rng.choice(n_classes, p=row) for row in p])
    return p, y


def test_quantile_index_and_too_few_scores():
    scores = np.arange(1.0, 10.0)  # n = 9
    assert C.conformal_quantile(scores, 0.1) == 9.0  # ceil(10 * 0.9) = 9
    assert C.conformal_quantile(np.arange(5.0), 0.1) == float("inf")  # ceil(6 * 0.9) = 6 > 5


@pytest.mark.parametrize("method", ["LAC", "APS"])
@pytest.mark.parametrize("alpha", [0.05, 0.1, 0.2])
def test_marginal_coverage_holds_on_exchangeable_data(method, alpha):
    p_cal, y_cal = calibrated_draws(2000, seed=1)
    p_test, y_test = calibrated_draws(20000, seed=2)
    sets = C.conformal_sets(p_cal, y_cal, p_test, alpha, method)
    cov = C.set_metrics(sets, y_test, None)["coverage"]
    assert cov >= 1 - alpha - 0.03  # guarantee, minus ~3 sd of the finite calibration set (n = 2000)
    assert cov <= 1 - alpha + 0.03  # and not wildly conservative


def test_mondrian_covers_every_class_not_only_on_average():
    p_cal, y_cal = calibrated_draws(6000, seed=3)
    p_test, y_test = calibrated_draws(30000, seed=4)
    sets = C.conformal_sets(p_cal, y_cal, p_test, 0.1, "LAC", per_class=True)
    per_class = C.coverage_by(sets, y_test, {"class": y_test})
    assert per_class["coverage"].min() >= 0.9 - 0.04


def test_smaller_alpha_gives_larger_sets():
    p_cal, y_cal = calibrated_draws(1000, seed=5)
    p_test, _ = calibrated_draws(1000, seed=6)
    for method in ("LAC", "APS"):
        tight = C.conformal_sets(p_cal, y_cal, p_test, 0.2, method)
        wide = C.conformal_sets(p_cal, y_cal, p_test, 0.05, method)
        assert (wide >= tight).all()


def test_aps_score_of_the_top_class_is_its_probability_and_the_total_is_one():
    p = np.array([[0.5, 0.3, 0.2], [0.1, 0.6, 0.3]])
    s = C.aps_scores(p)
    np.testing.assert_allclose(s[0], [0.5, 0.8, 1.0])
    np.testing.assert_allclose(s[1], [1.0, 0.6, 0.9])


def test_risk_coverage_on_a_toy_ranking():
    confidence = np.array([0.9, 0.8, 0.7, 0.6])
    correct = np.array([True, True, False, True])
    cov, acc = C.risk_coverage(confidence, correct)
    np.testing.assert_allclose(cov, [0.25, 0.5, 0.75, 1.0])
    np.testing.assert_allclose(acc, [1.0, 1.0, 2 / 3, 0.75])
    assert C.selective_accuracy_at(confidence, correct, 1.0) == pytest.approx(0.75)
    assert C.selective_accuracy_at(confidence, correct, 0.5) == pytest.approx(1.0)
    assert C.aurc(confidence, correct) == pytest.approx(1 - np.mean([1.0, 1.0, 2 / 3, 0.75]))


def test_a_better_ranking_has_a_lower_aurc():
    correct = np.array([True] * 8 + [False] * 2)
    good = np.linspace(1, 0, 10)  # errors ranked last
    bad = good[::-1]
    assert C.aurc(good, correct) < C.aurc(bad, correct)


def test_margin_is_top1_minus_top2():
    p = np.array([[0.5, 0.3, 0.2], [0.4, 0.4, 0.2]])
    np.testing.assert_allclose(C.margin(p), [0.2, 0.0])
    np.testing.assert_allclose(C.max_prob(p), [0.5, 0.4])


def test_set_metrics_separates_singletons_from_decided_and_flags_the_ambiguous_label():
    # classes: 0, 1, 2 (index 2 is the ambiguous label)
    sets = np.array(
        [
            [True, False, False],  # singleton, covers y=0
            [False, False, True],  # singleton {ambiguous}, covers y=2
            [True, True, False],  # two classes
            [False, False, False],  # empty
        ]
    )
    y = np.array([0, 2, 1, 0])
    m = C.set_metrics(sets, y, ambiguous_idx=2)
    assert m["coverage"] == pytest.approx(0.75)  # all but the empty set cover
    assert m["size"] == pytest.approx(1.0)
    assert m["frac_singleton"] == 0.5 and m["frac_decided"] == 0.25
    assert m["frac_empty"] == 0.25 and m["frac_has_ambiguous"] == 0.25
    assert m["singleton_accuracy"] == 1.0 and m["decided_accuracy"] == 1.0


def test_coverage_by_groups_rows():
    sets = np.array([[True, False], [False, True], [True, False], [True, False]])
    y = np.array([0, 0, 0, 1])
    out = C.coverage_by(sets, y, {"g": np.array(["a", "a", "b", "b"])})
    row = out.set_index("value")
    assert row.loc["a", "coverage"] == 0.5 and row.loc["b", "coverage"] == 0.5
    assert row.loc["a", "n"] == 2


def test_group_thresholds_give_coverage_inside_each_group():
    # two groups with very different confidence: one marginal threshold under-covers the hard one
    rng = np.random.default_rng(0)

    def draw(n, conc, seed):
        r = np.random.default_rng(seed)
        p = r.dirichlet(np.full(6, conc), size=n)
        y = np.array([r.choice(6, p=row) for row in p])
        return p, y

    p_easy, y_easy = draw(4000, 0.1, 1)
    p_hard, y_hard = draw(4000, 3.0, 2)
    # an overconfident model on the hard group: sharpen its probabilities without changing the labels
    p_hard = p_hard**3 / (p_hard**3).sum(1, keepdims=True)
    p = np.vstack([p_easy, p_hard])
    y = np.concatenate([y_easy, y_hard])
    g = np.array([0] * 4000 + [1] * 4000)
    idx = rng.permutation(len(y))
    cal, test = idx[:4000], idx[4000:]
    marginal = C.conformal_sets(p[cal], y[cal], p[test], 0.1, "LAC")
    by_group = C.conformal_sets_by_group(p[cal], y[cal], g[cal], p[test], g[test], 0.1, "LAC")
    cov_marginal = C.coverage_by(marginal, y[test], {"g": g[test]}).set_index("value").coverage
    cov_group = C.coverage_by(by_group, y[test], {"g": g[test]}).set_index("value").coverage
    assert cov_marginal.min() < 0.87  # the marginal guarantee hides the hard group
    assert cov_group.min() > 0.87 and cov_group.max() < 0.93


def test_a_group_with_too_few_calibration_rows_gets_the_full_set():
    p = np.array([[0.7, 0.3], [0.6, 0.4], [0.9, 0.1]])
    y = np.array([0, 0, 0])
    sets = C.conformal_sets_by_group(p, y, np.array([0, 0, 0]), p[:2], np.array([0, 1]), 0.1, "LAC")
    assert sets[1].all()  # group 1 has no calibration rows
