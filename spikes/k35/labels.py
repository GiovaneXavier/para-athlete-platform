"""Label encoding of the six attributes and the left/right swap used by the mirror augmentation. Pure Python (no torch, no numpy).

Left and right are the PERSON's own sides. Reflecting a picture left to right swaps the person's left and right,
so the label of the reflected picture is the original label with the two sides swapped (flags do not change).
"""
from __future__ import annotations

from para_triage.consistency.schema import ATTRIBUTES, DOMAINS, UNKNOWN, Attrs

LIMBS = ("lower_left", "lower_right", "upper_left", "upper_right")
FLAGS = ("wheelchair", "prosthesis")
HEADS = ATTRIBUTES  # the order of the six heads and of every label vector
assert HEADS == LIMBS + FLAGS

IGNORE = -1  # level 1 has no chair or prosthesis: those two heads take no loss there
N_CLASSES = {name: len(DOMAINS[name]) for name in HEADS}  # lower 4 levels + `?`, upper 3 + `?`, flags yes/no/`?`
SWAP_INDEX = (1, 0, 3, 2, 4, 5)  # position of each head after reflecting: lower_left <-> lower_right, upper_left <-> upper_right


def encode(name: str, value) -> int:
    return DOMAINS[name].index(value)


def decode(name: str, index: int):
    return DOMAINS[name][index]


def encode_attrs(attrs: Attrs, level: int) -> list[int]:
    """The six head indices of a label; at level 1 the two flags are IGNORE."""
    out = [encode(name, getattr(attrs, name)) for name in HEADS]
    if level == 1:
        out[4] = out[5] = IGNORE
    return out


def swap_labels(y):
    """The label vector of the left-right reflected picture. Works on a list, a tuple, a numpy row or a torch row."""
    return [y[i] for i in SWAP_INDEX] if isinstance(y, (list, tuple)) else y[list(SWAP_INDEX)]


def swap_attrs(attrs: Attrs) -> Attrs:
    return attrs.swapped_sides()


def is_unknown(name: str, index: int) -> bool:
    return index != IGNORE and decode(name, index) == UNKNOWN
