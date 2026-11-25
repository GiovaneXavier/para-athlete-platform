"""The development checkpoint: the trained network on the development set only (never the test set).

    PYTHONPATH=src;spikes  python -m k35.dev --name run1
"""
from __future__ import annotations

import argparse
import sys

from . import evaluate


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="run1")
    args = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(evaluate.run_dev_report(args.name))


if __name__ == "__main__":
    main()
