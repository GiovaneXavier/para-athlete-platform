"""Regenerates tests/fixtures/education_golden.json. Read the docstring of education_golden.py first."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from education_golden import build  # noqa: E402

OUT = Path(__file__).with_name("education_golden.json")

if __name__ == "__main__":
    OUT.write_text(json.dumps(build(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {OUT}")
