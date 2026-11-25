"""Read-only facts about a model checkpoint: its hash and, when we know it, protocol and metrics.

The checkpoint is never loaded here (it is a pickle; see models/predict.py), only hashed.
What we know about a checkpoint is bound to its hash through KNOWN_CHECKPOINTS, so a retrained
file with the same name is reported as unknown instead of inheriting someone else's numbers.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from .evidence import EVIDENCE_LEVEL, EVIDENCE_NOTICE

# sha256 of the checkpoint file -> what is known about it. Text only: no metric is typed here;
# metrics are read from the metrics.json that sits next to the checkpoint.
KNOWN_CHECKPOINTS: dict[str, dict] = {
    "1d9fef51fee578d86fcadcafe17ec612473d6eda104e8f7de0dbc534f9ab4148": {
        "name": "mlp_v1",
        "status": "preliminary",
        "protocol": (
            "Primeiro protocolo de treino: um único conjunto de perfis sintéticos para as 5 execuções, "
            "divisão 70/15/15 por linha e hiperparâmetros fixos (sem ajuste na validação). "
            "Anterior ao protocolo atual dos experimentos E1 e E7."
        ),
        "limits": (
            "Preliminar e ignorado pelo git: o arquivo existe só na máquina de quem o treinou.",
            "Treinado e avaliado só com dados sintéticos gerados pelas mesmas regras que o rotulam.",
            "Não vale como resultado atual dos experimentos; os números do E1 e do E7 são outros.",
        ),
    }
}


@dataclass(frozen=True)
class CheckpointInfo:
    file_name: str  # name only: never a local path
    sha256: str
    size_bytes: int
    known: bool  # True when the hash is in KNOWN_CHECKPOINTS
    name: str | None
    status: str  # "preliminary" or "unknown"
    protocol: str | None
    limits: tuple[str, ...]
    metrics: dict | None  # read from the metrics.json beside the checkpoint, known checkpoints only
    evidence_level: str = EVIDENCE_LEVEL
    notice: str = EVIDENCE_NOTICE


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stat(block: dict) -> dict:
    return {"mean": block["mean"], "std": block["std"]}


def _read_metrics(path: Path) -> dict | None:
    """Summary of a train.py metrics.json (aggregate over runs), or None when absent or unreadable."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        mlp = data["aggregate"]["overall"]["mlp"]
        return {
            "n_runs": len(data["runs"]),
            "mlp_agreement_with_rule_labels": _stat(mlp["accuracy"]),
            "mlp_macro_f1": _stat(mlp["macro_f1"]),
            "evidence_level": EVIDENCE_LEVEL,
            "notice": EVIDENCE_NOTICE,
        }
    except (OSError, ValueError, KeyError, TypeError):
        return None


def checkpoint_info(path: Path | str) -> CheckpointInfo | None:
    """Facts about the checkpoint at `path`, or None when there is no such file."""
    path = Path(path)
    if not path.is_file():
        return None
    sha256 = file_sha256(path)
    entry = KNOWN_CHECKPOINTS.get(sha256)
    return CheckpointInfo(
        file_name=path.name,
        sha256=sha256,
        size_bytes=path.stat().st_size,
        known=entry is not None,
        name=entry["name"] if entry else None,
        status=entry["status"] if entry else "unknown",
        protocol=entry["protocol"] if entry else None,
        limits=tuple(entry["limits"]) if entry else (),
        metrics=_read_metrics(path.with_name("metrics.json")) if entry else None,
    )
