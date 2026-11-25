"""Baselines for the paper: rules with imputation, and gradient boosting on the same inputs."""
from __future__ import annotations

import dataclasses
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier

from ..data.generator import rule_label
from ..data.records import PROFILE_COLUMNS
from ..rules import Profile, RuleEngine

_SKIP = {"impairments", "age"}
_FIELDS = tuple(f for f in PROFILE_COLUMNS if f not in _SKIP)
_ROUNDED = {"iq", "ankle_pf_mrc", "lower_limb_sides_affected"}


def _key(profile: Profile) -> tuple:
    return tuple(sorted(i.value for i in profile.impairments))


class RuleImputer:
    """Fills a missing field with the training value typical of profiles that declare the same impairments.

    The median for numbers and the most frequent value for categories and flags, over the training rows
    where the field was recorded. A field never recorded for an impairment set (it does not apply there)
    stays missing. Nothing observed is changed.
    """

    def fit(self, profiles: Sequence[Profile]) -> "RuleImputer":
        seen: dict[tuple, dict[str, list]] = defaultdict(lambda: defaultdict(list))
        for p in profiles:
            for name in _FIELDS:
                value = getattr(p, name)
                if value is not None:
                    seen[_key(p)][name].append(value)
        self.fill: dict[tuple, dict[str, object]] = {}
        for key, fields in seen.items():
            self.fill[key] = {}
            for name, values in fields.items():
                if isinstance(values[0], (bool, np.bool_)) or hasattr(values[0], "value"):
                    self.fill[key][name] = Counter(values).most_common(1)[0][0]
                else:
                    med = float(np.median(values))
                    self.fill[key][name] = int(round(med)) if name in _ROUNDED else med
        return self

    def transform(self, profile: Profile) -> Profile:
        fill = self.fill.get(_key(profile), {})
        changes = {n: v for n, v in fill.items() if getattr(profile, n) is None}
        return dataclasses.replace(profile, **changes) if changes else profile


def imputed_rule_labels(imputer: RuleImputer, profiles: Sequence[Profile], engine: RuleEngine | None = None) -> np.ndarray:
    engine = engine or RuleEngine()
    return np.array([rule_label(engine.evaluate(imputer.transform(p))) for p in profiles])


def nan_features(x: np.ndarray, m: np.ndarray) -> np.ndarray:
    """Gradient boosting reads a missing field as NaN, which carries the mask."""
    return np.where(m > 0, x, np.nan)


@dataclass(frozen=True)
class GbConfig:
    max_iter: int = 100
    learning_rate: float = 0.1
    max_leaf_nodes: int = 15
    l2_regularization: float = 0.0


def fit_gb(x: np.ndarray, m: np.ndarray, y_idx: np.ndarray, cfg: GbConfig, seed: int) -> HistGradientBoostingClassifier:
    model = HistGradientBoostingClassifier(
        max_iter=cfg.max_iter,
        learning_rate=cfg.learning_rate,
        max_leaf_nodes=cfg.max_leaf_nodes,
        l2_regularization=cfg.l2_regularization,
        early_stopping=False,
        random_state=seed,
    )
    return model.fit(nan_features(x, m), y_idx)


def gb_proba(model: HistGradientBoostingClassifier, x: np.ndarray, m: np.ndarray, n_classes: int) -> np.ndarray:
    """Probabilities over all `n_classes` (a class absent from training gets zero)."""
    out = np.zeros((len(x), n_classes))
    out[:, model.classes_] = model.predict_proba(nan_features(x, m))
    return out
