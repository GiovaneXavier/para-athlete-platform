"""HTTP API over the rule engine, the MLP and the report generator.

    uvicorn para_triage.api.app:app --port 8000

Environment: PARA_CHECKPOINT (default <repo>/runs/mlp_v1/model.pt), PARA_TRANSPARENCY_JSON (default
<repo>/web/public/transparency.json), OLLAMA_HOST, OLLAMA_MODEL.

The routes live in `routers/` (health, triage, report, transparency, education); this module only builds the app.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..models.predict import Predictor
from ..report import OllamaClient
from ..rules import RuleEngine
from .routers import education, health, report, transparency, triage
from .routers.report import JobStore
from .routers.transparency import DEFAULT_REPORT, load_transparency

# Relative to the repository root, so the server works from any directory.
DEFAULT_CHECKPOINT = Path(__file__).resolve().parents[3] / "runs" / "mlp_v1" / "model.pt"


def create_app(checkpoint: Path | None = None, llm: OllamaClient | None = None) -> FastAPI:
    checkpoint = checkpoint or Path(os.environ.get("PARA_CHECKPOINT", DEFAULT_CHECKPOINT))
    default_llm = llm or OllamaClient(
        model=os.environ.get("OLLAMA_MODEL", "qwen2.5:7b"),
        host=os.environ.get("OLLAMA_HOST", "http://localhost:11434"),
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.engine = RuleEngine()
        app.state.predictor = Predictor.load(checkpoint) if checkpoint.exists() else None
        try:
            report_path = Path(os.environ.get("PARA_TRANSPARENCY_JSON", DEFAULT_REPORT))
            app.state.transparency = load_transparency(report_path, checkpoint if checkpoint.exists() else None)
            app.state.transparency_error = None
        except (OSError, ValueError) as error:  # the report is optional: triage keeps working without it
            app.state.transparency, app.state.transparency_error = None, f"{type(error).__name__}: {error}"
        yield

    app = FastAPI(title="para-athletics-triage", version="0.1.0", lifespan=lifespan)
    app.state.llm = default_llm
    app.state.jobs = JobStore()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(triage.router)
    app.include_router(report.router)
    app.include_router(transparency.router)
    app.include_router(education.router)
    return app


app = create_app()
