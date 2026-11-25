"""What the study mode (K2) covers, and the fixed constants of its contract.

Scope decided in ADR 0018 (D28): only groups whose rules are implemented from numeric criteria or
amputation levels. Everything else is refused by the API and absent from the web.
"""
from __future__ import annotations

from dataclasses import dataclass

CASE_VERSION = "v1"  # first segment of every case id after "k2."; bump when case generation changes

NOTICE = (
    "Material de estudo, com dados fictícios. Não ensina a classificar oficialmente. "
    "Regras do livreto do CPB (2024) em leitura nossa, ainda a validar com a especialista."
)

REVIEW_DRAFT = "draft"
REVIEW_REVIEWED = "reviewed"

DIFFICULTIES = ("easy", "medium", "hard")
QUIZ_DIFFICULTIES = (*DIFFICULTIES, "mixed")
QUIZ_SIZES = (5, 10, 15)
DEFAULT_QUIZ_SIZE = 10
MIXED_SHARES = (("easy", 0.4), ("medium", 0.4), ("hard", 0.2))
MAX_SEED = 999_999_999

# Difficulty margins (initial values, see docs/educacao.md section 3).
VISUAL_LOGMAR_MARGIN = 0.25  # logMAR distance from every acuity threshold for an "easy" case
VISUAL_FIELD_MARGIN = 10.0  # degrees from every field threshold for an "easy" case
SHORT_STATURE_MARGIN = 0.08  # relative distance from every limit for an "easy" case

# Answer option ids (besides "class:<id>").
OPTION_NONE = "none"
OPTION_SPECIALIST = "specialist"
OPTION_INSUFFICIENT = "insufficient"


@dataclass(frozen=True)
class GroupScope:
    id: str  # catalog and generator group name
    n_per_label: int  # profiles per label drawn for the case bank
    classes: tuple[int, ...]


# Order is the order shown to the user. Nothing else is reachable.
GROUPS: tuple[GroupScope, ...] = (
    GroupScope("visual", 40, (11, 12, 13)),
    GroupScope("short_stature", 40, (40, 41)),
    GroupScope("limb_standing", 120, (42, 43, 44, 45, 46, 47)),
    GroupScope("limb_prosthesis", 40, (61, 62, 63, 64)),
)
ALLOWED_GROUPS: tuple[str, ...] = tuple(g.id for g in GROUPS)
GROUP_BY_ID = {g.id: g for g in GROUPS}

# Groups the study mode must never reach (provisional rules, or an open divergence on class 20).
EXCLUDED_GROUPS: tuple[str, ...] = (
    "intellectual",
    "neuro_seated",
    "neuro_standing",
    "frame_runner",
    "wheelchair",
)
EXCLUDED_CLASSES: tuple[int, ...] = (20, 31, 32, 33, 34, 35, 36, 37, 38, 51, 52, 53, 54, 55, 56, 57, 71, 72)


def class_option_id(class_id: int) -> str:
    return f"class:{class_id}"
