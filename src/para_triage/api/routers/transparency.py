"""GET /api/transparency: the committed K11 report plus what this server is running.

The report is web/public/transparency.json (written by para_triage.transparency.export). The API
never reads runs/: the numbers come from that committed file, and `live` only compares it with the
rule book and the checkpoint this process actually loaded.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from ...provenance_info import checkpoint_info, rules_version
from ..schemas import LiveOut, ServedModelOut, TransparencyOut, TransparencyReport

router = APIRouter()

DEFAULT_REPORT = Path(__file__).resolve().parents[4] / "web" / "public" / "transparency.json"


def load_transparency(report_path: Path, checkpoint: Path | None) -> TransparencyOut:
    """Validates the committed report and describes the live rule book and checkpoint."""
    report = TransparencyReport.model_validate_json(Path(report_path).read_text(encoding="utf-8"))
    rules = rules_version()
    info = checkpoint_info(checkpoint) if checkpoint is not None else None
    served = (
        ServedModelOut(
            file_name=info.file_name,
            sha256=info.sha256,
            size_bytes=info.size_bytes,
            known=info.known,
            name=info.name,
            status=info.status,
        )
        if info
        else None
    )
    matches = served.sha256 == report.model_card.sha256 if served and report.model_card else None
    live = LiveOut(
        rules_id=rules.id,
        rules_match_report=rules.id == report.rules.id,
        served_model=served,
        served_model_matches_card=matches,
    )
    return TransparencyOut(report=report, live=live)


@router.get("/api/transparency", response_model=TransparencyOut)
def transparency(request: Request) -> TransparencyOut:
    """Aggregated N1 results, rule book version and model card, with a check against what is served."""
    state = request.app.state
    if state.transparency is None:
        raise HTTPException(status_code=503, detail=f"transparency report unavailable: {state.transparency_error}")
    return state.transparency
