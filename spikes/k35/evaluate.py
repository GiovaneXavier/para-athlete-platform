"""Builds every table of the report from a trained network and a set of splits (dev or test). Needs torch only to read the network.

The same code serves the development checkpoint (`dev.py`) and the one run on the test set (`final.py`), so what is looked at on the
development set is exactly what will be looked at on the test set.
"""
from __future__ import annotations

import json
from collections import Counter

import numpy as np
import torch

from . import analysis as an
from . import data, forms, paths
from .labels import HEADS, LIMBS
from .net import SmallNet, predict

DIRECTORY_BANDS = {1: [("nível 1", -1)], 2: [("faixa 0", 0), ("faixa 1", 1), ("faixa 2", 2), ("faixa 3", 3)]}


def load_model(name: str) -> SmallNet:
    model = SmallNet()
    model.load_state_dict(torch.load(paths.RUNS / f"{name}.pt", map_location="cpu"))
    model.eval()
    return model


def read_split(model: SmallNet, split: data.Split) -> dict:
    probs = predict(model, split.x)
    flipped = predict(model, split.x, flip=True)
    idx, conf = an.readings(probs)
    idx_f, _ = an.readings(flipped)
    return {"idx": idx, "conf": conf, "idx_flipped": idx_f}


def md_table(header: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(out)


def sizes_section(splits: dict[int, data.Split]) -> str:
    rows = []
    for level, sp in splits.items():
        for label, band in DIRECTORY_BANDS[level]:
            m = sp.band == band
            unknown = int(sum((sp.y[m][:, j] == _unk(name)).sum() for j, name in enumerate(LIMBS)))
            rows.append([f"nível {level}", sp.name, label, str(int(m.sum())), str(int((m & sp.held).sum())), str(int((m & ~sp.held).sum())), str(unknown)])
    return md_table(["nível", "conjunto", "faixa", "imagens", "de combinações seguradas", "de combinações vistas", "membros `?` no rótulo da imagem"], rows)


def _unk(name: str) -> int:
    from .labels import N_CLASSES
    return N_CLASSES[name] - 1


def attribute_section(splits, reads, classical=None, train_y=None) -> tuple[str, dict]:
    """Attribute accuracy against the IMAGE label (N1), by level and band: the network, the network only where the picture shows the
    attribute, the classical reader and the best constant guess. Returns the markdown and the raw (k, n) pairs for the hypotheses."""
    raw, rows = {}, []
    for level, sp in splits.items():
        r = reads[level]
        for label, band in DIRECTORY_BANDS[level]:
            m = sp.band == band
            tabs = {"rede": an.attribute_hits(r["idx"], sp.y, m), "rede (só onde a imagem mostra o atributo)": an.visible_hits(r["idx"], sp.y, m)}
            if classical is not None:
                tabs["clássica (só membros)"] = an.classical_hits(classical[level], sp.y, m)
            if train_y is not None:
                tabs["melhor chute constante"] = an.majority_hits(train_y[level], sp.y, m)
            for who, hits in tabs.items():
                raw[(level, band, who)] = hits
                rows.append([f"{label} (n={int(m.sum())})", who] + [an.interval(*hits[h]) if h in hits else "n/a" for h in HEADS])
    return md_table(["conjunto", "leitor"] + list(HEADS), rows), raw


def mirror_section(splits, reads) -> str:
    rows = []
    for level, sp in splits.items():
        r = reads[level]
        for label, band in DIRECTORY_BANDS[level]:
            m = sp.band == band
            c = an.mirror_consistency(r["idx"], r["idx_flipped"], m)
            rows.append([f"{label}"] + [an.interval(*c[k]) for k in list(LIMBS) + ["all four limbs"]])
    return md_table(["conjunto"] + list(LIMBS) + ["os quatro membros juntos"], rows)


def calibration_section(splits, reads) -> str:
    rows = []
    for level, sp in splits.items():
        r = reads[level]
        for label, band in DIRECTORY_BANDS[level]:
            m = sp.band == band
            c = an.calibration(r["idx"], r["conf"], sp.y, m)
            rows.append([label, f"{c['ece']:.3f}", f"{c['mean_confidence']:.3f}", f"{c['accuracy']:.3f}", str(c["n"] // 4)])
    return md_table(["conjunto", "ECE (10 faixas)", "confiança média", "acerto dos membros", "imagens"], rows)


def class_section(splits, reads, classical=None) -> tuple[str, dict]:
    """The automatic class, by level and band: the image arm (network), the network with the true posture, and the classical reader with the true posture."""
    rows, raw = [], {}
    for level, sp in splits.items():
        r = reads[level]
        for label, band in DIRECTORY_BANDS[level]:
            m = sp.band == band
            arms = {"imagem (rede)": an.class_arms(sp, r["idx"], level, m)}
            if level == 2:
                arms["imagem (rede), postura verdadeira"] = an.class_arms(sp, r["idx"], level, m, oracle_posture=True)
            if classical is not None:
                arms["clássica, postura verdadeira"] = an.classical_class(sp, classical[level], level, m)
            for who, a in arms.items():
                raw[(level, band, who)] = a
                lo = an.boot(a["flags"]) if a["n"] else (0, 1)
                rows.append([label, who, an.interval(a["ok"], a["n"]), f"{100 * lo[0]:.1f} a {100 * lo[1]:.1f}", f"{100 * a['undecided'] / max(a['n'], 1):.1f}% ({a['undecided']}/{a['n']})",
                             an.interval(a["ok_nonempty"], a["n_nonempty"])])
    return md_table(["conjunto", "leitor", "classe correta (todas as imagens)", "bootstrap 95%", "não decidiu", "classe correta só onde a classe verdadeira não é vazia"], rows), raw


def form_section(splits, reads, tau: float, only_level: int | None = None) -> tuple[str, dict]:
    rows, raw = [], {}
    for level, sp in splits.items():
        if only_level and level != only_level:
            continue
        r = reads[level]
        grid = an.form_grid(sp, r["idx"], r["conf"], level, np.ones(len(sp), bool), tau)
        raw[level] = grid
        for cell, g in grid.items():
            n = g["n"]
            rows.append([f"nível {level}", f"{int(cell[0] * 100)}%", f"{int(cell[1] * 100)}%", an.interval(g["form_ok"], n), an.interval(g["fusion_ok"], n),
                         f"{100 * g['fusion_review'] / n:.1f}%", an.interval(g["error_flagged"], g["form_with_error"]), an.interval(g["clean_flagged"], g["form_clean"]),
                         f"{100 * g['form_undecided'] / n:.1f}% / {100 * g['fusion_undecided'] / n:.1f}%"])
    header = ["nível", "campos faltando", "campos errados", "formulário: classe correta", "fusão: classe automática correta", "fusão: revisar", "revisar quando o formulário tem erro",
              "revisar quando o formulário não tem erro", "não decidiu (formulário / fusão)"]
    return md_table(header, rows), raw


def run_dev_report(name: str) -> str:
    model = load_model(name)
    splits = {1: data.load(1, "dev"), 2: data.load(2, "dev")}
    reads = {lv: read_split(model, sp) for lv, sp in splits.items()}
    train_y = {lv: data.load(lv, "train").y for lv in (1, 2)}
    tau, scores = an.choose_tau({lv: (splits[lv], reads[lv]["idx"], reads[lv]["conf"]) for lv in splits})
    (paths.RUNS / f"tau_{name}.json").write_text(json.dumps({"tau": tau, "scores": scores}), encoding="utf-8")
    text = ["## Conjunto de desenvolvimento (a única coisa vista antes da rodada do teste)", "", f"Limiar da fusão escolhido no desenvolvimento: **{tau}** (bons resultados por limiar: " + ", ".join(f"{k}: {v:.3f}" for k, v in scores.items()) + ").", ""]
    text += ["### Tamanhos", sizes_section(splits), ""]
    t, _ = attribute_section(splits, reads, None, train_y)
    text += ["### Acerto por atributo contra o rótulo da imagem (N1)", t, ""]
    text += ["### Consistência do espelho", mirror_section(splits, reads), ""]
    text += ["### Calibração", calibration_section(splits, reads), ""]
    t, _ = class_section(splits, reads, None)
    text += ["### Classe (braço da imagem)", t, ""]
    t, _ = form_section(splits, reads, tau)
    text += ["### Formulário e fusão", t, ""]
    return "\n".join(text)
