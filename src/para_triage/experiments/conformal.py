"""Selective prediction and split conformal prediction on class probabilities.

All functions take probabilities `p` of shape (n, n_classes) and true class indices `y`. They are
model-agnostic: the same code scores the MLP and gradient boosting.

Conformal sets have a *marginal* guarantee, Pr[y in C] >= 1 - alpha, when the calibration and test
rows are exchangeable. They do not guarantee the accuracy of the singleton sets, nor coverage
conditional on group, class or number of missing fields; `coverage_by` measures those.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

# ------------------------------------------------------------------ selective prediction


def max_prob(p: np.ndarray) -> np.ndarray:
    return p.max(axis=1)


def margin(p: np.ndarray) -> np.ndarray:
    top2 = -np.sort(-p, axis=1)[:, :2]
    return top2[:, 0] - top2[:, 1]


def risk_coverage(confidence: np.ndarray, correct: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Selective accuracy after answering the k most confident rows, for k = 1..n.

    Returns (coverage, selective accuracy); ties are kept in input order (stable sort).
    """
    order = np.argsort(-confidence, kind="stable")
    hits = np.cumsum(correct[order].astype(float))
    k = np.arange(1, len(confidence) + 1)
    return k / len(confidence), hits / k


def aurc(confidence: np.ndarray, correct: np.ndarray) -> float:
    """Area under the risk-coverage curve (mean selective error over coverage); lower is better."""
    _, acc = risk_coverage(confidence, correct)
    return float((1.0 - acc).mean())


def selective_accuracy_at(confidence: np.ndarray, correct: np.ndarray, coverage: float) -> float:
    """Accuracy on the ceil(coverage * n) most confident rows."""
    cov, acc = risk_coverage(confidence, correct)
    k = max(1, int(math.ceil(coverage * len(confidence) - 1e-9)))
    return float(acc[k - 1])


# ------------------------------------------------------------------ split conformal


def conformal_quantile(scores: np.ndarray, alpha: float) -> float:
    """The ceil((n + 1)(1 - alpha)) / n empirical quantile; infinite if there are too few scores."""
    n = len(scores)
    k = math.ceil((n + 1) * (1 - alpha))
    if k > n:
        return float("inf")
    return float(np.sort(scores)[k - 1])


def lac_scores(p: np.ndarray) -> np.ndarray:
    """Score of every (row, class): 1 - p. Smaller means a better fit."""
    return 1.0 - p


def aps_scores(p: np.ndarray) -> np.ndarray:
    """Non-randomized adaptive scores: mass of the classes at least as likely as this one, itself included."""
    order = np.argsort(-p, axis=1, kind="stable")
    cum = np.cumsum(np.take_along_axis(p, order, axis=1), axis=1)
    out = np.empty_like(cum)
    np.put_along_axis(out, order, cum, axis=1)
    return out


SCORERS = {"LAC": lac_scores, "APS": aps_scores}


def conformal_sets(
    p_cal: np.ndarray, y_cal: np.ndarray, p_test: np.ndarray, alpha: float, method: str = "LAC", per_class: bool = False
) -> np.ndarray:
    """Boolean (n_test, n_classes) membership matrix.

    `per_class=True` is Mondrian conformal: one threshold per true class, so coverage holds within
    each class (needs enough calibration rows per class).
    """
    score = SCORERS[method.removesuffix("_Mondrian")]
    s_cal = score(p_cal)[np.arange(len(y_cal)), y_cal]
    s_test = score(p_test)
    if not per_class:
        return s_test <= conformal_quantile(s_cal, alpha)
    q = np.full(p_test.shape[1], np.inf)
    for c in np.unique(y_cal):
        q[c] = conformal_quantile(s_cal[y_cal == c], alpha)
    return s_test <= q[None, :]


def set_metrics(sets: np.ndarray, y: np.ndarray, ambiguous_idx: int | None) -> dict:
    """Summary of conformal sets against the true class indices.

    The *singleton* share counts every set with one class. The *decided* share excludes a singleton
    that is the ambiguous label, which means "send to the specialist"; its complement is the
    referral rate (empty, several classes, or the ambiguous label).
    """
    n = len(y)
    size = sets.sum(axis=1)
    covered = sets[np.arange(n), y]
    singleton = size == 1
    has_amb = sets[:, ambiguous_idx] if ambiguous_idx is not None else np.zeros(n, dtype=bool)
    decided = singleton & ~has_amb
    only = sets.argmax(axis=1)
    return {
        "coverage": float(covered.mean()),
        "size": float(size.mean()),
        "frac_singleton": float(singleton.mean()),
        "frac_decided": float(decided.mean()),
        "frac_empty": float((size == 0).mean()),
        "frac_has_ambiguous": float(has_amb.mean()),
        "singleton_accuracy": float((only[singleton] == y[singleton]).mean()) if singleton.any() else float("nan"),
        "decided_accuracy": float((only[decided] == y[decided]).mean()) if decided.any() else float("nan"),
    }


def coverage_by(sets: np.ndarray, y: np.ndarray, keys: dict[str, np.ndarray]) -> pd.DataFrame:
    """Coverage and mean set size within each value of each key (group, class, missing-field band...)."""
    covered = sets[np.arange(len(y)), y]
    size = sets.sum(axis=1)
    frames = []
    for name, values in keys.items():
        frame = pd.DataFrame({"covered": covered, "size": size, "value": values})
        agg = frame.groupby("value").agg(coverage=("covered", "mean"), size=("size", "mean"), n=("covered", "size"))
        agg = agg.reset_index()
        agg.insert(0, "by", name)
        frames.append(agg)
    return pd.concat(frames, ignore_index=True)


def conformal_sets_by_group(
    p_cal: np.ndarray, y_cal: np.ndarray, g_cal: np.ndarray, p_test: np.ndarray, g_test: np.ndarray, alpha: float, method: str = "LAC"
) -> np.ndarray:
    """Conformal sets with one threshold per group (here: a band of observed missing fields).

    Coverage holds within each group under exchangeability inside that group. A group with too few
    calibration rows gets an infinite threshold, which is the set of all classes.
    """
    score = SCORERS[method]
    s_cal = score(p_cal)[np.arange(len(y_cal)), y_cal]
    s_test = score(p_test)
    q = np.array([conformal_quantile(s_cal[g_cal == g], alpha) if (g_cal == g).any() else float("inf") for g in g_test])
    return s_test <= q[:, None]
