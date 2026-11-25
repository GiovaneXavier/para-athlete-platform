"""Missing-not-at-random fields: the chance that a field is not recorded depends on the case.

The default generator (`noise.observe`) drops every field independently with a fixed probability (MCAR).
Here the probability for field f in row i is

    p_f * m_i / mean(m_i over the rows that have the field),    capped at 1,

where p_f is the field's MCAR rate (already multiplied by the missing-field multiplier) and m_i depends on
the case. Dividing by the mean keeps each field's marginal missing rate at p_f, so a difference with MCAR
comes from the mechanism and not from the rate. The cap can break that when p_f * m_i / mean > 1; the
realized rate and the share of capped rows are reported per field (`MissingReport`).

Mechanisms:
  label       m_i = 1 - s when the label is ambiguous (-1), else 1: borderline cases are measured thoroughly
              and clear ones are not. The mask then carries information about the label.
  value_up    m_i = 1 + s (2 z_i - 1), z_i the mid-rank ECDF of the field's true value: high values go missing
              more often.
  value_down  the same with z_i replaced by 1 - z_i.
Fields without a natural order (sex, posture, cerebral palsy distribution) keep m_i = 1 in the value
mechanisms. `s` is the strength, between 0 and 1.
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ..rules import Profile

KINDS = ("label", "value_up", "value_down")
AMBIGUOUS = -1


@dataclass(frozen=True)
class MissingMechanism:
    kind: str
    strength: float

    def __post_init__(self):
        if self.kind not in KINDS:
            raise ValueError(f"unknown mechanism {self.kind!r}; use one of {KINDS}")
        if not 0 <= self.strength <= 1:
            raise ValueError("strength must be between 0 and 1")

    @property
    def name(self) -> str:
        return f"{self.kind}_{self.strength:g}"


@dataclass
class MissingReport:
    """Per field: target rate, mean probability after the cap, realized rate, share of rows that hit the cap."""

    rows: list[dict] = field(default_factory=list)

    def frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.rows)


def _ordered_value(value):
    """A number for a field with a natural order, None otherwise (sex, posture, cp distribution)."""
    if isinstance(value, (bool, int, float, np.integer, np.floating)):
        return float(value)
    return None


def case_multipliers(mech: MissingMechanism, values: list, labels: np.ndarray) -> np.ndarray:
    """m_i for the rows that have the field (`values` are their true values, in order)."""
    n = len(values)
    if mech.kind == "label":
        return np.where(labels == AMBIGUOUS, 1.0 - mech.strength, 1.0)
    ordered = [_ordered_value(v) for v in values]
    if any(o is None for o in ordered):
        return np.ones(n)
    z = (pd.Series(ordered).rank(method="average").to_numpy() - 0.5) / n
    if mech.kind == "value_down":
        z = 1.0 - z
    return 1.0 + mech.strength * (2.0 * z - 1.0)


def apply_mechanism(
    observed: list[Profile],
    true_profiles: list[Profile],
    labels: np.ndarray,
    base_p: dict[str, float],
    mech: MissingMechanism,
    rng: np.random.Generator,
    report: MissingReport | None = None,
) -> list[Profile]:
    """Drops fields from `observed` (noisy but complete) with the mechanism's probabilities."""
    drops: list[dict] = [dict() for _ in observed]
    for name, p_f in base_p.items():
        rows = [i for i, p in enumerate(true_profiles) if getattr(p, name) is not None and getattr(observed[i], name) is not None]
        if not rows or p_f <= 0:
            if report is not None and rows:
                report.rows.append({"field": name, "rows": len(rows), "target": p_f, "mean_probability": 0.0, "realized": 0.0, "clipped_share": 0.0})
            continue
        m = case_multipliers(mech, [getattr(true_profiles[i], name) for i in rows], labels[rows])
        raw = p_f * m / m.mean()
        p = np.clip(raw, 0.0, 1.0)
        dropped = rng.random(len(rows)) < p
        for i, d in zip(rows, dropped):
            if d:
                drops[i][name] = None
        if report is not None:
            report.rows.append(
                {"field": name, "rows": len(rows), "target": p_f, "mean_probability": float(p.mean()),
                 "realized": float(dropped.mean()), "clipped_share": float((raw > 1.0).mean())}
            )
    out = []
    for profile, drop in zip(observed, drops):
        if {"logmar_best_eye", "visual_field_deg"} <= drop.keys():
            del drop["visual_field_deg"]  # a visual form always has at least one measure, as in noise.observe
        out.append(dataclasses.replace(profile, **drop) if drop else profile)
    return out
