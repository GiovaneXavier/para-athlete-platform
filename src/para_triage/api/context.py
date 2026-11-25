"""Shared by the triage and report routers: from a request payload to a ReportContext."""
from __future__ import annotations

from fastapi import FastAPI

from ..report import build_context
from ..report.context import ReportContext
from .schemas import TriageIn


def context_for(app: FastAPI, payload: TriageIn) -> ReportContext:
    profile = payload.profile.to_profile()
    predictor = app.state.predictor
    probabilities = classes = None
    if predictor is not None:
        probabilities, classes = predictor.predict_proba([profile])[0], predictor.classes
    return build_context(profile, app.state.engine, probabilities, classes, payload.top_k)
