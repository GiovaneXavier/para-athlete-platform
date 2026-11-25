"""Texts by reason code and language (pt and en; es later). A missing translation falls back to English."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

MESSAGES = Path(__file__).parent / "data" / "messages"
LANGUAGES = ("pt", "en")
FALLBACK = "en"


class _Keep(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


@lru_cache(maxsize=None)
def table(lang: str) -> dict[str, str]:
    path = MESSAGES / f"{lang}.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.is_file() else {}


def codes(lang: str) -> set[str]:
    return set(table(lang))


def message(code: str, lang: str = "pt", **params) -> str:
    """The text of a reason code; unknown codes are returned as they are."""
    template = table(lang).get(code) or table(FALLBACK).get(code) or code
    return template.format_map(_Keep(params))
