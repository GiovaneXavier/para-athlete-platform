"""Which split the paper outputs are being written for.

Kept apart from `paper_outputs` because that module runs as `__main__` while the modules that write E7 import it
under its package name: two copies, so state kept inside it would not be shared.
"""
from __future__ import annotations

from contextlib import contextmanager

VARIANT = {"macro": "", "file": ""}


@contextmanager
def variant(macro_suffix: str = "", file_suffix: str = ""):
    """Writes the outputs of another split: macro names get `macro_suffix`, table and figure files `file_suffix`.

    With the suffix "Row" every macro is defined twice: under its plain name and with the suffix.
    """
    previous = dict(VARIANT)
    VARIANT.update(macro=macro_suffix, file=file_suffix)
    try:
        yield
    finally:
        VARIANT.update(previous)


def figname(name: str) -> str:
    """File name of a figure or table with the suffix of the split being written."""
    stem, dot, ext = name.rpartition(".")
    return f"{stem}{VARIANT['file']}{dot}{ext}"
