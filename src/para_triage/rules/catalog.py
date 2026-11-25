"""Loads classes.yaml into typed specs."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from .schema import Impairment, Posture

DEFAULT_CATALOG = Path(__file__).with_name("classes.yaml")


@dataclass(frozen=True)
class GroupSpec:
    name: str
    impairments: frozenset[Impairment]
    evaluator: str
    implemented: bool


@dataclass(frozen=True)
class ClassSpec:
    class_id: int
    group: str
    name_pt: str
    postures: tuple[Posture, ...]
    events: tuple[str, ...]  # subset of: track, jump, field
    equipment: tuple[str, ...]
    source_page: int | None
    criteria: dict[str, Any]
    # Seated classes 51-57 are the field (F) classes; the track class that covers
    # the same functional profile has a different number (e.g. F54 -> T53).
    track_equivalent: int | None = None

    @property
    def codes(self) -> tuple[str, ...]:
        """Official class codes, e.g. ("T44", "F44"). T covers track and jump."""
        out = []
        if {"track", "jump"} & set(self.events):
            out.append(f"T{self.track_equivalent or self.class_id}")
        if "field" in self.events:
            out.append(f"F{self.class_id}")
        return tuple(out)


@dataclass(frozen=True)
class Catalog:
    groups: dict[str, GroupSpec]
    classes: dict[int, ClassSpec]

    def group_classes(self, group: str) -> list[ClassSpec]:
        return [c for c in self.classes.values() if c.group == group]


def load_catalog(path: Path | None = None) -> Catalog:
    if path is None:
        return _default_catalog()
    return _parse(path)


@lru_cache(maxsize=1)
def _default_catalog() -> Catalog:
    return _parse(DEFAULT_CATALOG)


def _parse(path: Path) -> Catalog:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    groups = {
        name: GroupSpec(
            name=name,
            impairments=frozenset(Impairment(i) for i in g["impairments"]),
            evaluator=g["evaluator"],
            implemented=g["implemented"],
        )
        for name, g in raw["groups"].items()
    }
    classes = {
        int(cid): ClassSpec(
            class_id=int(cid),
            group=c["group"],
            name_pt=c["name_pt"],
            postures=tuple(Posture(p) for p in c.get("postures", ())),
            events=tuple(c["events"]),
            equipment=tuple(c.get("equipment", ())),
            source_page=c.get("source_page"),
            criteria=c.get("criteria", {}),
            track_equivalent=c.get("track_equivalent"),
        )
        for cid, c in raw["classes"].items()
    }
    return Catalog(groups=groups, classes=classes)
