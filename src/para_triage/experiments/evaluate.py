"""System-level metrics for one (train cell, test cell) evaluation.

Labels come from the same rules as the baseline, so these numbers measure fidelity to the rules
under corrupted inputs, not accuracy against official classifiers.
"""
from __future__ import annotations

import numpy as np

from ..data.generator import ABSTAIN
from ..eval import metrics

SYSTEMS = ("rules", "rules_imp", "gb", "mlp", "hybrid")
ABSTAINING = ("rules", "rules_imp")


def system_predictions(
    classes: np.ndarray, rules: np.ndarray, rules_imp: np.ndarray, p_mlp: np.ndarray, p_gb: np.ndarray
) -> dict[str, np.ndarray]:
    mlp = classes[p_mlp.argmax(1)]
    return {
        "rules": rules,
        "rules_imp": rules_imp,
        "gb": classes[p_gb.argmax(1)],
        "mlp": mlp,
        "hybrid": np.where(rules == ABSTAIN, mlp, rules),
    }


def evaluate(
    y: np.ndarray,
    groups: np.ndarray,
    classes: np.ndarray,
    rules: np.ndarray,
    rules_imp: np.ndarray,
    p_mlp: np.ndarray,
    p_gb: np.ndarray,
) -> tuple[list[dict], dict, list[dict]]:
    """Returns (rows per system, MLP extras, rows per system and group)."""
    y_idx = np.searchsorted(classes, y)
    preds = system_predictions(classes, rules, rules_imp, p_mlp, p_gb)
    rows = []
    for name, pred in preds.items():
        decided = pred != ABSTAIN if name in ABSTAINING else np.ones(len(y), dtype=bool)
        rows.append(
            {
                "system": name,
                "accuracy": metrics.accuracy(y, pred),
                "macro_f1": metrics.macro_f1(y, pred),
                "coverage": float(decided.mean()),
                "accuracy_decided": metrics.accuracy(y[decided], pred[decided]),
            }
        )

    decided = rules != ABSTAIN
    wrong = decided & (rules != y)
    mlp = preds["mlp"]
    extras = {
        "mlp_accuracy_rules_decided": metrics.accuracy(y[decided], mlp[decided]),
        "mlp_accuracy_rules_abstain": metrics.accuracy(y[~decided], mlp[~decided]),
        "mlp_accuracy_rules_wrong": metrics.accuracy(y[wrong], mlp[wrong]),
        "gb_accuracy_rules_abstain": metrics.accuracy(y[~decided], preds["gb"][~decided]),
        "mlp_top2": metrics.top_k_accuracy(p_mlp, y_idx, 2),
        "mlp_ece": metrics.ece(p_mlp, y_idx),
        "mlp_nll": metrics.nll(p_mlp, y_idx),
        "mlp_brier": metrics.brier(p_mlp, y_idx),
        "gb_nll": metrics.nll(np.clip(p_gb, 1e-12, 1.0), y_idx),
    }

    by_group = []
    for group in np.unique(groups):
        idx = np.where(groups == group)[0]
        for name, pred in preds.items():
            by_group.append({"system": name, "group": group, "accuracy": metrics.accuracy(y[idx], pred[idx]), "n": len(idx)})
    return rows, extras, by_group
