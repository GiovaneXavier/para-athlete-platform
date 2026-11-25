"""Read-only id of the rule book: a hash of the rule sources.

Covered: `rules/classes.yaml`, `rules/engine.py`, `rules/catalog.py`, `rules/schema.py` and
`rules/evaluators/*.py`. The id changes when any of them changes, and only then. Line endings are
normalised so the same sources give the same id on Windows and Linux.
"""
from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from .. import rules as _rules_package

RULES_DIR = Path(_rules_package.__file__).resolve().parent
CATALOG_FILE = "classes.yaml"
CORE_FILES = (CATALOG_FILE, "engine.py", "catalog.py", "schema.py")  # beside evaluators/*.py
ID_PREFIX = "rules-"
ID_LENGTH = 12


@dataclass(frozen=True)
class RulesVersion:
    id: str  # e.g. "rules-3f9a1c2b7d44": short, for screens and API responses
    sha256: str  # full digest over the files below
    files: tuple[tuple[str, str], ...]  # (path relative to rules/, sha256 of the file), sorted


def _digest(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def _sort_key(name: str) -> tuple[bool, str]:
    return (name != CATALOG_FILE, name)  # classes.yaml first, then the evaluators by name


def rules_version_from_contents(contents: Mapping[str, bytes]) -> RulesVersion:
    """Same id from file contents keyed by path relative to rules/ (e.g. read from a git commit)."""
    files = tuple((name, _digest(contents[name])) for name in sorted(contents, key=_sort_key))
    combined = hashlib.sha256()
    for name, digest in files:
        combined.update(f"{name}\0{digest}\n".encode())
    digest = combined.hexdigest()
    return RulesVersion(id=ID_PREFIX + digest[:ID_LENGTH], sha256=digest, files=files)


def rules_version(rules_dir: Path | None = None) -> RulesVersion:
    """Hashes the rule sources under `rules_dir` (default: the installed rules)."""
    root = Path(rules_dir) if rules_dir is not None else RULES_DIR
    paths = [*(root / name for name in CORE_FILES), *(root / "evaluators").glob("*.py")]
    missing = [p.name for p in paths if not p.is_file()]
    if missing:
        raise FileNotFoundError(f"rule book files not found under {root.name}: {missing}")
    return rules_version_from_contents({p.relative_to(root).as_posix(): p.read_bytes() for p in paths})
