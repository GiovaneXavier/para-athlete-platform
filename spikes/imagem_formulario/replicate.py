"""REPLICATION, training seed 1, no tuning. The test set had ALREADY been opened (`final.py`, run 1, seed 0). This script is separate on purpose:
`final.py` refuses a second run and is not touched. Here the network of seed 1 (`run2`, same configuration, same data and splits, only the training
seed differs) is read on the test set with the fusion threshold FIXED at 0.5 (the value chosen on the development set for seed 0, not chosen again),
and H1 to H4 are re-evaluated with the same criteria. Nothing is chosen between the two seeds: both are reported side by side.

It also computes, AFTER the test (analysis not planned before it), the classical baseline and the best constant guess on the visible slice
(image label different from `?`) beside the network of each seed.

    PYTHONPATH=src;spikes  python -m imagem_formulario.replicate --first run1 --second run2
"""
from __future__ import annotations

import argparse
import json
import sys
import time

import numpy as np

from . import analysis as an
from . import classical, data, evaluate, final, paths
from .labels import HEADS, LIMBS

LABEL = "Replicação, semente 1, nenhum ajuste; o teste já tinha sido aberto antes (rodada 1, semente 0). Evidência N1: desenho sintético, rótulos por construção."
TAU = 0.5
BANDS = evaluate.DIRECTORY_BANDS


def pair(a: tuple[int, int], b: tuple[int, int]) -> str:
    return f"{100 * a[0] / a[1]:.1f} / {100 * b[0] / b[1]:.1f} ({an.seed_gap(a, b):+.1f})"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--first", default="run1")
    ap.add_argument("--second", default="run2")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    t0 = time.time()
    tau0 = json.loads((paths.RUNS / f"tau_{args.first}.json").read_text(encoding="utf-8"))["tau"]
    if tau0 != TAU:
        sys.exit(f"The fixed threshold is {TAU}, but the development set of {args.first} chose {tau0}.")
    splits = {1: data.load(1, "test"), 2: data.load(2, "test")}
    train_y = {lv: data.load(lv, "train").y for lv in (1, 2)}
    classical_reads = {lv: classical.read_all(lv, args.workers) for lv in (1, 2)}
    names = [args.first, args.second]
    reads = {n: {lv: evaluate.read_split(evaluate.load_model(n), sp) for lv, sp in splits.items()} for n in names}
    attr = {n: evaluate.attribute_section(splits, reads[n], classical_reads, train_y)[1] for n in names}
    form = {n: evaluate.form_section(splits, reads[n], TAU)[1] for n in names}

    out = [f"# Replicação no conjunto de teste ({time.strftime('%Y-%m-%d %H:%M')})", "", f"**{LABEL}**", f"Limiar da fusão fixo em {TAU} (não reescolhido). Semente 0 = `{args.first}`, semente 1 = `{args.second}`.", ""]

    out += ["## A. Hipóteses H1 a H4, cada semente com os mesmos critérios", ""]
    for n, label in zip(names, ("semente 0", "semente 1")):
        out += [f"### {label} (`{n}`)", final.hypotheses(splits, reads[n], classical_reads, train_y, form[n]), ""]

    out += ["## B. Variação entre as sementes, por célula", "", "Cada célula: semente 0 / semente 1 (diferença em pontos, semente 1 menos semente 0). Acerto contra o rótulo da imagem (N1).", ""]
    rows, gaps = [], []
    for level, sp in splits.items():
        for label, band in BANDS[level]:
            cells = []
            for h in HEADS:
                a, b = attr[names[0]][(level, band, "rede")].get(h), attr[names[1]][(level, band, "rede")].get(h)
                if a is None or a[1] == 0:
                    cells.append("n/a")
                else:
                    cells.append(pair(a, b))
                    gaps.append(abs(an.seed_gap(a, b)))
            rows.append([label] + cells)
    out += [evaluate.md_table(["conjunto"] + list(HEADS), rows), "", f"Diferença absoluta entre as sementes, nas {len(gaps)} células acima: média {np.mean(gaps):.1f} pontos, máxima {np.max(gaps):.1f} pontos.", ""]

    rows = []
    for level, sp in splits.items():
        for label, band in BANDS[level]:
            m = sp.band == band
            cells = []
            for key in list(LIMBS) + ["all four limbs"]:
                a = an.mirror_consistency(reads[names[0]][level]["idx"], reads[names[0]][level]["idx_flipped"], m)[key]
                b = an.mirror_consistency(reads[names[1]][level]["idx"], reads[names[1]][level]["idx_flipped"], m)[key]
                cells.append(pair(a, b))
            rows.append([label] + cells)
    out += ["### Consistência do espelho", evaluate.md_table(["conjunto"] + list(LIMBS) + ["os quatro membros juntos"], rows), ""]

    rows = []
    for level in (2, 1):
        for missing in (0.0, 0.10, 0.30, 0.50):
            for errors in (0.0, 0.05, 0.10):
                g0, g1 = form[names[0]][level][(missing, errors)], form[names[1]][level][(missing, errors)]
                n = g0["n"]
                rows.append([f"nível {level}", f"{int(missing * 100)}%", f"{int(errors * 100)}%", pair((g0["fusion_ok"], n), (g1["fusion_ok"], n)),
                             pair((g0["fusion_review"], n), (g1["fusion_review"], n)), f"{100 * g0['form_ok'] / n:.1f}"])
    out += ["### Fusão: classe automática correta e taxa de revisão", evaluate.md_table(["nível", "faltando", "errados", "classe automática correta (s0 / s1)", "revisar (s0 / s1)", "formulário (é o mesmo nas duas sementes)"], rows), ""]

    out += ["## C. Análise posterior ao teste (NÃO prevista antes): membro visível", "",
            "**Rótulo desta seção: análise posterior ao teste.** Só as imagens em que o rótulo do membro não é `?`. Cada célula: acerto % (k/n). Compara a linha de base clássica, a rede de cada semente e o melhor chute constante entre os rótulos visíveis do treino.", ""]
    rows = []
    sp = splits[2]
    for label, band in BANDS[2]:
        m = sp.band == band
        cl = an.classical_visible_hits(classical_reads[2], sp.y, m)
        ma = an.majority_visible_hits(train_y[2], sp.y, m)
        for name in LIMBS:
            r0 = an.visible_hits(reads[names[0]][2]["idx"], sp.y, m)[name]
            r1 = an.visible_hits(reads[names[1]][2]["idx"], sp.y, m)[name]
            rows.append([label, name, an.interval(*cl[name]), an.interval(*r0), an.interval(*r1), an.interval(*ma[name])])
    out += [evaluate.md_table(["faixa (nível 2)", "membro", "clássica", "rede, semente 0", "rede, semente 1", "melhor chute constante (visíveis)"], rows), ""]
    out += [f"Tempo desta análise: {time.time() - t0:.0f} s.", ""]
    text = "\n".join(out)
    paths.ensure()
    (paths.RUNS / f"replication_{args.second}.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
