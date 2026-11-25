"""CLI: python -m para_triage.report.cli examples/prosthesis_below_knee.json"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ..data import record_to_profile
from ..models.predict import Predictor
from ..rules import RuleEngine
from .client import OllamaClient
from .context import build_context
from .generate import generate_report
from .prompt import render_facts


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", type=Path, help="JSON with the profile fields")
    parser.add_argument("--checkpoint", type=Path, default=Path("runs/mlp_v1/model.pt"))
    parser.add_argument("--model", default="qwen2.5:7b", help="Ollama model")
    parser.add_argument("--no-llm", action="store_true", help="deterministic report only")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--show-facts", action="store_true", help="print what the LLM is given")
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")

    profile = record_to_profile(json.loads(args.profile.read_text(encoding="utf-8")))
    probabilities = classes = None
    if args.checkpoint.exists():
        predictor = Predictor.load(args.checkpoint)
        probabilities, classes = predictor.predict_proba([profile])[0], predictor.classes
    else:
        print(f"{args.checkpoint} not found: using the rules only, without probabilities", file=sys.stderr)

    ctx = build_context(profile, RuleEngine(), probabilities, classes, args.top_k)
    if args.show_facts:
        print(render_facts(ctx), end="\n\n---\n\n")

    llm = None if args.no_llm else OllamaClient(model=args.model)
    report = generate_report(ctx, llm)
    print(report.text)
    print(f"\n[source: {report.source}; attempts: {report.attempts}]", file=sys.stderr)
    for issue in report.issues:
        print(f"[{issue.kind}] {issue.detail}", file=sys.stderr)


if __name__ == "__main__":
    main()
