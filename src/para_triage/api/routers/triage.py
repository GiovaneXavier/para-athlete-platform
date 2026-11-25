"""POST /api/triage."""
from __future__ import annotations

from fastapi import APIRouter, Request

from ...report.prompt import render_template
from ..context import context_for
from ..schemas import OptionOut, TriageIn, TriageOut

router = APIRouter()


@router.post("/api/triage", response_model=TriageOut)
def triage(payload: TriageIn, request: Request) -> TriageOut:
    """Fast part: rules + MLP + the deterministic reference report."""
    app = request.app
    ctx = context_for(app, payload)
    return TriageOut(
        options=[
            OptionOut(
                class_id=o.class_id,
                codes=list(o.codes),
                name_pt=o.name_pt,
                probability=o.probability,
                rule_status=o.rule_status.value if o.rule_status else None,
                rule_reasons=list(o.rule_reasons),
                events=list(o.events),
                equipment=list(o.equipment),
            )
            for o in ctx.options
        ],
        p_none=ctx.p_none,
        p_ambiguous=ctx.p_ambiguous,
        rules_primary=ctx.rules_primary,
        rules_model_agree=ctx.rules_model_agree,
        flags=list(ctx.flags),
        review_notes=list(ctx.review_notes),
        missing=list(ctx.missing),
        facts=list(ctx.profile_facts),
        model_available=app.state.predictor is not None,
        reference_report=render_template(ctx),
    )
