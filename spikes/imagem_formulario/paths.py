"""Where the data and results live: OUTSIDE the repository."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(os.environ.get("IMAGEM_FORMULARIO_HOME", str(Path.home() / "imagem_formulario")))
DATA = ROOT / "data"
RUNS = ROOT / "runs"
FINAL_MARKER = ROOT / "FINAL_RUN_DONE.txt"  # written by the one run on the test set; its presence makes `final` refuse to run again


def ensure() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    RUNS.mkdir(parents=True, exist_ok=True)
