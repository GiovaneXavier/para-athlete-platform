"""Study mode (K2): fictitious cases, quiz and the answer with its trace.

Stateless: a case id is a recipe the server replays, nothing is stored, and the answer key leaves
the server only in POST /api/education/answer. Groups outside the study mode are refused (422 by
validation, 404 for a case id that names one).
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from ...education import cases, scope
from ...education import texts_pt as T
from ...education.options import options_for
from ...provenance_info import rules_version
from ...rules.catalog import load_catalog
from ..education_schemas import (
    SEED_MAX,
    AnswerIn,
    AnswerOut,
    CaseOut,
    Difficulty,
    DifficultyOut,
    FactOut,
    GroupId,
    OptionOut,
    PresentationOut,
    QuizDifficulty,
    QuizOut,
    ScopeGroupOut,
    ScopeOut,
    TraceStepOut,
)

router = APIRouter(prefix="/api/education")

REVIEW_NOTE = (
    "Todo caso e toda explicação são rascunho até a especialista rever. A tela mostra \"Rascunho\" enquanto for assim."
)
SeedParam = Annotated[int, Query(ge=0, le=SEED_MAX, description="Seed: same seed, same cases")]


def _options(group: str) -> list[OptionOut]:
    return [OptionOut(id=o.id, label=o.label) for o in options_for(group)]


def _case_out(case: cases.Case) -> CaseOut:
    """The case as the learner sees it: no class, verdict, trace or any field derived from the answer."""
    return CaseOut(
        case_id=case.case_id,
        group=case.group,
        difficulty=case.difficulty,
        review_status=case.review_status,
        notice=scope.NOTICE,
        presentation=PresentationOut(
            summary=case.presentation.summary,
            facts=[FactOut(label=f.label, value=f.value) for f in case.presentation.facts],
        ),
        options=_options(case.group),
    )


@router.get("/scope", response_model=ScopeOut)
def education_scope() -> ScopeOut:
    """The four groups of the study mode, the fixed notice and the rule book version."""
    return ScopeOut(
        notice=scope.NOTICE,
        review_status_note=REVIEW_NOTE,
        rules_version=rules_version().id,
        case_version=scope.CASE_VERSION,
        quiz_sizes=list(scope.QUIZ_SIZES),
        difficulties=[
            DifficultyOut(id=d, label=T.DIFFICULTY_LABELS[d], hint=T.DIFFICULTY_HINTS[d]) for d in scope.QUIZ_DIFFICULTIES
        ],
        groups=[
            ScopeGroupOut(
                id=g.id,
                label=T.GROUP_LABELS[g.id],
                summary=T.GROUP_SUMMARIES[g.id],
                classes=list(g.classes),
                warning=T.GROUP_WARNINGS[g.id],
                difficulties=list(scope.DIFFICULTIES),
                options=_options(g.id),
            )
            for g in scope.GROUPS
        ],
    )


@router.get("/case", response_model=CaseOut)
def education_case(
    group: GroupId,
    difficulty: Difficulty,
    seed: SeedParam,
    index: Annotated[int, Query(ge=0, le=10_000)] = 0,
) -> CaseOut:
    """One case, without the answer. Same parameters, same case."""
    try:
        return _case_out(cases.get_case(group, difficulty, seed, index))
    except KeyError as error:
        raise HTTPException(status_code=404, detail="case not found") from error


@router.get("/quiz", response_model=QuizOut)
def education_quiz(
    seed: SeedParam,
    size: Annotated[int, Query(description="5, 10 or 15 questions")] = scope.DEFAULT_QUIZ_SIZE,
    groups: Annotated[list[GroupId] | None, Query()] = None,
    difficulty: QuizDifficulty = "mixed",
) -> QuizOut:
    """A deterministic quiz (no repeated case), without the answers."""
    if size not in scope.QUIZ_SIZES:
        raise HTTPException(status_code=422, detail="size must be 5, 10 or 15")
    chosen = tuple(dict.fromkeys(groups)) if groups else scope.ALLOWED_GROUPS
    quiz = cases.build_quiz(seed, size, chosen, difficulty)
    return QuizOut(
        notice=scope.NOTICE,
        seed=seed,
        size=size,
        difficulty=difficulty,
        cases=[_case_out(case) for case in quiz],
    )


@router.post("/answer", response_model=AnswerOut)
def education_answer(payload: AnswerIn) -> AnswerOut:
    """Checks a choice on the server and only then returns the answer, the trace and its limits."""
    try:
        case = cases.case_from_id(payload.case_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="case not found") from error

    options = {o.id: o.label for o in options_for(case.group)}
    if payload.choice is not None and payload.choice not in options:
        raise HTTPException(status_code=422, detail="choice is not an option of this case")

    trace = cases.trace_of(case)
    answer = case.answer
    if payload.choice is None:
        outcome, title = "revealed", T.REVEALED_TITLE
    elif payload.choice == answer:
        outcome, title = "correct", T.CORRECT_TITLE
    else:
        outcome, title = "wrong", T.WRONG_TITLE

    class_name, codes = None, []
    if answer.startswith("class:"):
        spec = load_catalog().classes[int(answer.split(":")[1])]
        class_name, codes = spec.name_pt, list(spec.codes)

    return AnswerOut(
        case_id=case.case_id,
        outcome=outcome,
        title=title,
        correct=outcome == "correct",
        answer_id=answer,
        answer_label=options[answer],
        class_name_pt=class_name,
        class_codes=codes,
        steps=[
            TraceStepOut(
                criterion=s.criterion,
                reference=s.reference,
                value=s.value,
                result=s.result,
                result_label=T.RESULT_LABELS[s.result],
                explanation=s.explanation,
            )
            for s in trace.steps
        ],
        conclusion=trace.conclusion,
        references=[T.SOURCE_REFERENCE.format(page=page) for page in trace.source_pages],
        limits=list(trace.limits),
        review_status=case.review_status,
        notice=scope.NOTICE,
    )
