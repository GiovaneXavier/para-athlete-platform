"""THE one run on the test set. It writes the tables of the report and refuses to run twice.

    PYTHONPATH=src;spikes  python -m k35.final --name run1
    PYTHONPATH=src;spikes  python -m k35.final --name run1 --bugfix "what the code bug was"   (only for a bug in the CODE, never to retune)

A marker file outside the repository records every run. A second run is allowed only with `--bugfix` and a reason; both runs are
kept and both must be reported with what changed. Nothing is ever retuned after seeing the test: the threshold of the fusion and
the weights come from the development set.
"""
from __future__ import annotations

import argparse
import json
import sys
import time

import numpy as np

from para_triage.consistency.metrics import wilson

from . import analysis as an
from . import classical, data, evaluate, forms, paths
from .labels import LIMBS

EVIDENCE = "Evidência N1: desenho sintético, rótulos por construção. Aviso para revisão humana, não decisão."


def paired_ci(a: list[bool], b: list[bool], draws: int = 2000, seed: int = 0) -> tuple[float, float, float]:
    """Mean difference a - b over the same images, with a bootstrap by image 95% interval."""
    d = np.array(a, float) - np.array(b, float)
    pick = np.random.RandomState(seed).randint(0, len(d), size=(draws, len(d)))
    means = d[pick].mean(axis=1)
    return float(d.mean()), float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def hypotheses(splits, reads, classical_reads, train_y, form_raw) -> str:
    lines = ["| hipótese | o que mede | resultado | veredito |", "|---|---|---|---|"]
    notes = []
    # H1 and H2: the network against the classical reader, by band, limb attributes, test images of every combination
    for h, bands, test in (("H1", (0, 1), "rede >= limite inferior do Wilson da clássica"), ("H2", (2, 3), "limite inferior do Wilson da rede > acerto da clássica")):
        holds, parts = 0, []
        sp, r = splits[2], reads[2]
        for band in bands:
            m = sp.band == band
            net = an.attribute_hits(r["idx"], sp.y, m)
            cl = an.classical_hits(classical_reads[2], sp.y, m)
            for name in LIMBS:
                (kn, n), (kc, _) = net[name], cl[name]
                lo_n, _ = wilson(kn, n)
                lo_c, _ = wilson(kc, n)
                ok = (kn / n >= lo_c) if h == "H1" else (lo_n > kc / n)
                holds += ok
                parts.append(f"faixa {band} {name}: rede {100 * kn / n:.1f}% contra clássica {100 * kc / n:.1f}%{' ok' if ok else ' NÃO'}")
        total = 4 * len(bands)
        lines.append(f"| {h} | {test}; nível 2, faixas {bands[0]} e {bands[1]}, 4 membros | {holds} de {total} comparações | **{'confirmada' if holds == total else 'NÃO confirmada' if holds < total else ''}** |")
        notes.append(f"{h}: " + "; ".join(parts))
    # H3: fusion class against form class, level 2, errors 0, missing 10, 30, 50
    grid, parts, holds = form_raw[2], [], 0
    for missing in (0.10, 0.30, 0.50):
        g = grid[(missing, 0.0)]
        mean, lo, hi = paired_ci(g["fusion_flags"], g["form_flags"])
        ok = lo > 0
        holds += ok
        parts.append(f"{int(missing * 100)}% faltando: fusão {100 * g['fusion_ok'] / g['n']:.1f}% contra formulário {100 * g['form_ok'] / g['n']:.1f}%, diferença {100 * mean:+.1f} pontos (bootstrap {100 * lo:+.1f} a {100 * hi:+.1f}){' ok' if ok else ' NÃO'}")
    lines.append(f"| H3 | classe automática da fusão contra a do formulário, nível 2, 0% de erros, 10/30/50% faltando | {holds} de 3 | **{'confirmada' if holds == 3 else 'NÃO confirmada'}** |")
    notes.append("H3 (nível 2): " + "; ".join(parts))
    grid1, parts1 = form_raw[1], []
    for missing in (0.10, 0.30, 0.50):
        g = grid1[(missing, 0.0)]
        mean, lo, hi = paired_ci(g["fusion_flags"], g["form_flags"])
        parts1.append(f"{int(missing * 100)}%: {100 * mean:+.1f} pontos (bootstrap {100 * lo:+.1f} a {100 * hi:+.1f})")
    notes.append("H3 (nível 1, só para informar): " + "; ".join(parts1))
    # H4: held-out combinations
    holds, parts = 0, []
    for level in (1, 2):
        sp, r = splits[level], reads[level]
        held, seen = sp.held, ~sp.held
        nh, ns = an.attribute_hits(r["idx"], sp.y, held), an.attribute_hits(r["idx"], sp.y, seen)
        ch, cs = an.majority_hits(train_y[level], sp.y, held), an.majority_hits(train_y[level], sp.y, seen)
        for name in LIMBS:
            (kh, n_h), (ks, n_s) = nh[name], ns[name]
            lo_h, _ = wilson(kh, n_h)
            chance_h, chance_s = ch[name][0] / ch[name][1], cs[name][0] / cs[name][1]
            acc_h, acc_s = kh / n_h, ks / n_s
            above = lo_h > chance_h
            keeps = (acc_h - chance_h) > 0.5 * (acc_s - chance_s)
            ok = above and keeps
            holds += ok
            parts.append(f"nível {level} {name}: vistas {100 * acc_s:.1f}% (acaso {100 * chance_s:.1f}%), seguradas {100 * acc_h:.1f}% (acaso {100 * chance_h:.1f}%; limite inferior {100 * lo_h:.1f}%){' ok' if ok else ' NÃO'}")
    lines.append(f"| H4 | combinações seguradas: acima do melhor chute constante e mais da metade da vantagem das vistas; 2 níveis x 4 membros | {holds} de 8 | **{'confirmada' if holds == 8 else 'NÃO confirmada'}** |")
    notes.append("H4: " + "; ".join(parts))
    return "\n".join(lines) + "\n\n" + "\n".join(f"- {n}" for n in notes)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="run1")
    ap.add_argument("--bugfix", default="", help="reason, to run again after a bug in the CODE (never to retune)")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    runs = paths.FINAL_MARKER.read_text(encoding="utf-8").splitlines() if paths.FINAL_MARKER.exists() else []
    if runs and not args.bugfix:
        sys.exit(f"The test set was already used ({len(runs)} run(s) recorded in {paths.FINAL_MARKER}). Refusing to run again without --bugfix 'reason'.")
    n_run = len(runs) + 1
    t0 = time.time()
    tau = json.loads((paths.RUNS / f"tau_{args.name}.json").read_text(encoding="utf-8"))["tau"]
    model = evaluate.load_model(args.name)
    splits = {1: data.load(1, "test"), 2: data.load(2, "test")}
    train_y = {lv: data.load(lv, "train").y for lv in (1, 2)}
    t1 = time.time()
    reads = {lv: evaluate.read_split(model, sp) for lv, sp in splits.items()}
    t_net = time.time() - t1
    t2 = time.time()
    classical_reads = {lv: classical.read_all(lv, args.workers) for lv in (1, 2)}
    t_classical = time.time() - t2

    out = [f"# Rodada {n_run} no conjunto de teste ({time.strftime('%Y-%m-%d %H:%M')})", "", EVIDENCE, f"Limiar da fusão (do desenvolvimento): {tau}.", ""]
    if args.bugfix:
        out += [f"Rodada repetida depois de um erro de CÓDIGO: {args.bugfix}", ""]
    out += ["## Tamanhos", evaluate.sizes_section(splits), ""]
    t, _ = evaluate.attribute_section(splits, reads, classical_reads, train_y)
    out += ["## Acerto por atributo contra o rótulo da imagem", t, ""]
    out += ["## Consistência do espelho (leitura da imagem espelhada igual à original com os lados trocados)", evaluate.mirror_section(splits, reads), ""]
    out += ["## Calibração da rede", evaluate.calibration_section(splits, reads), ""]
    t, _ = evaluate.class_section(splits, reads, classical_reads)
    out += ["## Classe pelas regras, braço da imagem e linha de base clássica", t, ""]
    t, form_raw = evaluate.form_section(splits, reads, tau)
    out += ["## Formulário e fusão (curva do formulário)", t, ""]
    out += ["## Hipóteses", hypotheses(splits, reads, classical_reads, train_y, form_raw), ""]
    n_images = sum(len(s) for s in splits.values())
    out += ["## Tempos desta rodada", f"- leitura da rede em {n_images} imagens (e as espelhadas): {t_net:.0f} s ({1000 * t_net / (2 * n_images):.0f} ms por leitura)",
            f"- linha de base clássica nas mesmas imagens: {t_classical:.0f} s (em {args.workers} processos; pode vir do cache de uma execução anterior)", f"- total: {time.time() - t0:.0f} s", ""]
    text = "\n".join(out)
    paths.ensure()
    (paths.RUNS / f"final_run{n_run}.md").write_text(text, encoding="utf-8")
    with paths.FINAL_MARKER.open("a", encoding="utf-8") as f:
        f.write(f"run {n_run} {time.strftime('%Y-%m-%d %H:%M')} {args.name} {'bugfix: ' + args.bugfix if args.bugfix else ''}\n")
    print(text)


if __name__ == "__main__":
    main()
