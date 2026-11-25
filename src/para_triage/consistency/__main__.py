"""`python -m para_triage.consistency level1 [--every N]`: runs level 1 end to end with the readers that need no
model (the classical image reader, the rule-based report reader, and the chance baseline) and prints the tables.

Nothing is written to disk and nothing is downloaded. With `--every 1` it renders the 432 images and takes a few minutes.
"""
from __future__ import annotations

import argparse
import sys

from . import errors, fakes, metrics, pipeline
from .baselines import ConstantExtractor, classical_extract, majority_attrs
from .dataset import DEFAULT_SEED, VARIATIONS, level1_records
from .reports import read_report
from .schema import level1_combinations


def run_level1(every: int = 1, seed: int = DEFAULT_SEED, draws: int = 1000) -> str:
    combos = level1_combinations()[::every]
    records = list(level1_records(seed=seed, combos=combos))
    pairs = errors.build_pairs([(r.image_id, r.attrs) for r in records], seed)
    images = pipeline.index_images(records)
    runs = {
        "linha de base clássica (imagem) e regras (laudo)": (classical_extract, read_report),
        "chute (valor mais comum de cada atributo)": None,
        "extratores perfeitos (confere o próprio pipeline)": (fakes.oracle_image_extractor(records), fakes.oracle_report_extractor(pairs)),
    }
    guess = ConstantExtractor(majority_attrs(r.attrs for r in records))
    runs["chute (valor mais comum de cada atributo)"] = (guess, guess)
    out = [f"Nível 1: {len(records)} imagens ({len(combos)} combinações x {VARIATIONS} variações), semente {seed}.", ""]
    for name, (image_extractor, report_extractor) in runs.items():
        outcomes = pipeline.evaluate(pairs, images, image_extractor, report_extractor)
        out += [f"## {name}", "", metrics.format_summary(metrics.summarize(outcomes, pairs, draws=draws))]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m para_triage.consistency")
    sub = parser.add_subparsers(dest="command", required=True)
    level1 = sub.add_parser("level1", help="run level 1 with the baselines that need no model")
    level1.add_argument("--every", type=int, default=1, help="use every N-th combination of the 144 (default: all)")
    level1.add_argument("--seed", type=int, default=DEFAULT_SEED)
    level1.add_argument("--draws", type=int, default=1000, help="bootstrap draws")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(run_level1(args.every, args.seed, args.draws))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
