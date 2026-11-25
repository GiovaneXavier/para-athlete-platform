"""Visual, intellectual and short-stature evaluators (classes with numeric criteria)."""
from __future__ import annotations

from collections.abc import Sequence

from ..catalog import ClassSpec
from ..schema import Profile, Sex, Status, Verdict
from .base import resolve, uniform


def _acuity_class(logmar: float, c: dict[int, dict]) -> int | str | None:
    if logmar > c[11]["logmar_gt"]:
        return 11
    if c[12]["logmar_min"] <= logmar <= c[12]["logmar_max"]:
        return 12
    if c[13]["logmar_min"] <= logmar <= c[13]["logmar_max"]:
        return 13
    if c[13]["logmar_max"] < logmar < c[12]["logmar_min"]:
        return "gap"  # booklet leaves (1.40, 1.50) unassigned
    return None


def _field_class(field_deg: float, c: dict[int, dict]) -> int | None:
    if field_deg < c[12]["field_lt_deg"]:
        return 12
    if field_deg < c[13]["field_lt_deg"]:
        return 13
    return None


def evaluate_visual(profile: Profile, specs: Sequence[ClassSpec]) -> dict[int, Verdict]:
    c = {s.class_id: s.criteria for s in specs}
    acuity, field_deg = profile.logmar_best_eye, profile.visual_field_deg
    missing = tuple(
        name
        for name, value in (("logmar_best_eye", acuity), ("visual_field_deg", field_deg))
        if value is None
    )
    if len(missing) == 2:
        return uniform(specs, Status.INSUFFICIENT_DATA, "visual acuity and visual field not provided", missing)

    acuity_cls = _acuity_class(acuity, c) if acuity is not None else None
    field_cls = _field_class(field_deg, c) if field_deg is not None else None

    hits: list[tuple[int, str]] = []
    gap = acuity_cls == "gap"
    if isinstance(acuity_cls, int):
        hits.append((acuity_cls, f"best-eye logMAR {acuity} is in the class {acuity_cls} range"))
    if field_cls is not None:
        hits.append((field_cls, f"visual field of {field_deg} degrees is in the class {field_cls} range"))

    gap_reason = f"logMAR {acuity} falls between the class 13 and class 12 ranges, which the booklet leaves unassigned"
    if hits:
        primary = min(cls for cls, _ in hits)
        reason = "; ".join(r for cls, r in hits if cls == primary)
        if missing and primary != 11:
            reason += f" ({missing[0]} not provided; a more impaired class is possible)"
        borderline = {12: gap_reason} if gap and primary > 12 else {}
        return resolve(specs, {primary: reason}, borderline, "visual criteria for this class not met", missing)
    if gap:
        return resolve(specs, borderline={12: gap_reason, 13: gap_reason}, missing=missing)
    if missing:
        return uniform(
            specs,
            Status.INSUFFICIENT_DATA,
            f"provided measure is above the eligibility limits; {missing[0]} not provided",
            missing,
        )
    return uniform(specs, Status.NOT_MET, "visual acuity and field are above the minimum eligibility criteria")


def evaluate_intellectual(profile: Profile, specs: Sequence[ClassSpec]) -> dict[int, Verdict]:
    iq_max = specs[0].criteria["iq_max"]
    checks = {
        "iq": None if profile.iq is None else profile.iq <= iq_max,
        "adaptive_limitation": profile.adaptive_limitation,
        "onset_before_22": profile.onset_before_22,
    }
    failed = [k for k, v in checks.items() if v is False]
    missing = tuple(k for k, v in checks.items() if v is None)
    if failed:
        return uniform(specs, Status.NOT_MET, f"criterion not met: {', '.join(failed)}")
    if missing:
        return uniform(specs, Status.INSUFFICIENT_DATA, "intellectual criteria incomplete", missing)
    return resolve(specs, {20: f"IQ <= {iq_max}, adaptive limitation, onset before age 22"})


def evaluate_short_stature(profile: Profile, specs: Sequence[ClassSpec]) -> dict[int, Verdict]:
    needed = (
        ("sex", profile.sex),
        ("height_cm", profile.height_cm),
        ("longest_arm_cm", profile.longest_arm_cm),
    )
    missing = tuple(name for name, value in needed if value is None)
    if missing:
        return uniform(specs, Status.INSUFFICIENT_DATA, "short stature measurements incomplete", missing)

    height, arm = profile.height_cm, profile.longest_arm_cm
    total = height + arm
    key = "male" if profile.sex is Sex.MALE else "female"
    meets: dict[int, str] = {}
    for spec in sorted(specs, key=lambda s: s.class_id):
        lim = spec.criteria[key]
        if height <= lim["max_height_cm"] and arm <= lim["max_arm_cm"] and total <= lim["max_sum_cm"]:
            meets[spec.class_id] = (
                f"height {height} cm, arm {arm} cm, sum {total} cm are within the "
                f"limits ({lim['max_height_cm']}/{lim['max_arm_cm']}/{lim['max_sum_cm']})"
            )
            break  # classes are nested; the most impaired one wins
    return resolve(specs, meets, default_reason="limits exceeded, or a more impaired class applies")
