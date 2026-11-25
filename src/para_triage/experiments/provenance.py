"""What a run needs to record so that someone else can reproduce it."""
from __future__ import annotations

import datetime
import json
import platform
import subprocess
import sys
from pathlib import Path


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def provenance() -> dict:
    import numpy
    import pandas
    import sklearn
    import torch

    return {
        "commit": _git("rev-parse", "HEAD"),
        # The code that produced the numbers is what the commit hash must describe: files outside src/, tests/ and
        # pyproject.toml (papers, notes) may be edited while an experiment runs without changing its results.
        "code_tree_dirty": bool(_git("status", "--porcelain", "--", "src", "tests", "pyproject.toml")),
        "tree_dirty": bool(_git("status", "--porcelain")),
        "python": platform.python_version(),
        "numpy": numpy.__version__,
        "pandas": pandas.__version__,
        "scikit_learn": sklearn.__version__,
        "torch": torch.__version__,
        "command": " ".join([Path(sys.executable).name, *sys.argv]),
        "written_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
    }


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
