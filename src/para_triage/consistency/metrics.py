"""Metrics of image-and-report check (design note section 8), all at evidence level N1 (synthetic data, our labels).

* Wilson 95% intervals for proportions.
* A bootstrap by IMAGE for aggregates: the seven pairs of one image are not independent, so whole
  images are resampled, never single pairs. Seeded, so it reproduces.
* A table by level and by kind of planted error, always with the size of the set beside it, plus
  the false-alarm rate on the consistent pairs, the "não sei" rate, the confusion matrix of the
  three verdicts, and the accuracy of each component (image reading, report reading) per attribute.

Pairs the planted error left indistinguishable, and pairs that could not be built, are not in the
rates: they are counted in their own columns so nothing is hidden.

Language rule: the word "acurácia" only appears next to "N1".
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Iterable, Mapping, Sequence

import numpy as np

from .compare import CONFERE, NAO_CONFERE, NAO_SEI, VERDICTS
from .errors import ERROR_KINDS, INDISTINGUISHABLE, KINDS, NOT_APPLICABLE, NOISE, CONSISTENT, OK, Pair
from .pipeline import Outcome
from .schema import ATTRIBUTES

Z95 = 1.959963984540054
EVIDENCE = "Evidência: N1 (dado sintético, rótulos nossos). Aviso para revisão humana, não decisão."


def wilson(successes: int, n: int, z: float = Z95) -> tuple[float, float]:
    """Wilson score interval. For n == 0 it is the whole [0, 1]."""
    if n <= 0:
        return (0.0, 1.0)
    if not 0 <= successes <= n:
        raise ValueError("successes must be between 0 and n")
    p = successes / n
    denominator = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denominator
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    low = 0.0 if successes == 0 else max(0.0, center - half)  # exact at the ends, not off by a rounding error
    high = 1.0 if successes == n else min(1.0, center + half)
    return (low, high)


def bootstrap_by_image(per_image: Mapping[str, tuple[int, int]], draws: int = 2000, seed: int = 0, level: float = 0.95) -> tuple[float, float]:
    """Percentile interval of `sum(successes) / sum(trials)` resampling whole images with replacement.

    `per_image` maps an image id to (successes, trials). Images with no trials are ignored."""
    cells = [v for _, v in sorted(per_image.items()) if v[1] > 0]
    if not cells:
        return (0.0, 1.0)
    successes = np.array([c[0] for c in cells], float)
    trials = np.array([c[1] for c in cells], float)
    pick = np.random.RandomState(seed).randint(0, len(cells), size=(draws, len(cells)))
    rates = successes[pick].sum(axis=1) / trials[pick].sum(axis=1)
    tail = (1 - level) / 2 * 100
    low, high = np.percentile(rates, [tail, 100 - tail])
    return (float(low), float(high))


@dataclass(frozen=True)
class Row:
    level: int
    kind: str  # a kind of pair, or "all errors" / "all consistent" for the aggregates
    pairs: int  # in the rates
    images: int
    correct: int
    rate: float
    wilson: tuple[float, float]
    bootstrap: tuple[float, float]
    verdicts: Mapping[str, int]
    indistinguishable: int
    not_applicable: int
    redirected: int


@dataclass(frozen=True)
class Summary:
    rows: list[Row]
    false_alarm: dict[int, Row]  # per level: share of "não confere" among consistent and noisy pairs
    unsure_rate: dict[int, tuple[int, int]]  # per level: ("não sei", all pairs in the rates)
    confusion: dict[int, dict[str, dict[str, int]]]  # level -> expected -> got -> count
    components: dict[int, dict[str, dict[str, tuple[int, int]]]]  # level -> "image"/"report" -> attribute -> (right, total)
    wrong_by_locus: dict[int, Counter] = field(default_factory=dict)
    verdict_chance: dict[int, tuple[str, int, int]] = field(default_factory=dict)  # level -> (most common expected verdict, its count, pairs)


def _make_row(level: int, kind: str, outs: Sequence[Outcome], hit, draws: int, seed: int, excluded: Mapping[str, int]) -> Row:
    used = [o for o in outs if o.status == OK]
    per_image: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for o in used:
        per_image[o.image_id][0] += int(hit(o))
        per_image[o.image_id][1] += 1
    correct = sum(v[0] for v in per_image.values())
    n = len(used)
    return Row(
        level=level, kind=kind, pairs=n, images=len(per_image), correct=correct, rate=(correct / n if n else float("nan")),
        wilson=wilson(correct, n), bootstrap=bootstrap_by_image({k: tuple(v) for k, v in per_image.items()}, draws, seed),
        verdicts=dict(Counter(o.got for o in used)), indistinguishable=excluded.get(INDISTINGUISHABLE, 0),
        not_applicable=excluded.get(NOT_APPLICABLE, 0), redirected=sum(1 for o in used if o.note == "redirected"),
    )


def summarize(outcomes: Iterable[Outcome], pairs: Iterable[Pair] = (), draws: int = 1000, seed: int = 0) -> Summary:
    """`pairs` (all of them, built or not) lets the table count the not-applicable ones; without it only built pairs are known."""
    outcomes = list(outcomes)
    pairs = list(pairs)
    levels = sorted({o.level for o in outcomes})
    level_of = {o.image_id: o.level for o in outcomes}
    rows: list[Row] = []
    false_alarm: dict[int, Row] = {}
    unsure: dict[int, tuple[int, int]] = {}
    confusion: dict[int, dict[str, dict[str, int]]] = {}
    components: dict[int, dict[str, dict[str, tuple[int, int]]]] = {}
    wrong_by_locus: dict[int, Counter] = {}
    verdict_chance: dict[int, tuple[str, int, int]] = {}
    for level in levels:
        mine = [o for o in outcomes if o.level == level]
        skipped = Counter()
        for p in pairs:
            if level_of.get(p.image_id) == level and p.status == NOT_APPLICABLE:
                skipped[(p.kind, NOT_APPLICABLE)] += 1
        for kind in KINDS:
            of_kind = [o for o in mine if o.kind == kind]
            excluded = {INDISTINGUISHABLE: sum(1 for o in of_kind if o.status == INDISTINGUISHABLE), NOT_APPLICABLE: skipped[(kind, NOT_APPLICABLE)]}
            rows.append(_make_row(level, kind, of_kind, lambda o: o.correct, draws, seed, excluded))
        errors = [o for o in mine if o.kind in ERROR_KINDS]
        rows.append(_make_row(level, "all errors", errors, lambda o: o.correct, draws, seed, {
            INDISTINGUISHABLE: sum(1 for o in errors if o.status == INDISTINGUISHABLE), NOT_APPLICABLE: sum(v for (k, s), v in skipped.items() if k in ERROR_KINDS)}))
        consistent = [o for o in mine if o.kind in (CONSISTENT, NOISE)]
        false_alarm[level] = _make_row(level, "false alarm", consistent, lambda o: o.got == NAO_CONFERE, draws, seed, {})
        used = [o for o in mine if o.status == OK]
        unsure[level] = (sum(1 for o in used if o.got == NAO_SEI), len(used))
        matrix = {e: {g: 0 for g in VERDICTS} for e in VERDICTS}
        for o in used:
            matrix[o.expected][o.got] += 1
        confusion[level] = matrix
        shares = Counter(o.expected for o in used)
        top = max(VERDICTS, key=lambda v: (shares[v], -VERDICTS.index(v))) if used else CONFERE
        verdict_chance[level] = (top, shares[top], len(used))
        by_image, by_report = {}, []
        for o in mine:
            by_image.setdefault(o.image_id, (o.image_true, o.image_read))
            by_report.append((o.report_true, o.report_read))
        components[level] = {
            "image": {a: (sum(getattr(t, a) == getattr(r, a) for t, r in by_image.values()), len(by_image)) for a in ATTRIBUTES},
            "report": {a: (sum(getattr(t, a) == getattr(r, a) for t, r in by_report), len(by_report)) for a in ATTRIBUTES},
        }
        wrong_by_locus[level] = Counter(o.locus for o in used if not o.correct)
    return Summary(rows, false_alarm, unsure, confusion, components, wrong_by_locus, verdict_chance)


def _pct(x: float) -> str:
    return "—" if x != x else f"{100 * x:.1f}%"


def format_summary(summary: Summary) -> str:
    """Plain Markdown. Every rate has its n beside it, and the evidence line comes first."""
    out = [EVIDENCE, ""]
    for level in sorted(summary.confusion):
        out += [f"### Nível {level}", "", "| tipo | pares | imagens | taxa de aviso correto (N1) | Wilson 95% | bootstrap por imagem 95% | confere | não confere | não sei | indistinguíveis | não aplicáveis | redirecionados |",
                "|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in (r for r in summary.rows if r.level == level):
            v = r.verdicts
            out.append(
                f"| {r.kind} | {r.pairs} | {r.images} | {_pct(r.rate)} | {_pct(r.wilson[0])} a {_pct(r.wilson[1])} | {_pct(r.bootstrap[0])} a {_pct(r.bootstrap[1])} | "
                f"{v.get(CONFERE, 0)} | {v.get(NAO_CONFERE, 0)} | {v.get(NAO_SEI, 0)} | {r.indistinguishable} | {r.not_applicable} | {r.redirected} |"
            )
        fa = summary.false_alarm[level]
        unsure_n, unsure_total = summary.unsure_rate[level]
        top, top_count, top_total = summary.verdict_chance[level]
        out += ["", f"Chute do veredito (dar sempre \"{top}\", o mais comum): {top_count} de {top_total} pares ({_pct(top_count / top_total if top_total else float('nan'))}), Wilson {_pct(wilson(top_count, top_total)[0])} a {_pct(wilson(top_count, top_total)[1])}. É o piso para os números acima.",
                f"Falso alarme (\"não confere\" nos pares consistentes e com ruído): {fa.correct} de {fa.pairs} ({_pct(fa.rate)}), Wilson {_pct(fa.wilson[0])} a {_pct(fa.wilson[1])}.",
                f"\"Não sei\": {unsure_n} de {unsure_total} pares ({_pct(unsure_n / unsure_total if unsure_total else float('nan'))}).", "",
                "Matriz de confusão (linhas: veredito esperado; colunas: veredito dado):", "", "| esperado \\ dado | " + " | ".join(VERDICTS) + " |", "|---|---|---|---|"]
        for e in VERDICTS:
            out.append(f"| {e} | " + " | ".join(str(summary.confusion[level][e][g]) for g in VERDICTS) + " |")
        out += ["", "Componentes (certos de total, por atributo):", ""]
        for part, label in (("image", "leitura da imagem"), ("report", "leitura do laudo")):
            cells = summary.components[level][part]
            out.append(f"- {label}: " + "; ".join(f"{a} {c[0]}/{c[1]}" for a, c in cells.items()))
        if summary.wrong_by_locus[level]:
            out.append("- onde estão os vereditos errados: " + "; ".join(f"{k} {v}" for k, v in sorted(summary.wrong_by_locus[level].items())))
        out.append("")
    return "\n".join(out)
