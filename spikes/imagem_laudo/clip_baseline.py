"""OpenCLIP zero-shot baseline (image-and-report check design note, section 7b). Local files only; the network is not used.

    set PYTHONPATH=src;spikes/imagem_laudo
    <venv-imagem-laudo>\\Scripts\\python.exe spikes/imagem_laudo/clip_baseline.py --level 1

For each pair of sentences ("an amputated LEFT leg" against "an amputated RIGHT leg") CLIP picks the closer one. The
expectation, written before the run, is near 50% on left and right (chance), because CLIP is known to mix up sides and
spatial relations. The same test on the MIRRORED picture (sides swapped in the label) separates "does not know the
side" (the answer does not change with the mirror) from a bias for one side. Evidence level N1 (synthetic data).
"""
from __future__ import annotations

import argparse
import os
import sys
import time

os.environ.setdefault("HF_HUB_OFFLINE", "1")  # the weights are a local file; nothing is fetched

import numpy as np
import torch
import open_clip
from PIL import Image

import paths
import subsets
from extractors import mirrored
from para_triage.consistency.metrics import wilson
from para_triage.consistency.png import decode_png
from para_triage.consistency.schema import UNKNOWN

LOWER_LEVEL_TEXT = {
    0: "a photo of a person with two complete legs",
    1: "a photo of a person with part of a foot missing",
    2: "a photo of a person with a leg amputated below the knee",
    3: "a photo of a person with a leg amputated above the knee",
}
UPPER_LEVEL_TEXT = {
    0: "a photo of a person with two complete arms",
    1: "a photo of a person with a forearm or hand missing",
    2: "a photo of a person with an arm amputated at or above the elbow",
}
SIDE_TEXT = {
    "lower": ("a photo of a person whose LEFT leg is amputated", "a photo of a person whose RIGHT leg is amputated"),
    "upper": ("a photo of a person whose LEFT arm is amputated", "a photo of a person whose RIGHT arm is amputated"),
}
FLAG_TEXT = {
    "wheelchair": ("a photo of a person sitting in a wheelchair", "a photo of a person standing or walking without a wheelchair"),
    "prosthesis": ("a photo of a person wearing a prosthetic limb", "a photo of a person without any prosthetic limb"),
}


def pct(k: int, n: int) -> str:
    if n == 0:
        return "-"
    lo, hi = wilson(k, n)
    return f"{100 * k / n:.1f}% ({k}/{n}; {100 * lo:.1f} a {100 * hi:.1f})"


class Clip:
    def __init__(self):
        torch.set_num_threads(max(1, (os.cpu_count() or 4) // 2))
        self.model, _, self.preprocess = open_clip.create_model_and_transforms("ViT-B-32", pretrained=str(paths.OPENCLIP))
        self.model.eval()
        self.tokenizer = open_clip.get_tokenizer("ViT-B-32")
        self.seconds: list[float] = []

    def text(self, sentences: list[str]) -> torch.Tensor:
        with torch.no_grad():
            t = self.model.encode_text(self.tokenizer(sentences))
        return t / t.norm(dim=-1, keepdim=True)

    def image(self, png: bytes) -> torch.Tensor:
        t0 = time.time()
        pil = Image.fromarray(decode_png(png))
        with torch.no_grad():
            v = self.model.encode_image(self.preprocess(pil).unsqueeze(0))
        self.seconds.append(time.time() - t0)
        return v / v.norm(dim=-1, keepdim=True)

    def choose(self, image_vec: torch.Tensor, text_vecs: torch.Tensor) -> int:
        return int((image_vec @ text_vecs.T).argmax())


def run(level: int) -> str:
    records = subsets.full(level)
    clip = Clip()
    out = [f"CLIP zero-shot (OpenCLIP ViT-B/32 LAION-2B), nível {level}, {len(records)} imagens. Evidência N1.", ""]
    side_txt = {region: clip.text(list(texts)) for region, texts in SIDE_TEXT.items()}
    lower_txt = clip.text([LOWER_LEVEL_TEXT[k] for k in sorted(LOWER_LEVEL_TEXT)])
    upper_txt = clip.text([UPPER_LEVEL_TEXT[k] for k in sorted(UPPER_LEVEL_TEXT)])
    flag_txt = {name: clip.text(list(texts)) for name, texts in FLAG_TEXT.items()}

    side = {r: {"n": 0, "orig": 0, "mirr": 0, "same": 0, "pick_left": 0} for r in ("lower", "upper")}
    levels = {"lower_left": [0, 0], "lower_right": [0, 0], "upper_left": [0, 0], "upper_right": [0, 0]}
    flags = {"wheelchair": [0, 0], "prosthesis": [0, 0]}
    for r in records:
        v = clip.image(r.png)
        vm = clip.image(mirrored(r.png))
        for region in ("lower", "upper"):
            l, rr = getattr(r.attrs, f"{region}_left"), getattr(r.attrs, f"{region}_right")
            # side test only where exactly one side is amputated (the sentence then has a single right answer)
            if UNKNOWN in (l, rr) or (l == 0) == (rr == 0):
                continue
            truth = 0 if l != 0 else 1  # index 0 = left sentence, 1 = right sentence
            o, m = clip.choose(v, side_txt[region]), clip.choose(vm, side_txt[region])
            s = side[region]
            s["n"] += 1
            s["orig"] += int(o == truth)
            s["mirr"] += int(m == 1 - truth)  # mirrored picture: the amputated side is the other one
            s["same"] += int(o == m)
            s["pick_left"] += int(o == 0)
        for name, txt in (("lower", lower_txt), ("upper", upper_txt)):
            for side_name in ("left", "right"):
                field = f"{name}_{side_name}"
                truth = getattr(r.attrs, field)
                if truth == UNKNOWN:
                    continue
                # the level sentences do not name a side: the argmax is compared with the level of the worse limb
                other = getattr(r.attrs, f"{name}_{'right' if side_name == 'left' else 'left'}")
                worst = max(truth, other) if other != UNKNOWN else truth
                levels[field][1] += 1
                levels[field][0] += int(clip.choose(v, txt) == worst)
        if r.level == 2:
            for name in ("wheelchair", "prosthesis"):
                truth = getattr(r.attrs, name)
                if truth == UNKNOWN:
                    continue
                flags[name][1] += 1
                flags[name][0] += int(("yes", "no")[clip.choose(v, flag_txt[name])] == truth)

    out.append("### Esquerda e direita (pares de frases; só imagens com exatamente um lado amputado). Acaso esperado: 50%.")
    for region, s in side.items():
        n = s["n"]
        out.append(f"- {region}: {n} imagens. Acerto no original {pct(s['orig'], n)}; no espelhado {pct(s['mirr'], n)}; "
                   f"mesma resposta nos dois {s['same']}/{n}; escolheu a frase da ESQUERDA {s['pick_left']}/{n}.")
    out += ["", "### Nível do membro (4 ou 3 frases, sem lado; comparado com o pior dos dois membros da região)"]
    for field, (k, n) in levels.items():
        out.append(f"- {field}: {pct(k, n)}")
    if level == 2:
        out += ["", "### Cadeira de rodas e prótese (duas frases)"]
        for name, (k, n) in flags.items():
            out.append(f"- {name}: {pct(k, n)}")
    s = clip.seconds
    out += ["", f"Tempo por imagem codificada: mediana {np.median(s):.2f} s, média {np.mean(s):.2f} s ({len(s)} imagens, incluindo as espelhadas)."]
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--level", type=int, choices=(1, 2), default=1)
    args = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(run(args.level))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
