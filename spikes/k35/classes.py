"""The class that the RULES give from the attributes (never from the network): a table computed once from the engine.

A combination of four limb levels and a posture maps to the set of classes MET plus the ones BORDERLINE (the engine's
`candidates`). Only 27 of the 432 decided combinations (144 x 3 postures) give a non-empty set; the rest are empty
("no class from limb deficiency alone"), and a seated person always gives the empty set.

`candidates(...)` returns None ("undecided") when an attribute the class needs is `?`: the posture needs the chair and
prosthesis flags, and every one of the four limbs is read by the engine. With a `?` the engine has no data and its
candidate list is empty, so "empty" and "undecided" would be confused if we did not keep them apart. This module keeps them apart.
"""
from __future__ import annotations

from para_triage.consistency.schema import UNKNOWN

from .class_table import TABLE

STANDING, PROSTHESIS, SEATED = "standing", "prosthesis", "seated"


def posture(wheelchair, prosthesis) -> str | None:
    """seated if there is a chair; else prosthesis if there is one; else standing. None if the flags do not decide it."""
    if wheelchair == "yes":
        return SEATED
    if wheelchair == UNKNOWN:
        return None
    if prosthesis == "yes":
        return PROSTHESIS
    if prosthesis == UNKNOWN:
        return None
    return STANDING


def candidates(limbs, wheelchair="no", prosthesis="no") -> frozenset | None:
    """`limbs` is (lower_left, lower_right, upper_left, upper_right). Returns the frozenset of candidate classes
    (met first is lost on purpose: only the set is compared), or None when it cannot be decided."""
    if any(v == UNKNOWN for v in limbs):
        return None
    p = posture(wheelchair, prosthesis)
    if p is None:
        return None
    meets, borderline = TABLE.get((p, *limbs), ((), ()))
    return frozenset(meets) | frozenset(borderline)


def table_size() -> tuple[int, int]:
    return len(TABLE), 3 * 144
