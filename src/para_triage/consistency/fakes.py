"""Fake extractors for the tests (and for later smoke tests): no model, no pixel reading.

`oracle_*` return the true label (looked up by the PNG bytes or by the text), so a pipeline run
with them must reproduce the expected verdicts exactly. The `flip_sides`, `shift_level` and
`say_unknown` wrappers plant a failure of a known kind in any extractor.
"""
from __future__ import annotations

from typing import Callable, Iterable, Mapping

from .errors import Pair
from .schema import LIMB_FIELDS, UNKNOWN, Attrs
from .errors import LEVELS_OF


def oracle_image_extractor(records: Iterable) -> Callable[[bytes], Attrs]:
    table = {r.png: r.attrs for r in records}
    return table.__getitem__


def oracle_report_extractor(pairs: Iterable[Pair]) -> Callable[[str], Attrs]:
    table: dict[str, Attrs] = {}
    for p in pairs:
        if p.content is None:
            continue
        if p.text in table and table[p.text] != p.content.attrs:
            raise ValueError("two different labels were rendered as the same text")
        table[p.text] = p.content.attrs
    return table.__getitem__


def flip_sides(extractor: Callable) -> Callable:
    """Reads everything right but returns left for right and right for left."""
    return lambda item: extractor(item).swapped_sides()


def shift_level(extractor: Callable, name: str, step: int = 1) -> Callable:
    """Reads everything right except `name`, which comes one step off (towards the other end if it would leave the domain)."""
    def read(item) -> Attrs:
        attrs = extractor(item)
        value = getattr(attrs, name)
        if value == UNKNOWN:
            return attrs
        new = value + step if value + step in LEVELS_OF[name] else value - step
        return attrs.with_(**{name: new})
    return read


def say_unknown(extractor: Callable, names: Iterable[str] = LIMB_FIELDS) -> Callable:
    """Reads everything right except `names`, which come back `?`."""
    return lambda item: extractor(item).with_(**{n: UNKNOWN for n in names})


def by_table(table: Mapping, default: Attrs = Attrs()) -> Callable:
    return lambda item: table.get(item, default)
