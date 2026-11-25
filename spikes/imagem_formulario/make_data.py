"""Generates the image sets with the existing generators and writes them OUTSIDE the repository (`paths.DATA`).

    PYTHONPATH=src;spikes  python -m imagem_formulario.make_data [--workers 8] [--only level split]

Each image is reduced 2x2 by averaging (400x280 -> 200x140, uint8) to keep CPU training fast. The test set also keeps the original
PNG bytes (the classical baseline reads those). Nothing is written to the repository.
"""
from __future__ import annotations

import argparse
import pickle
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np

from para_triage.consistency import dataset, level2
from para_triage.consistency.png import decode_png
from para_triage.consistency.schema import Attrs

from . import paths, splits
from .labels import HEADS, IGNORE, encode, encode_attrs


def reduce2(pixels: np.ndarray) -> np.ndarray:
    h, w, c = pixels.shape
    return pixels.reshape(h // 2, 2, w // 2, 2, c).mean(axis=(1, 3)).round().astype(np.uint8)


def true_vector(level: int, true_levels: dict, wheelchair: str, prosthesis: str) -> list[int]:
    """The TRUE attributes as head indices (the real level of every limb, even where the picture hides it)."""
    attrs = Attrs(**true_levels, wheelchair=wheelchair, prosthesis=prosthesis)
    return encode_attrs(attrs, level if level == 1 else 2)


def render_item(args):
    level, split, item = args
    combo_index, band, index, held = item
    seed = splits.SEEDS[split]
    attrs4 = splits.combos()[combo_index]
    if level == 1:
        appearance = dataset.appearance_for(combo_index, index, seed)
        png = dataset.render(attrs4, appearance).png
        image_label = attrs4.restricted(("lower_left", "lower_right", "upper_left", "upper_right"))
        truth = {n: getattr(attrs4, n) for n in HEADS[:4]}
        t = true_vector(1, truth, "no", "no")
        detail = {}
    else:
        png, image_label, _vector, detail = level2.render_level2(attrs4, band, index, seed)
        truth = detail["true_levels"]
        t = true_vector(2, truth, "yes" if detail["chair"] else "no", "yes" if detail["prostheses"] else "no")
    y = encode_attrs(image_label, level)
    return reduce2(decode_png(png)), y, t, band, combo_index, held, png if split == "test" else b""


def build(level: int, split: str, workers: int) -> None:
    its = splits.items(level, split)
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=workers) as pool:
        rows = list(pool.map(render_item, [(level, split, it) for it in its], chunksize=20))
    x = np.stack([r[0] for r in rows])
    np.savez(paths.DATA / f"L{level}_{split}.npz", x=x, y=np.array([r[1] for r in rows], dtype=np.int8), t=np.array([r[2] for r in rows], dtype=np.int8),
             band=np.array([r[3] for r in rows], dtype=np.int8), combo=np.array([r[4] for r in rows], dtype=np.int16), held=np.array([r[5] for r in rows], dtype=bool))
    if split == "test":
        with open(paths.DATA / f"L{level}_test_png.pkl", "wb") as f:
            pickle.dump([r[6] for r in rows], f)
    print(f"level {level} {split}: {len(rows)} images, {x.nbytes / 1e6:.0f} MB, {time.time() - t0:.0f} s", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--only", nargs=2, metavar=("LEVEL", "SPLIT"))
    args = ap.parse_args()
    paths.ensure()
    todo = [(int(args.only[0]), args.only[1])] if args.only else [(lv, sp) for lv in (1, 2) for sp in ("dev", "test", "train")]
    for level, split in todo:
        build(level, split, args.workers)


if __name__ == "__main__":
    main()
