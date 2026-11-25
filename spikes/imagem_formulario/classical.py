"""The classical baseline (image-and-report check) read on the TEST pictures. It reads pixels only and sees no label; it is not tuned, so computing it
does not touch the test labels. Results are cached in `paths.RUNS` (about 1 s per image, run in parallel).

    PYTHONPATH=src;spikes  python -m imagem_formulario.classical [--workers 8]
"""
from __future__ import annotations

import argparse
import json
import pickle
import time
from concurrent.futures import ProcessPoolExecutor

from para_triage.consistency.baselines import classical_extract

from . import paths


def _read(png: bytes) -> dict:
    return {k: v for k, v in classical_extract(png).as_dict().items() if k.startswith(("lower", "upper"))}


def read_all(level: int, workers: int = 8) -> list[dict]:
    cache = paths.RUNS / f"classical_L{level}_test.json"
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    with open(paths.DATA / f"L{level}_test_png.pkl", "rb") as f:
        pngs = pickle.load(f)
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=workers) as pool:
        out = list(pool.map(_read, pngs, chunksize=10))
    print(f"classical level {level}: {len(out)} pictures in {time.time() - t0:.0f} s", flush=True)
    cache.write_text(json.dumps(out), encoding="utf-8")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    paths.ensure()
    for lv in (1, 2):
        read_all(lv, a.workers)
