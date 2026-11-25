"""Case bank of the study mode: deterministic cases per (group, seed), difficulty and answer key.

A case id is a recipe, not a secret: "k2.<version>.<group>.<difficulty>.<seed>.<index>" lets the
server rebuild the same case (the sampler is deterministic) without storing anything. The answer key
is always the rule engine's verdict on the case profile; it never travels with the case.

Read-only on the core: this module imports the rule engine, the catalog and the profile sampler.
"""
from __future__ import annotations

import dataclasses
import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np

from ..data.generator import sample_true_profiles
from ..rules import Impairment, Profile, RuleEngine, Status
from ..rules.catalog import Catalog, load_catalog
from . import scope
from .presentation import Presentation, present
from .scope import (
    ALLOWED_GROUPS,
    CASE_VERSION,
    DIFFICULTIES,
    GROUP_BY_ID,
    OPTION_INSUFFICIENT,
    OPTION_NONE,
    OPTION_SPECIALIST,
    class_option_id,
)
from .trace import Trace, build_trace

REVIEW_FILE = Path(__file__).with_name("review_status.json")
CASE_ID = re.compile(r"^k2\.(?P<version>[a-z0-9]+)\.(?P<group>[a-z_]+)\.(?P<difficulty>[a-z]+)\.(?P<seed>\d+)\.(?P<index>\d+)$")

MASKABLE_FIELDS = {
    "visual": ("logmar_best_eye", "visual_field_deg"),
    "short_stature": ("sex", "height_cm", "longest_arm_cm"),
    "limb_standing": ("lower_left", "lower_right", "upper_left", "upper_right"),
    "limb_prosthesis": ("lower_left", "lower_right", "upper_left", "upper_right"),
}
MIN_MASKED_VARIANTS = 40  # for groups with no "specialist" cases to pair them with


@dataclass(frozen=True)
class Candidate:
    profile: Profile
    answer: str  # option id from the rule engine
    masked: str | None  # profile field hidden from the learner (hard level), if any


@dataclass(frozen=True)
class BankStats:
    offered: int  # profiles kept (before the masked variants)
    discarded: int  # trace and engine disagreed: not offered
    not_offered: int  # the engine gives no single answer (for example two classes met)
    filtered: int  # outside the pathway of the study mode (limb_standing: not by amputation)


@dataclass(frozen=True)
class Bank:
    pools: dict[str, tuple[Candidate, ...]]
    stats: BankStats


@dataclass(frozen=True)
class Case:
    case_id: str
    group: str
    difficulty: str
    candidate: Candidate
    presentation: Presentation
    review_status: str

    @property
    def answer(self) -> str:
        return self.candidate.answer


# --- engine side: the answer key ----------------------------------------------------------------------


@lru_cache(maxsize=1)
def _engine() -> RuleEngine:
    return RuleEngine()


@lru_cache(maxsize=1)
def _catalog() -> Catalog:
    return load_catalog()


def engine_answer(group: str, profile: Profile) -> str | None:
    """The answer key: what the rule engine says about this profile, for the classes of `group`.

    None when the engine gives no single answer (the case is then not offered).
    """
    result = _engine().evaluate(profile)
    ids = {spec.class_id for spec in _catalog().group_classes(group)}
    statuses = {v.status for cid, v in result.verdicts.items() if cid in ids}
    if statuses == {Status.INSUFFICIENT_DATA}:
        return OPTION_INSUFFICIENT
    if statuses & {Status.INSUFFICIENT_DATA, Status.NOT_IMPLEMENTED, Status.NOT_APPLICABLE}:
        return None
    if statuses & {Status.BORDERLINE, Status.NEEDS_REVIEW}:
        return OPTION_SPECIALIST
    meets = [cid for cid, v in result.verdicts.items() if cid in ids and v.status is Status.MEETS]
    if len(meets) == 1:
        return class_option_id(meets[0])
    return OPTION_NONE if not meets else None


# --- difficulty ---------------------------------------------------------------------------------------


def _margin_visual(profile: Profile, criteria: dict[int, dict]) -> tuple[float, float]:
    c11, c12, c13 = criteria[11], criteria[12], criteria[13]
    logmar_edges = (c13["logmar_min"], c13["logmar_max"], c12["logmar_min"], c12["logmar_max"], c11["logmar_gt"])
    field_edges = (c12["field_lt_deg"], c13["field_lt_deg"])
    return (
        min(abs(profile.logmar_best_eye - e) for e in logmar_edges),
        min(abs(profile.visual_field_deg - e) for e in field_edges),
    )


def _min_relative_margin_short(profile: Profile, criteria: dict[int, dict]) -> float:
    key = "male" if profile.sex.value == "M" else "female"
    height, arm = profile.height_cm, profile.longest_arm_cm
    margins = []
    for cid in (40, 41):
        limit = criteria[cid][key]
        for value, bound in ((height, limit["max_height_cm"]), (arm, limit["max_arm_cm"]), (height + arm, limit["max_sum_cm"])):
            margins.append(abs(value - bound) / bound)
    return min(margins)


def difficulty_of(group: str, profile: Profile, answer: str) -> str:
    """Level of a complete (unmasked) profile: easy, medium or hard."""
    if answer in (OPTION_SPECIALIST, OPTION_INSUFFICIENT):
        return "hard"
    criteria = {cid: spec.criteria for cid, spec in _catalog().classes.items()}
    if group == "visual":
        logmar_margin, field_margin = _margin_visual(profile, criteria)
        near = logmar_margin < scope.VISUAL_LOGMAR_MARGIN or field_margin < scope.VISUAL_FIELD_MARGIN
        return "medium" if near else "easy"
    if group == "short_stature":
        return "easy" if _min_relative_margin_short(profile, criteria) >= scope.SHORT_STATURE_MARGIN else "medium"
    affected = sum(1 for name in ("lower_left", "lower_right", "upper_left", "upper_right") if int(getattr(profile, name)) > 0)
    return "easy" if affected == 1 else "medium"


# --- bank ---------------------------------------------------------------------------------------------


def _group_index(group: str) -> int:
    return ALLOWED_GROUPS.index(group)


@lru_cache(maxsize=256)
def bank(group: str, seed: int) -> Bank:
    """All offered candidates for (group, seed), split by difficulty and deterministically shuffled."""
    if group not in GROUP_BY_ID:
        raise KeyError(f"group outside the study mode: {group}")
    spec = GROUP_BY_ID[group]
    drawn = sample_true_profiles(spec.n_per_label, [group], seed)
    gi = _group_index(group)

    kept: dict[tuple[Profile, str | None], Candidate] = {}
    discarded = not_offered = filtered = 0
    for profile in drawn.profiles:
        if group == "limb_standing" and profile.impairments != frozenset({Impairment.LIMB_DEFICIENCY}):
            filtered += 1  # strength / range of motion / leg length pathway: not by amputation
            continue
        answer = engine_answer(group, profile)
        if answer is None:
            not_offered += 1
            continue
        if build_trace(group, profile, _catalog()).answer != answer:
            discarded += 1
            continue
        kept.setdefault((profile, None), Candidate(profile, answer, None))

    pools: dict[str, list[Candidate]] = {d: [] for d in DIFFICULTIES}
    for candidate in kept.values():
        pools[difficulty_of(group, candidate.profile, candidate.answer)].append(candidate)

    # Hard level also has cases with one field hidden; the key is the engine on the masked profile.
    rng = np.random.default_rng([seed, gi, 99])
    complete = [c for c in kept.values() if c.answer != OPTION_SPECIALIST]
    offered = len(kept)
    wanted = min(max(len(pools["hard"]), MIN_MASKED_VARIANTS), 2 * MIN_MASKED_VARIANTS)
    for position in rng.permutation(len(complete)):
        if wanted <= 0:
            break
        base = complete[int(position)]
        field = MASKABLE_FIELDS[group][int(rng.integers(len(MASKABLE_FIELDS[group])))]
        masked_profile = dataclasses.replace(base.profile, **{field: None})
        if (masked_profile, field) in kept:
            continue
        if engine_answer(group, masked_profile) != OPTION_INSUFFICIENT:
            continue
        if build_trace(group, masked_profile, _catalog()).answer != OPTION_INSUFFICIENT:
            discarded += 1
            continue
        candidate = Candidate(masked_profile, OPTION_INSUFFICIENT, field)
        kept[(masked_profile, field)] = candidate
        pools["hard"].append(candidate)
        wanted -= 1

    shuffled: dict[str, tuple[Candidate, ...]] = {}
    for di, level in enumerate(DIFFICULTIES):
        order = np.random.default_rng([seed, gi, di]).permutation(len(pools[level]))
        shuffled[level] = tuple(pools[level][int(i)] for i in order)
    return Bank(shuffled, BankStats(offered, discarded, not_offered, filtered))


# --- cases ----------------------------------------------------------------------------------------------


def make_case_id(group: str, difficulty: str, seed: int, index: int) -> str:
    return f"k2.{CASE_VERSION}.{group}.{difficulty}.{seed}.{index}"


@lru_cache(maxsize=1)
def _review_file() -> dict:
    try:
        return json.loads(REVIEW_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def review_status(case_id: str) -> str:
    """'reviewed' only when the specialist reviewed both the case and the texts; draft otherwise."""
    data = _review_file()
    reviewed = bool(data.get("texts_reviewed")) and case_id in set(data.get("reviewed_cases", []))
    return scope.REVIEW_REVIEWED if reviewed else scope.REVIEW_DRAFT


def get_case(group: str, difficulty: str, seed: int, index: int) -> Case:
    if group not in GROUP_BY_ID or difficulty not in DIFFICULTIES or seed < 0 or index < 0:
        raise KeyError("no such case")
    pool = bank(group, seed).pools[difficulty]
    if not pool:
        raise KeyError("no such case")
    candidate = pool[index % len(pool)]
    case_id = make_case_id(group, difficulty, seed, index)
    return Case(case_id, group, difficulty, candidate, present(group, candidate.profile), review_status(case_id))


def case_from_id(case_id: str) -> Case:
    """Rebuilds a case from its id. KeyError when the id is not a case of the study mode."""
    match = CASE_ID.match(case_id)
    if not match or match["version"] != CASE_VERSION:
        raise KeyError("no such case")
    return get_case(match["group"], match["difficulty"], int(match["seed"]), int(match["index"]))


def trace_of(case: Case) -> Trace:
    return build_trace(case.group, case.candidate.profile, _catalog())


# --- quiz -----------------------------------------------------------------------------------------------


def _level_counts(size: int, difficulty: str) -> list[str]:
    """Difficulty of each question, in a fixed order (mixed: 40% easy, 40% medium, 20% hard)."""
    if difficulty != "mixed":
        return [difficulty] * size
    exact = [(level, share * size) for level, share in scope.MIXED_SHARES]
    counts = {level: int(value) for level, value in exact}
    leftovers = sorted(exact, key=lambda item: item[1] - int(item[1]), reverse=True)
    for level, _ in leftovers[: size - sum(counts.values())]:
        counts[level] += 1
    return [level for level, _ in scope.MIXED_SHARES for _ in range(counts[level])]


def build_quiz(seed: int, size: int, groups: tuple[str, ...], difficulty: str) -> list[Case]:
    """Deterministic quiz: groups in rotation, levels shuffled by seed, no case repeated.

    When a (group, level) pool is exhausted (small groups such as amputation levels have few distinct
    cases) the next level of that group is used; the case id always names the pool it came from.
    """
    rng = np.random.default_rng([seed, 7_000 + size])
    levels = _level_counts(size, difficulty)
    levels = [levels[int(i)] for i in rng.permutation(len(levels))]
    order = [groups[int(i)] for i in rng.permutation(len(groups))]
    used: dict[tuple[str, str], int] = {}
    cases: list[Case] = []
    for position, level in enumerate(levels):
        group = order[position % len(order)]
        sequence = [level, *[d for d in DIFFICULTIES if d != level]]
        for candidate_level in sequence:
            pool = bank(group, seed).pools[candidate_level]
            taken = used.get((group, candidate_level), 0)
            if taken < len(pool):
                used[(group, candidate_level)] = taken + 1
                cases.append(get_case(group, candidate_level, seed, taken))
                break
    return cases
