"""How hard level 2 is, MEASURED (design note section 4.2, items 1 to 4).

The criterion was written before running: the classical baseline's accuracy per limb attribute must fall by
at least `REQUIRED_DROP` (20 points) from band 0 to band 3. If it does not, the report says level 2 is not
harder and the intensities in `level2.TABLE` are raised, using only this baseline and chance, before any
learned model runs.

Two figures per band, both over the four limb attributes (evidence N1):
* **known**: only the limbs whose true label is a level (what the criterion uses: a drop here is a reading
  difficulty, not just a limb that the picture does not show);
* **all**: every limb, the label `?` counted as a value the reader would have to give.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Callable, Iterable, Sequence

from .metrics import bootstrap_by_image, wilson
from .schema import LIMB_FIELDS, UNKNOWN, Attrs

REQUIRED_DROP = 0.20
DEFAULT_DRAWS = 1000


@dataclass(frozen=True)
class BandRow:
    band: int
    images: int
    known_right: int
    known_total: int
    known_wilson: tuple
    known_bootstrap: tuple
    all_right: int
    all_total: int
    unknown_labels: int  # limbs whose label is `?` in this band

    @property
    def known_rate(self) -> float:
        return self.known_right / self.known_total if self.known_total else float("nan")

    @property
    def all_rate(self) -> float:
        return self.all_right / self.all_total if self.all_total else float("nan")


def score(read: Attrs, truth: Attrs) -> tuple[int, int, int, int]:
    """(right over known limbs, known limbs, right over all limbs, all limbs) for one image."""
    kr = kt = ar = 0
    for name in LIMB_FIELDS:
        t, r = getattr(truth, name), getattr(read, name)
        ar += r == t
        if t != UNKNOWN:
            kt += 1
            kr += r == t
    return kr, kt, ar, len(LIMB_FIELDS)


def band_curve(records: Iterable, extractor: Callable[[bytes], Attrs], draws: int = DEFAULT_DRAWS, seed: int = 0) -> tuple[list[BandRow], dict]:
    """Accuracy of `extractor` per band. Also returns the per-image reads, keyed by image id, so a run is read once."""
    per_band: dict[int, list] = defaultdict(list)
    reads: dict[str, Attrs] = {}
    for r in records:
        read = extractor(r.png)
        reads[r.image_id] = read
        per_band[r.band].append((r.image_id, *score(read, r.attrs), sum(getattr(r.attrs, n) == UNKNOWN for n in LIMB_FIELDS)))
    rows = []
    for band in sorted(per_band):
        cells = per_band[band]
        kr, kt = sum(c[1] for c in cells), sum(c[2] for c in cells)
        rows.append(BandRow(
            band=band, images=len(cells), known_right=kr, known_total=kt, known_wilson=wilson(kr, kt),
            known_bootstrap=bootstrap_by_image({c[0]: (c[1], c[2]) for c in cells}, draws, seed),
            all_right=sum(c[3] for c in cells), all_total=sum(c[4] for c in cells), unknown_labels=sum(c[5] for c in cells),
        ))
    return rows, reads


def verdict_of_drop(rows: Sequence[BandRow]) -> dict:
    """The pre-registered criterion: the drop in the `known` accuracy from the first band to the last."""
    first, last = rows[0], rows[-1]
    drop = first.known_rate - last.known_rate
    monotone = all(a.known_rate >= b.known_rate - 0.02 for a, b in zip(rows, rows[1:]))
    return {"first": first.known_rate, "last": last.known_rate, "drop": drop, "required": REQUIRED_DROP, "harder": drop >= REQUIRED_DROP, "monotone": monotone}


def by_factor(records: Iterable, reads: dict) -> dict:
    """Accuracy over the known limbs by the intensity of each factor (bands 1 to 3 together): which factor hurts."""
    table: dict = {}
    for r in records:
        if r.band == 0:
            continue
        kr, kt, _, _ = score(reads[r.image_id], r.attrs)
        for factor, intensity in r.vector.items():
            cell = table.setdefault(factor, {}).setdefault(intensity, [0, 0])
            cell[0] += kr
            cell[1] += kt
    return {f: {i: (c[0], c[1]) for i, c in sorted(levels.items())} for f, levels in table.items()}


def format_curve(rows: Sequence[BandRow], verdict: dict, version: str) -> str:
    pct = lambda x: "—" if x != x else f"{100 * x:.1f}%"  # noqa: E731
    out = [f"Tabela de intensidades `{version}`. Evidência: N1 (dado sintético nosso).", "",
           "| faixa | imagens | membros com nível conhecido | acerto da linha de base clássica (N1) | Wilson 95% | bootstrap por imagem 95% | acerto contando `?` como valor | membros `?` |",
           "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        out.append(f"| {r.band} | {r.images} | {r.known_total} | {pct(r.known_rate)} ({r.known_right}/{r.known_total}) | {pct(r.known_wilson[0])} a {pct(r.known_wilson[1])} | "
                   f"{pct(r.known_bootstrap[0])} a {pct(r.known_bootstrap[1])} | {pct(r.all_rate)} | {r.unknown_labels} |")
    out += ["", f"Critério escrito antes de rodar: queda de pelo menos {100 * verdict['required']:.0f} pontos da faixa 0 para a última. "
            f"Medido: {100 * verdict['drop']:.1f} pontos ({pct(verdict['first'])} para {pct(verdict['last'])}). "
            f"**{'O nível 2 conta como mais difícil.' if verdict['harder'] else 'O nível 2 NÃO é mais difícil: as intensidades têm de subir.'}** "
            f"Curva {'descendo' if verdict['monotone'] else 'não monótona'}."]
    return "\n".join(out)
