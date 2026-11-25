"""Classification and calibration metrics."""
from __future__ import annotations

import numpy as np
from sklearn.metrics import f1_score


def accuracy(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float((y_true == y_pred).mean()) if len(y_true) else float("nan")


def macro_f1(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(f1_score(y_true, y_pred, labels=np.unique(y_true), average="macro", zero_division=0))


def nll(proba: np.ndarray, y_idx: np.ndarray) -> float:
    return float(-np.log(proba[np.arange(len(y_idx)), y_idx] + 1e-12).mean())


def brier(proba: np.ndarray, y_idx: np.ndarray) -> float:
    onehot = np.zeros_like(proba)
    onehot[np.arange(len(y_idx)), y_idx] = 1.0
    return float(((proba - onehot) ** 2).sum(axis=1).mean())


def ece(proba: np.ndarray, y_idx: np.ndarray, n_bins: int = 15) -> float:
    """Expected calibration error on the top-1 confidence."""
    conf = proba.max(axis=1)
    correct = (proba.argmax(axis=1) == y_idx).astype(float)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    total = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        in_bin = (conf > lo) & (conf <= hi)
        if in_bin.any():
            total += in_bin.mean() * abs(correct[in_bin].mean() - conf[in_bin].mean())
    return float(total)


def top_k_accuracy(proba: np.ndarray, y_idx: np.ndarray, k: int = 2) -> float:
    top = np.argsort(-proba, axis=1)[:, :k]
    return float((top == y_idx[:, None]).any(axis=1).mean())
