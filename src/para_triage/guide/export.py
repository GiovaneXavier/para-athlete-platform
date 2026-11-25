"""Writes the guide content to web/src/content/guide.json (committed; the web only renders it).

    python -m para_triage.guide.export [--out web/src/content/guide.json] [--date YYYY-MM-DD]

The date is the day of the generation; tests ignore it, so regenerating without a content change only
moves that field.
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from .build import build_content

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUT = REPO_ROOT / "web" / "src" / "content" / "guide.json"
REVIEW_FILE = Path(__file__).with_name("review_status.json")


def load_review() -> dict:
    try:
        return json.loads(REVIEW_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"texts_reviewed": False, "reviewed_pages": []}


def build(generated_on: str | None = None) -> dict:
    return build_content(generated_on or date.today().isoformat(), load_review())


def dumps(content: dict) -> str:
    return json.dumps(content, indent=1, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--date", default=None, help="generation date (default: today)")
    args = parser.parse_args(argv)
    text = dumps(build(args.date))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8", newline="\n")
    print(f"gravado {args.out} ({len(text.encode('utf-8'))} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
