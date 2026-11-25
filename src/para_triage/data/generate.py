"""CLI: python -m para_triage.data.generate --n-per-label 300 --out data/processed/synthetic_v0.csv"""
from __future__ import annotations

import argparse
from pathlib import Path

from .generator import generate_dataset
from .noise import NoiseConfig
from .sampling import SAMPLERS


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n-per-label", type=int, default=300)
    parser.add_argument("--groups", nargs="*", choices=sorted(SAMPLERS), default=None)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--no-noise", action="store_true", help="exact measurements, nothing missing")
    parser.add_argument("--out", type=Path, default=Path("data/processed/synthetic_v0.csv"))
    args = parser.parse_args(argv)

    noise = NoiseConfig.none() if args.no_noise else NoiseConfig()
    df = generate_dataset(args.n_per_label, args.groups, args.seed, noise)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out, index=False)

    agree = (df.rule_label == df.label).mean()
    print(f"{len(df)} rows -> {args.out}")
    print(df.groupby(["group", "label"]).size().to_string())
    print(f"rules baseline agrees with the true label on {agree:.1%} of rows")


if __name__ == "__main__":
    main()
