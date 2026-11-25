"""Rules baseline vs MLP vs hybrid on one held-out split.

The rules baseline is the rule engine applied to the observed profile (the
`rule_label` column). When it abstains (-2) it counts as wrong. The hybrid keeps
the rules' answer when they decide and falls back to the MLP otherwise.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..data.generator import ABSTAIN
from . import metrics


def compare(test: pd.DataFrame, proba: np.ndarray, classes: np.ndarray) -> dict:
    y = test["label"].to_numpy()
    y_idx = np.searchsorted(classes, y)
    rules = test["rule_label"].to_numpy()
    mlp = classes[proba.argmax(axis=1)]
    hybrid = np.where(rules == ABSTAIN, mlp, rules)
    systems = {"rules": rules, "mlp": mlp, "hybrid": hybrid}

    decided = rules != ABSTAIN
    rules_wrong = decided & (rules != y)
    result: dict = {
        "overall": {
            name: {"accuracy": metrics.accuracy(y, pred), "macro_f1": metrics.macro_f1(y, pred)}
            for name, pred in systems.items()
        },
        "rules_coverage": float(decided.mean()),
        "rules_accuracy_when_decided": metrics.accuracy(y[decided], rules[decided]),
        "mlp_accuracy_when_rules_decided": metrics.accuracy(y[decided], mlp[decided]),
        "mlp_accuracy_when_rules_abstain": metrics.accuracy(y[~decided], mlp[~decided]),
        "mlp_accuracy_when_rules_wrong": metrics.accuracy(y[rules_wrong], mlp[rules_wrong]),
        "mlp_top2_accuracy": metrics.top_k_accuracy(proba, y_idx, 2),
        "mlp_calibration": {
            "nll": metrics.nll(proba, y_idx),
            "ece": metrics.ece(proba, y_idx),
            "brier": metrics.brier(proba, y_idx),
        },
        "by_group": {},
    }
    for group, idx in test.groupby("group").indices.items():
        result["by_group"][group] = {
            name: metrics.accuracy(y[idx], pred[idx]) for name, pred in systems.items()
        }
    return result
