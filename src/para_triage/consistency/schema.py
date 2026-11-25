"""The closed attribute schema of the image and report consistency check (K34, design note section 2).

Nothing here imports the rule engine: the level domains are written out and a test checks that
they equal `LowerLimbLevel` and `UpperLimbLevel`.

Left and right are the PERSON's side, not the viewer's. A figure seen from the front has the
person's left on the right of the image.

`?` means "cannot be determined" (hidden, cut, far, covered). It is never a level.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any, Mapping, Union

UNKNOWN = "?"

LOWER_LEVELS: tuple[int, ...] = (0, 1, 2, 3)  # none, partial foot, below knee, through or above knee
UPPER_LEVELS: tuple[int, ...] = (0, 1, 2)  # none, wrist or below elbow, elbow or above
YES_NO: tuple[str, ...] = ("yes", "no")

Value = Union[int, str]

LOWER_FIELDS = ("lower_left", "lower_right")
UPPER_FIELDS = ("upper_left", "upper_right")
LIMB_FIELDS = LOWER_FIELDS + UPPER_FIELDS
FLAG_FIELDS = ("wheelchair", "prosthesis")
ATTRIBUTES = LIMB_FIELDS + FLAG_FIELDS  # the six attributes of the closed schema
LEVEL1_ATTRIBUTES = LIMB_FIELDS  # level 1 (the mannequin) has only the four limbs

DOMAINS: dict[str, tuple[Value, ...]] = {
    "lower_left": LOWER_LEVELS + (UNKNOWN,),
    "lower_right": LOWER_LEVELS + (UNKNOWN,),
    "upper_left": UPPER_LEVELS + (UNKNOWN,),
    "upper_right": UPPER_LEVELS + (UNKNOWN,),
    "wheelchair": YES_NO + (UNKNOWN,),
    "prosthesis": YES_NO + (UNKNOWN,),
}

SIDE_SWAP = {"lower_left": "lower_right", "lower_right": "lower_left", "upper_left": "upper_right", "upper_right": "upper_left"}


class SchemaError(ValueError):
    """A value outside the closed domain of its attribute."""


def check_value(name: str, value: Any) -> Value:
    if name not in DOMAINS:
        raise SchemaError(f"unknown attribute {name!r}")
    # Exact types only: True would pass for 1 and 1.0 for 1.
    if type(value) not in (int, str) or value not in DOMAINS[name]:
        raise SchemaError(f"{name}: {value!r} is not in {DOMAINS[name]}")
    return value


@dataclass(frozen=True)
class Attrs:
    """The six attributes of one image or one report. Every field defaults to `?`."""

    lower_left: Value = UNKNOWN
    lower_right: Value = UNKNOWN
    upper_left: Value = UNKNOWN
    upper_right: Value = UNKNOWN
    wheelchair: Value = UNKNOWN
    prosthesis: Value = UNKNOWN

    def __post_init__(self) -> None:
        for f in fields(self):
            check_value(f.name, getattr(self, f.name))

    def as_dict(self) -> dict[str, Value]:
        return {name: getattr(self, name) for name in ATTRIBUTES}

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "Attrs":
        """Strict: an unknown key or a value outside the domain is refused; a missing key is `?`."""
        extra = set(data) - set(ATTRIBUTES)
        if extra:
            raise SchemaError(f"unknown attributes: {sorted(extra)}")
        return cls(**{k: check_value(k, v) for k, v in data.items()})

    def known(self) -> dict[str, Value]:
        return {k: v for k, v in self.as_dict().items() if v != UNKNOWN}

    def with_(self, **changes: Value) -> "Attrs":
        return Attrs(**{**self.as_dict(), **changes})

    def swapped_sides(self) -> "Attrs":
        return Attrs(**{SIDE_SWAP.get(k, k): v for k, v in self.as_dict().items()})

    def restricted(self, names: tuple[str, ...]) -> "Attrs":
        """Keeps only `names`; the others become `?` (e.g. level 1 has no wheelchair or prosthesis)."""
        return Attrs(**{k: (v if k in names else UNKNOWN) for k, v in self.as_dict().items()})


def level1_combinations() -> list[Attrs]:
    """The 144 combinations (4 x 4 x 3 x 3) of the four limb levels."""
    return [
        Attrs(lower_left=ll, lower_right=lr, upper_left=ul, upper_right=ur)
        for ll in LOWER_LEVELS
        for lr in LOWER_LEVELS
        for ul in UPPER_LEVELS
        for ur in UPPER_LEVELS
    ]
