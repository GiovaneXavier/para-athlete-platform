"""The simulated FORM: the attributes as an athlete would fill them in, with fields missing and with mistakes.

The truth is the exact set of attributes the generator built (the true level of every limb, even where the picture hides it,
and the true chair and prosthesis). A form is made from it with two independent rates:

- `missing`: each field is left blank (`?`) with this probability (the two flags too, at level 2);
- `errors`: each of the four limb fields is wrong with this probability, independently. Half of the mistakes put there the value
  of the OTHER side (a side mistake; if the two sides are equal that would not be a change, so it becomes a level mistake) and
  half put a level that is neither the truth nor `?` (a level mistake). A mistake always changes the value.

Every form is a pure function of (cell, image id), so the same form is built every time.
"""
from __future__ import annotations

import random

from para_triage.consistency.schema import DOMAINS, SIDE_SWAP, UNKNOWN

from .labels import FLAGS, LIMBS

MISSING_RATES = (0.0, 0.10, 0.30, 0.50)
ERROR_RATES = (0.0, 0.05, 0.10)
CELLS = [(m, e) for m in MISSING_RATES for e in ERROR_RATES]  # 12 cells


def make_form(truth: dict, missing: float, errors: float, key: str, level: int = 2) -> dict:
    """`truth` maps the six attributes to their TRUE values (no `?`). Returns the form with `?` where blank."""
    rng = random.Random(f"k35-form:{missing}:{errors}:{key}")
    form = dict(truth)
    for name in LIMBS:
        if rng.random() < errors:
            if rng.random() < 0.5 and truth[name] != truth[SIDE_SWAP[name]]:
                form[name] = truth[SIDE_SWAP[name]]
            else:
                form[name] = rng.choice([v for v in DOMAINS[name] if v not in (UNKNOWN, truth[name])])
    for name in LIMBS + (FLAGS if level == 2 else ()):
        if rng.random() < missing:
            form[name] = UNKNOWN
    return form


def has_error(form: dict, truth: dict) -> bool:
    """True if some limb field has a value that is not the truth (a blank is not an error)."""
    return any(form[n] != UNKNOWN and form[n] != truth[n] for n in LIMBS)
