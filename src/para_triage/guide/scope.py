"""What the class guide (K18) covers, and the fixed constants of its contract.

The scope is the one of the study mode (K2, ADR 0018 D28): the same four groups, 15 classes. "Validated"
here means "implemented and already used in K2", not reviewed by a classifier.
"""
from __future__ import annotations

from ..education.scope import ALLOWED_GROUPS, EXCLUDED_CLASSES, EXCLUDED_GROUPS, GROUP_BY_ID

CONTENT_VERSION = 1

NOTICE = (
    "Guia de estudo, em leitura nossa do livreto do CPB (2024). "
    "Não é classificação oficial e ainda está por validar com a especialista."
)

REVIEW_DRAFT = "draft"
REVIEW_REVIEWED = "reviewed"

# Addresses are in Portuguese; the catalog ids stay internal.
GROUP_SLUGS = {
    "visual": "visual",
    "short_stature": "baixa-estatura",
    "limb_standing": "amputacao-em-pe",
    "limb_prosthesis": "amputacao-com-protese",
}
SLUG_TO_GROUP = {slug: group for group, slug in GROUP_SLUGS.items()}

GROUPS: tuple[str, ...] = ALLOWED_GROUPS  # the order of the study mode


def class_slug(class_id: int) -> str:
    return f"classe-{class_id}"


def class_ids(group: str) -> tuple[int, ...]:
    return GROUP_BY_ID[group].classes


def group_path(group: str) -> str:
    return f"/guia/{GROUP_SLUGS[group]}"


def class_path(group: str, class_id: int) -> str:
    return f"{group_path(group)}/{class_slug(class_id)}"


GLOSSARY_PATH = "/guia/glossario"
HUB_PATH = "/guia"
RULES_PATH = "/transparencia#regras"


def practice_path(group: str) -> str:
    """Study-mode link by group (the API of K2 filters by group and level, not by class)."""
    return f"/educacao/praticar?grupo={group}&nivel=easy&semente=0&caso=0"


__all__ = [
    "ALLOWED_GROUPS",
    "EXCLUDED_CLASSES",
    "EXCLUDED_GROUPS",
]
