"""The comparator (design note section 3.2) and the three output texts (section 3.3).

A pure function: no model, no randomness, no clock. Per attribute, with the image value `i` and
the report value `l`:

    i known, l known and equal      -> ok
    i known, l known and different  -> divergence
    i known, l == ?                 -> gap (the report is silent about something the image shows)
    i == ?,  l known                -> gap (the report claims what the image cannot confirm)
    i == ?,  l == ?                 -> ignored

Overall: any divergence -> "não confere" (listing the fields); else any gap -> "não sei";
else at least one ok -> "confere"; else (everything `?`) -> "não sei".

The result is a warning for human review, never a decision. The texts never say "elegível",
"rejeitado" or speak of a class.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .schema import ATTRIBUTES, UNKNOWN, Attrs

OK = "ok"
DIVERGENCE = "divergence"
GAP = "gap"
IGNORED = "ignored"

CONFERE = "confere"
NAO_CONFERE = "não confere"
NAO_SEI = "não sei"
VERDICTS = (CONFERE, NAO_CONFERE, NAO_SEI)

# How each field is named for the reader (person's side).
FIELD_NAMES = {
    "lower_left": "membro inferior esquerdo",
    "lower_right": "membro inferior direito",
    "upper_left": "membro superior esquerdo",
    "upper_right": "membro superior direito",
    "wheelchair": "cadeira de rodas",
    "prosthesis": "prótese",
}

REVIEW_NOTE = "Peça revisão humana."
TEXT_CONFERE = "A imagem e o laudo concordam nos campos conferidos. Isto não substitui a revisão humana."
TEXT_NAO_CONFERE = "A imagem e o laudo divergem em: {fields}. " + REVIEW_NOTE
TEXT_NAO_SEI = "Não foi possível conferir: {fields}. " + REVIEW_NOTE
TEXT_NAO_SEI_TUDO = "Não foi possível conferir nenhum campo. " + REVIEW_NOTE


@dataclass(frozen=True)
class Comparison:
    verdict: str
    per_attribute: Mapping[str, str]
    divergent: tuple[str, ...]
    gaps: tuple[str, ...]
    agreed: tuple[str, ...]

    @property
    def fields(self) -> tuple[str, ...]:
        """The fields the verdict names: the divergent ones, or the gaps, or none."""
        if self.verdict == NAO_CONFERE:
            return self.divergent
        if self.verdict == NAO_SEI:
            return self.gaps
        return ()

    def text(self) -> str:
        return render_text(self)


def compare_attribute(image_value, report_value) -> str:
    if image_value == UNKNOWN and report_value == UNKNOWN:
        return IGNORED
    if image_value == UNKNOWN or report_value == UNKNOWN:
        return GAP
    return OK if image_value == report_value else DIVERGENCE


def compare(image: Attrs, report: Attrs, attributes: tuple[str, ...] = ATTRIBUTES) -> Comparison:
    per = {a: compare_attribute(getattr(image, a), getattr(report, a)) for a in attributes}
    divergent = tuple(a for a, r in per.items() if r == DIVERGENCE)
    gaps = tuple(a for a, r in per.items() if r == GAP)
    agreed = tuple(a for a, r in per.items() if r == OK)
    if divergent:
        verdict = NAO_CONFERE
    elif gaps:
        verdict = NAO_SEI
    elif agreed:
        verdict = CONFERE
    else:
        verdict = NAO_SEI
    return Comparison(verdict, per, divergent, gaps, agreed)


def render_text(result: Comparison) -> str:
    named = ", ".join(FIELD_NAMES[f] for f in result.fields)
    if result.verdict == CONFERE:
        return TEXT_CONFERE
    if result.verdict == NAO_CONFERE:
        return TEXT_NAO_CONFERE.format(fields=named)
    return TEXT_NAO_SEI.format(fields=named) if result.gaps else TEXT_NAO_SEI_TUDO
