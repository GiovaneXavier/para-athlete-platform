"""GET /api/health."""
from __future__ import annotations

from fastapi import APIRouter, Request

from ..schemas import HealthOut

router = APIRouter()


@router.get("/api/health", response_model=HealthOut)
def health(request: Request) -> HealthOut:
    state = request.app.state
    return HealthOut(
        status="ok",
        model_loaded=state.predictor is not None,
        ollama_available=state.llm.is_available(),
        ollama_model=state.llm.model,
    )
