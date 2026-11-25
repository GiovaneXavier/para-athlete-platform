"""Synthetic dataset: true profile -> rule-engine label -> noisy observation.

The label comes from the rule engine applied to the *true* profile, while the
features are the *observed* profile (measurement error and missing fields). The
`rule_label` column is what the rule engine predicts from the observed profile,
i.e. the rules-only baseline under the same noise.

Label codes: a class id (11..72), 0 = no eligible class, -1 = ambiguous
(borderline or needs expert review), -2 = the rules abstain (rule_label only).
"""
from __future__ import annotations

import warnings
from collections.abc import Sequence
import dataclasses
from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..rules import EligibilityResult, Profile, RuleEngine, Status
from .missingness import MissingMechanism, MissingReport, apply_mechanism
from .noise import NoiseConfig, observe
from .records import profile_to_record
from .sampling import SAMPLERS, TARGETS, natural_ranges

NONE_ELIGIBLE = 0
AMBIGUOUS = -1
ABSTAIN = -2


def label_of(result: EligibilityResult) -> int | None:
    """Label for a fully specified profile, or None when the rules cannot decide it."""
    statuses = {v.status for v in result.verdicts.values()}
    if statuses & {Status.NOT_IMPLEMENTED, Status.INSUFFICIENT_DATA}:
        return None
    if statuses & {Status.BORDERLINE, Status.NEEDS_REVIEW}:
        return AMBIGUOUS
    meets = result.meets
    if len(meets) == 1:
        return meets[0]
    return NONE_ELIGIBLE if not meets else None


def rule_label(result: EligibilityResult) -> int:
    label = label_of(result)
    return ABSTAIN if label is None else label


def generate_dataset(
    n_per_label: int = 200,
    groups: Sequence[str] | None = None,
    seed: int = 0,
    noise: NoiseConfig | None = None,
    max_tries_per_row: int = 400,
) -> pd.DataFrame:
    """Balanced dataset: `n_per_label` rows for every target label of every group."""
    rng = np.random.default_rng(seed)
    noise = NoiseConfig() if noise is None else noise
    engine = RuleEngine()
    rows: list[dict] = []

    for group in groups or list(SAMPLERS):
        sampler, targets = SAMPLERS[group], TARGETS[group]
        counts = dict.fromkeys(targets, 0)
        budget = max_tries_per_row * n_per_label * len(targets)
        for _ in range(budget):
            if all(c >= n_per_label for c in counts.values()):
                break
            true = sampler(rng)
            result = engine.evaluate(true)
            label = label_of(result)
            if label not in counts or counts[label] >= n_per_label:
                continue
            counts[label] += 1
            seen = observe(true, rng, noise)
            row = profile_to_record(seen)
            row.update(
                group=group,
                label=label,
                candidates="|".join(str(c) for c in result.candidates),
                rule_label=rule_label(engine.evaluate(seen)),
            )
            rows.append(row)
        short = {k: v for k, v in counts.items() if v < n_per_label}
        if short:
            warnings.warn(f"group '{group}': could not reach {n_per_label} rows for labels {short}")

    return pd.DataFrame(rows)


@dataclass(frozen=True)
class TrueSamples:
    """True (noise-free) profiles with their labels, in a fixed row order."""

    profiles: list[Profile]
    groups: list[str]
    labels: np.ndarray
    candidates: list[str]

    def __len__(self) -> int:
        return len(self.profiles)


def sample_true_profiles(
    n_per_label: int = 300,
    groups: Sequence[str] | None = None,
    seed: int = 0,
    max_tries_per_row: int = 400,
) -> TrueSamples:
    """Balanced true profiles drawn from a stream that only the sampler uses.

    Unlike `generate_dataset`, no noise is drawn from this generator, so the profiles and
    labels depend only on `seed` and can be corrupted any number of times with `observe_samples`.
    """
    rng = np.random.default_rng(seed)
    engine = RuleEngine()
    profiles, group_of, labels, candidates = [], [], [], []

    for group in groups or list(SAMPLERS):
        sampler, targets = SAMPLERS[group], TARGETS[group]
        counts = dict.fromkeys(targets, 0)
        for _ in range(max_tries_per_row * n_per_label * len(targets)):
            if all(c >= n_per_label for c in counts.values()):
                break
            true = sampler(rng)
            result = engine.evaluate(true)
            label = label_of(result)
            if label not in counts or counts[label] >= n_per_label:
                continue
            counts[label] += 1
            profiles.append(true)
            group_of.append(group)
            labels.append(label)
            candidates.append("|".join(str(c) for c in result.candidates))
        short = {k: v for k, v in counts.items() if v < n_per_label}
        if short:
            warnings.warn(f"group '{group}': could not reach {n_per_label} rows for labels {short}")

    return TrueSamples(profiles, group_of, np.array(labels), candidates)


def observe_samples(
    true: TrueSamples,
    noise: NoiseConfig,
    rng: np.random.Generator,
    mechanism: MissingMechanism | None = None,
    report: MissingReport | None = None,
) -> tuple[list[Profile], pd.DataFrame]:
    """One noisy view of `true`: the observed profiles and the same columns as `generate_dataset`.

    Without `mechanism`, fields go missing independently (MCAR, `noise.missing_p`). With one, measurement
    noise is applied as usual and `noise.missing_p` gives the base rates of `missingness.apply_mechanism`.
    """
    engine = RuleEngine()
    if mechanism is None:
        seen_profiles = [observe(p, rng, noise) for p in true.profiles]
    else:
        noisy = [observe(p, rng, dataclasses.replace(noise, missing_p={})) for p in true.profiles]
        seen_profiles = apply_mechanism(noisy, true.profiles, true.labels, noise.missing_p, mechanism, rng, report)
    rows = []
    for i, seen in enumerate(seen_profiles):
        row = profile_to_record(seen)
        row.update(
            group=true.groups[i],
            label=int(true.labels[i]),
            candidates=true.candidates[i],
            rule_label=rule_label(engine.evaluate(seen)),
        )
        rows.append(row)
    return seen_profiles, pd.DataFrame(rows)


def sample_natural_profiles(
    n_per_group: int = 2000, groups: Sequence[str] | None = None, seed: int = 0, max_tries_per_row: int = 50
) -> tuple[TrueSamples, int]:
    """True profiles drawn from the broad clinical ranges, with no balancing by label.

    Values are not concentrated near the rule thresholds, and label frequencies are whatever the rules
    give. Profiles the rules cannot label (several eligible classes, or not implemented) are dropped, as
    in the balanced generator. Returns the samples and the number of dropped draws.
    """
    rng = np.random.default_rng(seed)
    engine = RuleEngine()
    profiles, group_of, labels, candidates, dropped = [], [], [], [], 0
    with natural_ranges():
        for group in groups or list(SAMPLERS):
            sampler, kept = SAMPLERS[group], 0
            for _ in range(max_tries_per_row * n_per_group):
                if kept >= n_per_group:
                    break
                true = sampler(rng)
                result = engine.evaluate(true)
                label = label_of(result)
                if label is None:
                    dropped += 1
                    continue
                kept += 1
                profiles.append(true)
                group_of.append(group)
                labels.append(label)
                candidates.append("|".join(str(c) for c in result.candidates))
    return TrueSamples(profiles, group_of, np.array(labels), candidates), dropped
