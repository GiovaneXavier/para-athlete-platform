"""Turns a true profile into what a professional would actually record.

All defaults are assumptions about measurement error and incomplete forms. They
should be reviewed by the domain specialist.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace

import numpy as np

from ..rules import CpDistribution, LowerLimbLevel, Profile, UpperLimbLevel


def _default_missing() -> dict[str, float]:
    return {
        "sex": 0.01,
        "posture": 0.02,
        "logmar_best_eye": 0.05,
        "visual_field_deg": 0.10,
        "iq": 0.05,
        "adaptive_limitation": 0.10,
        "onset_before_22": 0.10,
        "height_cm": 0.02,
        "longest_arm_cm": 0.08,
        "lower_left": 0.02,
        "lower_right": 0.02,
        "upper_left": 0.05,
        "upper_right": 0.05,
        "ankle_pf_mrc": 0.15,
        "ankle_rom_deg": 0.20,
        "leg_length_diff_cm": 0.15,
        "hip_knee_deficit": 0.15,
        "lower_limb_sides_affected": 0.10,
        "brain_impairment_report": 0.05,
        "neuro_severity": 0.05,
        "cp_distribution": 0.10,
        "chair_propulsion": 0.10,
        "transfers_independently": 0.05,
        "walks_short_distances": 0.10,
        "trunk_straps_needed": 0.15,
        "arm_function": 0.05,
        "trunk_function": 0.05,
        "leg_function": 0.10,
    }


@dataclass(frozen=True)
class NoiseConfig:
    logmar_sd: float = 0.05
    field_sd_deg: float = 2.0
    iq_sd: float = 3.0
    height_sd_cm: float = 0.3
    arm_sd_cm: float = 0.5
    rom_sd_deg: float = 3.0
    leg_diff_sd_cm: float = 0.5
    mrc_shift_p: float = 0.08  # strength grade recorded one step off
    level_confusion_p: float = 0.03  # amputation level recorded one level off
    ordinal_shift_p: float = 0.05  # functional rating recorded one step off
    flag_flip_p: float = 0.03  # functional yes/no answer recorded wrongly
    distribution_swap_p: float = 0.03  # cerebral palsy distribution recorded wrongly
    missing_p: dict[str, float] = field(default_factory=_default_missing)

    def scaled(self, noise: float = 1.0, missing: float = 1.0) -> "NoiseConfig":
        """Multiplies every error scale and rate by `noise`, and every missing rate by `missing`.

        Probabilities are capped at 1. `scaled(1, 1)` is the default, and `scaled(0, 0)` corrupts
        nothing, like `none()` (its missing rates are all zero instead of absent).
        """
        if noise < 0 or missing < 0:
            raise ValueError("multipliers must be non-negative")
        prob = lambda p: min(1.0, p * noise)  # noqa: E731
        return NoiseConfig(
            logmar_sd=self.logmar_sd * noise,
            field_sd_deg=self.field_sd_deg * noise,
            iq_sd=self.iq_sd * noise,
            height_sd_cm=self.height_sd_cm * noise,
            arm_sd_cm=self.arm_sd_cm * noise,
            rom_sd_deg=self.rom_sd_deg * noise,
            leg_diff_sd_cm=self.leg_diff_sd_cm * noise,
            mrc_shift_p=prob(self.mrc_shift_p),
            level_confusion_p=prob(self.level_confusion_p),
            ordinal_shift_p=prob(self.ordinal_shift_p),
            flag_flip_p=prob(self.flag_flip_p),
            distribution_swap_p=prob(self.distribution_swap_p),
            missing_p={k: min(1.0, p * missing) for k, p in self.missing_p.items()},
        )

    @classmethod
    def none(cls) -> "NoiseConfig":
        return cls(
            logmar_sd=0,
            field_sd_deg=0,
            iq_sd=0,
            height_sd_cm=0,
            arm_sd_cm=0,
            rom_sd_deg=0,
            leg_diff_sd_cm=0,
            mrc_shift_p=0,
            level_confusion_p=0,
            ordinal_shift_p=0,
            flag_flip_p=0,
            distribution_swap_p=0,
            missing_p={},
        )


_ORDINAL_FIELDS = ("neuro_severity", "chair_propulsion", "arm_function", "trunk_function", "leg_function")
_FLAG_FIELDS = ("transfers_independently", "walks_short_distances", "trunk_straps_needed")


def _jitter(rng, value, sd, digits):
    if value is None or sd == 0:
        return value
    return round(float(value + rng.normal(0, sd)), digits)


def _shift_level(rng, level, enum_cls):
    if level is None or level == 0:
        return level
    top = max(enum_cls)
    return enum_cls(int(np.clip(int(level) + rng.choice([-1, 1]), 1, top)))


def observe(profile: Profile, rng: np.random.Generator, cfg: NoiseConfig) -> Profile:
    changes: dict = {
        "logmar_best_eye": _jitter(rng, profile.logmar_best_eye, cfg.logmar_sd, 2),
        "visual_field_deg": _jitter(rng, profile.visual_field_deg, cfg.field_sd_deg, 1),
        "height_cm": _jitter(rng, profile.height_cm, cfg.height_sd_cm, 1),
        "longest_arm_cm": _jitter(rng, profile.longest_arm_cm, cfg.arm_sd_cm, 1),
        "ankle_rom_deg": _jitter(rng, profile.ankle_rom_deg, cfg.rom_sd_deg, 1),
        "leg_length_diff_cm": _jitter(rng, profile.leg_length_diff_cm, cfg.leg_diff_sd_cm, 1),
    }
    if profile.visual_field_deg is not None:
        changes["visual_field_deg"] = max(0.0, changes["visual_field_deg"])
    if profile.iq is not None:
        changes["iq"] = int(round(profile.iq + rng.normal(0, cfg.iq_sd))) if cfg.iq_sd else profile.iq
    if profile.ankle_pf_mrc is not None and rng.random() < cfg.mrc_shift_p:
        changes["ankle_pf_mrc"] = int(np.clip(profile.ankle_pf_mrc + rng.choice([-1, 1]), 0, 5))

    for name, enum_cls in (
        ("lower_left", LowerLimbLevel),
        ("lower_right", LowerLimbLevel),
        ("upper_left", UpperLimbLevel),
        ("upper_right", UpperLimbLevel),
    ):
        level = getattr(profile, name)
        if rng.random() < cfg.level_confusion_p:
            changes[name] = _shift_level(rng, level, enum_cls)

    for name in _ORDINAL_FIELDS:
        value = getattr(profile, name)
        if value is not None and rng.random() < cfg.ordinal_shift_p:
            enum_cls = type(value)
            changes[name] = enum_cls(int(np.clip(int(value) + rng.choice([-1, 1]), min(enum_cls), max(enum_cls))))
    for name in _FLAG_FIELDS:
        value = getattr(profile, name)
        if value is not None and rng.random() < cfg.flag_flip_p:
            changes[name] = not value
    if profile.cp_distribution is not None and rng.random() < cfg.distribution_swap_p:
        others = [d for d in CpDistribution if d is not profile.cp_distribution]
        changes["cp_distribution"] = others[int(rng.integers(len(others)))]

    observed = replace(profile, **{k: v for k, v in changes.items() if v is not None})

    drop = {name: None for name, p in cfg.missing_p.items() if rng.random() < p}
    both_visual = {"logmar_best_eye", "visual_field_deg"}
    if both_visual <= drop.keys() and profile.logmar_best_eye is not None:
        del drop["visual_field_deg"]  # a visual form always has at least one measure
    return replace(observed, **drop)
