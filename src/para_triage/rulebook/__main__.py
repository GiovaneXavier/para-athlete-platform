"""Commands of the rule book:

    python -m para_triage.rulebook test    [--group visual]
    python -m para_triage.rulebook regress [--group visual] [--seeds 5] [--per-label N] [--exhaustive]
    python -m para_triage.rulebook diff    [--group visual] [--a cpb-2024] [--b cpb-2024] [--set name=value ...]
    python -m para_triage.rulebook regress --engine [--exhaustive]    the whole engine (33 classes at once, mixed impairments)
    python -m para_triage.rulebook reasons                            the sentences of the engine against the codes of the books
    python -m para_triage.rulebook time                               microseconds per profile, current engine and shadow engine

`regress` compares the interpreter with the current engine (exit code 1 on any divergence). A bigger sample, outside the
CI: `python -m para_triage.rulebook regress --exhaustive` (20 seeds of 400 profiles per class, and, for a group with
`domains`, every combination of its discrete measures with every set of impairments).
"""
from __future__ import annotations

import argparse
import sys

import yaml

from .compare import (
    diff_variants,
    domain_cases,
    format_diff,
    format_engine_report,
    format_report,
    group_items,
    reasons_summary,
    reasons_table,
    regress,
    regress_engine,
    sample_cases,
    sweep_cases,
    timing,
)
from .engine import GROUPS
from .interpreter import DEFAULT_VARIANT, Rulebook


def _books(group: str) -> list[Rulebook]:
    return [Rulebook.load(g) for g in (GROUPS if group == "all" else (group,))]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m para_triage.rulebook", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("reasons")
    sub.add_parser("time")
    for name in ("test", "regress", "diff"):
        p = sub.add_parser(name)
        p.add_argument("--group", default="all", choices=("all", *GROUPS))
        if name != "test":
            p.add_argument("--seeds", type=int, default=5)
            p.add_argument("--per-label", type=int, default=None)
            p.add_argument("--exhaustive", action="store_true", help="20 seeds of 400 profiles per class and the whole product of the domains")
        if name == "regress":
            p.add_argument("--engine", action="store_true", help="the whole engine against the current one, not group by group")
        if name == "diff":
            p.add_argument("--a", default=DEFAULT_VARIANT)
            p.add_argument("--b", default=DEFAULT_VARIANT)
            p.add_argument("--set", dest="overrides", action="append", default=[], metavar="NAME=VALUE", help="override a parameter in B")
    args = parser.parse_args(argv)

    if args.command == "time":
        for name, (current, shadow) in timing().items():
            print(f"{name:16s} current engine {current:8.0f} us   shadow engine {shadow:8.0f} us   ({shadow / current:.1f}x)")
        return 0
    if args.command == "reasons":
        summary = reasons_summary(reasons_table(group_items()))
        print("\n".join(f"{key:32s} {value}" for key, value in summary.items()))
        return 0
    if args.command == "regress" and args.engine:
        report = regress_engine(group_items(args.exhaustive))
        print(format_engine_report(report))
        return int(not report.clean)

    status = 0
    for book in _books(args.group):
        if args.command == "test":
            failures = book.run_tests()
            print(f"{book.name}: {len(book.data.get('tests', []))} tests as data, {len(failures)} failed")
            for failure in failures:
                print("  ", failure)
            status |= bool(failures)
            continue
        seeds, per_label = (max(args.seeds, 20), args.per_label or 400) if args.exhaustive else (args.seeds, args.per_label)
        discrete = "domains" in book.data
        cases = sample_cases(book, range(seeds), per_label) + (domain_cases(book, args.exhaustive) if discrete else sweep_cases(book))
        if args.command == "regress":
            report = regress(book, cases)
            print(format_report(report))
            status |= not report.clean
        else:
            overrides = dict(item.split("=", 1) for item in args.overrides)
            parsed = {k: yaml.safe_load(v) for k, v in overrides.items()}
            print(format_diff(diff_variants(book, cases, args.a, args.b, overrides_b=parsed or None)))
    return status


if __name__ == "__main__":
    sys.exit(main())
