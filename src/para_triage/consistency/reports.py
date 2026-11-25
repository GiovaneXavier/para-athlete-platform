"""Synthetic reports in Portuguese and a rule-based reader of them (design note sections 5 and 7).

The report is written by us from the label, with phrase templates and variations (order,
vocabulary, "esquerda" or "à esquerda", "transtibial" or "abaixo do joelho"). The truth is the
LABEL, never the text: a model that paraphrases the text does not change it. No sentence comes
from the CPB booklet.

`render_report` is deterministic given the content and the seed. `read_report` is the cheap
rule-based baseline: keywords and regular expressions, no model. It is also what keeps the
generator honest: a test checks that it recovers the label from every clean report.

What a report can say beyond the labels: a clause whose SIDE is missing ("em um dos membros
inferiores, lado não informado"). Its labels are `?` for both sides of that region; the level it
mentions is kept in `ReportContent.unsided` only so the sentence can be written.
"""
from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from typing import Mapping

from .schema import UNKNOWN, Attrs

# region -> (noun, article) forms; the level phrases are noun phrases so every template reads well after "há".
REGIONS = {
    "lower": [("membro inferior", "no"), ("perna", "na")],
    "upper": [("membro superior", "no"), ("braço", "no")],
}
LEVEL_PHRASES = {
    "lower": {
        0: ["ausência de amputação", "membro completo", "membro íntegro"],
        1: ["amputação parcial do pé", "amputação do antepé", "ausência de parte do pé"],
        2: ["amputação abaixo do joelho", "amputação transtibial", "ausência da perna abaixo do joelho"],
        3: ["amputação acima do joelho", "amputação transfemoral", "amputação na altura do joelho ou acima"],
    },
    "upper": {
        0: ["ausência de amputação", "membro completo", "membro íntegro"],
        1: ["amputação no punho ou abaixo do cotovelo", "amputação transradial", "ausência da mão e de parte do antebraço"],
        2: ["amputação no cotovelo ou acima", "amputação transumeral", "amputação acima do cotovelo"],
    },
}
SIDE_WORDS = {"left": {"m": "esquerdo", "f": "esquerda"}, "right": {"m": "direito", "f": "direita"}}
GENDER = {"membro inferior": "m", "membro superior": "m", "perna": "f", "braço": "m"}
FLAG_PHRASES = {
    ("wheelchair", "yes"): ["Usa cadeira de rodas.", "Faz uso de cadeira de rodas."],
    ("wheelchair", "no"): ["Não usa cadeira de rodas.", "Sem uso de cadeira de rodas."],
    ("prosthesis", "yes"): ["Usa prótese.", "Faz uso de prótese."],
    ("prosthesis", "no"): ["Não usa prótese.", "Sem uso de prótese."],
}
EMPTY_REPORT = "Laudo sem informação sobre os membros."
UNSIDED = "Há {level} em um dos {plural}, sem informar o lado ({marker})."
UNSIDED_MARKER = "lado não informado"
PLURALS = {"lower": "membros inferiores", "upper": "membros superiores"}

# Irrelevant sentences for the noisy report: none names a limb, a side, a level, a chair or a prosthesis.
FILLER = [
    "A atleta compareceu à avaliação no horário combinado.",
    "O documento foi emitido a pedido do próprio interessado.",
    "Treina três vezes por semana, em dois turnos.",
    "Nenhuma intercorrência durante o atendimento.",
    "O relatório segue o modelo usado pela equipe local.",
    "Foi entregue uma cópia ao responsável pelo clube.",
    "A avaliação ocorreu em sala reservada e climatizada.",
    "Este texto resume o que foi observado na consulta.",
]
ABBREVIATIONS = [("membro inferior", "MI"), ("membro superior", "MS")]
SIDE_ABBREVIATIONS = {"esquerdo": "esq.", "esquerda": "esq.", "direito": "dir.", "direita": "dir."}


@dataclass(frozen=True)
class ReportContent:
    """What the report says. `attrs` is the label of the report; `unsided` maps a region ("lower" or
    "upper") to a level that the report mentions without saying the side (both sides are then `?`)."""

    attrs: Attrs
    unsided: Mapping[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for region in self.unsided:
            names = ("lower_left", "lower_right") if region == "lower" else ("upper_left", "upper_right")
            if region not in PLURALS or any(getattr(self.attrs, n) != UNKNOWN for n in names):
                raise ValueError(f"an unsided {region!r} clause needs both sides of that region to be `?`")


def _protected_words() -> set[str]:
    words: set[str] = set()
    for region in LEVEL_PHRASES.values():
        for phrases in region.values():
            for phrase in phrases:
                words.update(phrase.split())
    for forms in REGIONS.values():
        for noun, article in forms:
            words.update(noun.split())
            words.add(article)
    for forms in FLAG_PHRASES.values():
        for phrase in forms:
            words.update(w.strip(".").lower() for w in phrase.split())
    words.update(w for sides in SIDE_WORDS.values() for w in sides.values())
    words.update(PLURALS.values())
    words.update(UNSIDED_MARKER.split())
    return {w.lower() for w in words}


PROTECTED = _protected_words()


def _typo(word: str, rng: random.Random) -> str:
    """Swaps two adjacent inner letters. Only words that are not keywords are touched."""
    core = word.rstrip(".,:;")
    if len(core) < 6 or core.lower() in PROTECTED or not core.isalpha():
        return word
    i = rng.randrange(1, len(core) - 2)
    return core[:i] + core[i + 1] + core[i] + core[i + 2 :] + word[len(core) :]


def _limb_clause(region: str, side: str, level: int, rng: random.Random, abbreviate: bool) -> str:
    noun, article = rng.choice(REGIONS[region])
    gender = GENDER[noun]
    side_word = SIDE_WORDS[side][gender]
    phrase = rng.choice(LEVEL_PHRASES[region][level])
    if abbreviate:
        for long, short in ABBREVIATIONS:
            noun = noun.replace(long, short)
        side_word = SIDE_ABBREVIATIONS[side_word]
    template = rng.choice(("A", "B", "C"))
    if template == "A":
        text = f"{noun[0].upper() + noun[1:]} {side_word}: {phrase}."
    elif template == "B":
        text = f"{article.capitalize()} {noun} {side_word}, há {phrase}."
    else:
        text = f"Registra-se {phrase} {article} {noun} {side_word}."
    return text


def render_report(content: ReportContent, seed: str | int, noisy: bool = False) -> str:
    """The report text. With `noisy`, abbreviations, typos in non-keyword words and irrelevant sentences are added
    (design note section 5, error type (f)): none of that changes a fact."""
    rng = random.Random(f"k34-report:{seed}")
    clauses: list[str] = []
    attrs = content.attrs
    for region, sides in (("lower", ("lower_left", "lower_right")), ("upper", ("upper_left", "upper_right"))):
        for name in sides:
            level = getattr(attrs, name)
            if level != UNKNOWN:
                clauses.append(_limb_clause(region, "left" if name.endswith("left") else "right", level, rng, abbreviate=noisy and rng.random() < 0.7))
        if region in content.unsided:
            level = content.unsided[region]
            clauses.append(UNSIDED.format(level=rng.choice(LEVEL_PHRASES[region][level]), plural=PLURALS[region], marker=UNSIDED_MARKER).capitalize())
    for flag in ("wheelchair", "prosthesis"):
        value = getattr(attrs, flag)
        if value != UNKNOWN:
            clauses.append(rng.choice(FLAG_PHRASES[(flag, value)]))
    if not clauses:
        clauses = [EMPTY_REPORT]
    rng.shuffle(clauses)
    if noisy:
        for sentence in rng.sample(FILLER, rng.randint(3, 5)):
            clauses.insert(rng.randrange(len(clauses) + 1), sentence)
        clauses = [" ".join(_typo(w, rng) for w in c.split(" ")) for c in clauses]
    return " ".join(clauses)


# ---------------------------------------------------------------------------------------------
# The rule-based reader


LEVEL_PATTERNS = {
    "lower": [
        (3, r"acima do joelho|transfemoral|altura do joelho"),
        (2, r"abaixo do joelho|transtibial"),
        (1, r"parcial do pé|antepé|parte do pé"),
        (0, r"ausência de amputação|completo|íntegro"),
    ],
    "upper": [
        (2, r"acima do cotovelo|transumeral|cotovelo ou acima"),
        (1, r"abaixo do cotovelo|transradial|antebraço|punho"),
        (0, r"ausência de amputação|completo|íntegro"),
    ],
}
REGION_PATTERNS = {"lower": r"\b(inferior|inferiores|perna|pernas|mi)\b", "upper": r"\b(superior|superiores|braço|braços|ms)\b"}
SENTENCE_BREAK = re.compile(r"(?<=\.)\s+(?=[A-ZÀ-Ú])")


def split_sentences(text: str) -> list[str]:
    """Splits after a period that is followed by a capital letter ("esq." inside a sentence does not break it)."""
    return [s.strip() for s in SENTENCE_BREAK.split(text) if s.strip()]


def read_report(text: str) -> Attrs:
    """Keywords and regular expressions, no model. Anything it does not recognise stays `?`."""
    found: dict[str, int | str] = {}
    for sentence in split_sentences(text):
        low = sentence.lower()
        flagged = False
        for flag, word in (("wheelchair", "cadeira"), ("prosthesis", "prótese")):
            if word in low:
                found[flag] = "no" if re.search(r"\b(não|sem)\b", low) else "yes"
                flagged = True
        if flagged:
            continue
        for region in ("lower", "upper"):
            if not re.search(REGION_PATTERNS[region], low):
                continue
            level = next((lv for lv, pattern in LEVEL_PATTERNS[region] if re.search(pattern, low)), None)
            if level is None or UNSIDED_MARKER in low:
                continue
            for side, pattern in (("left", r"esq"), ("right", r"dir")):
                if re.search(pattern, low):
                    found[f"{region}_{side}"] = level
    return Attrs(**found)
