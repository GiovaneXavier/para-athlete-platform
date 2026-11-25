"""Answer options of a group: one per class, plus none, specialist and "missing data"."""
from __future__ import annotations

from dataclasses import dataclass

from ..rules.catalog import load_catalog
from . import texts_pt as T
from .scope import (
    GROUP_BY_ID,
    OPTION_INSUFFICIENT,
    OPTION_NONE,
    OPTION_SPECIALIST,
    class_option_id,
)


@dataclass(frozen=True)
class Option:
    id: str
    label: str


def options_for(group: str) -> tuple[Option, ...]:
    """Same list at every difficulty, so the level never leaks through the options.

    Class options carry only the number and the codes; the class name is shown after the answer.
    """
    catalog = load_catalog()
    classes = [
        Option(class_option_id(cid), T.option_label_class(cid, catalog.classes[cid].codes))
        for cid in GROUP_BY_ID[group].classes
    ]
    return (
        *classes,
        Option(OPTION_NONE, T.OPTION_LABEL_NONE),
        Option(OPTION_SPECIALIST, T.OPTION_LABEL_SPECIALIST),
        Option(OPTION_INSUFFICIENT, T.OPTION_LABEL_INSUFFICIENT),
    )
