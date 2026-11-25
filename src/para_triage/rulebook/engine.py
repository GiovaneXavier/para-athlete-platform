"""The whole engine of the rule books, in shadow (step 6): the eight books in one object that answers like `RuleEngine`.

`ShadowEngine.evaluate(profile)` translates the profile into measures (the adapter below), evaluates each of the eight
books, and gathers the verdicts by class in a `ShadowResult`, which has the shape of the `EligibilityResult` of the current
engine (`verdicts`, `meets`, `primary_class`, `candidates`, `with_status`). The books are loaded once, and so is the variant.

Nothing uses it in production: the current `RuleEngine` is the default, and nothing outside this package imports this module
(a test enforces it). It does not import the current engine either; only the regression (compare.py) does.

What differs from the current engine, on purpose:
  - the statuses are strings (`"meets"`), not `Status`; `Status` is a `str` enum, so `Status.MEETS == "meets"`, and the
    regression compares the `.value`;
  - `Verdict.reasons` are reason codes (texts: `messages.message(code, "pt" | "en")`), not the English sentences of the engine;
  - the onset of the intellectual group is the age of the adapter below, and its missing field is called `onset_age`
    (the engine calls it `onset_before_22`).
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from .interpreter import DEFAULT_VARIANT, Rulebook, RulebookError, Verdict, load_variant

# The eight groups of the catalog. The verdicts come out sorted by class, so the order here is not the order of the output.
GROUPS = ("visual", "intellectual", "neuro", "short_stature", "limb_standing", "wheelchair", "limb_prosthesis", "frame_runner")

# The adapter of the onset. The current profile knows the onset only as a boolean (`onset_before_22`); the rule book of the
# intellectual group reads an age (`onset_age`), so that the limit can be a parameter that a variant changes. Until the profile
# has the age (item R12, not decided), a true flag is a representative age before the limit and a false one is the limit itself.
# This is not the real age: between 18 and 21 and at the boundary the engine cannot say, and the rule book is tested by hand there.
ONSET_AGE_IF_BEFORE, ONSET_AGE_IF_NOT, ONSET_LIMIT = 21, 22, 22


def onset_age(flag: bool | None) -> int | None:
    return None if flag is None else ONSET_AGE_IF_BEFORE if flag else ONSET_AGE_IF_NOT


def onset_flag(age: float | None) -> bool | None:
    """The other way round, for the regression: an age is before the limit of the booklet, or it is not."""
    return None if age is None else age < ONSET_LIMIT


def measures_of(profile, names: list[str]) -> dict:
    """The measures of a profile that a book reads, as plain values (enums by value); a missing measure is left out."""
    out = {}
    for name in names:
        value = onset_age(profile.onset_before_22) if name == "onset_age" else getattr(profile, name, None)
        if value is not None:
            out[name] = getattr(value, "value", value)
    return out


@dataclass(frozen=True)
class ShadowResult:
    """The shape of `EligibilityResult`: a verdict per class (sorted by class), and the questions the callers ask of it."""

    verdicts: dict[int, Verdict]

    def with_status(self, *statuses: str) -> list[int]:
        return [cid for cid, v in self.verdicts.items() if v.status in statuses]

    @property
    def meets(self) -> list[int]:
        return self.with_status("meets")

    @property
    def primary_class(self) -> int | None:
        """The single class that is met, or None when none or several are."""
        meets = self.meets
        return meets[0] if len(meets) == 1 else None

    @property
    def candidates(self) -> list[int]:
        """Classes that are met first, then borderline ones."""
        return self.with_status("meets") + self.with_status("borderline")


class ShadowEngine:
    def __init__(self, variant: str = DEFAULT_VARIANT, overrides: dict | None = None, on: dt.date | None = None, groups: tuple[str, ...] = GROUPS):
        self.books = {name: Rulebook.load(name) for name in groups}  # loaded once
        known = {p for book in self.books.values() for p in book.data.get("parameters", {})}
        if set(overrides or {}) - known:
            raise RulebookError(f"unknown parameter(s): {sorted(set(overrides) - known)}")
        self.variant, self.on = load_variant(variant), on  # the variant is read once too: a dict is taken as it is
        self.overrides = {name: {k: v for k, v in (overrides or {}).items() if k in book.data.get("parameters", {})} for name, book in self.books.items()}

    def evaluate(self, profile) -> ShadowResult:
        impairments = {getattr(i, "value", i) for i in profile.impairments}
        verdicts: dict[int, Verdict] = {}
        for name, book in self.books.items():
            evaluation = book.evaluate(measures_of(profile, book.measures), impairments, variant=self.variant, overrides=self.overrides[name] or None, on=self.on)
            if verdicts.keys() & evaluation.verdicts.keys():
                raise RulebookError(f"{name}: a class is decided by two books")
            verdicts.update(evaluation.verdicts)
        return ShadowResult(dict(sorted(verdicts.items())))
