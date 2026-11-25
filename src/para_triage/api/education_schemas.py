"""Request and response models of the study-mode API (K2).

Kept apart from schemas.py. The case models carry no answer: the key is only in AnswerOut.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..education.scope import ALLOWED_GROUPS, MAX_SEED

# The refusal of every group outside the study mode lives in these Literals (422 for anything else).
GroupId = Literal["visual", "short_stature", "limb_standing", "limb_prosthesis"]
Difficulty = Literal["easy", "medium", "hard"]
QuizDifficulty = Literal["easy", "medium", "hard", "mixed"]
ReviewStatus = Literal["draft", "reviewed"]

assert set(GroupId.__args__) == set(ALLOWED_GROUPS), "GroupId must list exactly the groups of the study mode"


class OptionOut(BaseModel):
    id: str
    label: str


class FactOut(BaseModel):
    label: str
    value: str


class PresentationOut(BaseModel):
    summary: str
    facts: list[FactOut]


class CaseOut(BaseModel):
    case_id: str
    group: GroupId
    difficulty: Difficulty
    review_status: ReviewStatus
    notice: str
    presentation: PresentationOut
    options: list[OptionOut]


class ScopeGroupOut(BaseModel):
    id: GroupId
    label: str
    summary: str
    classes: list[int]
    warning: str | None
    difficulties: list[Difficulty]
    options: list[OptionOut]


class DifficultyOut(BaseModel):
    id: QuizDifficulty
    label: str
    hint: str


class ScopeOut(BaseModel):
    notice: str
    review_status_note: str
    rules_version: str
    case_version: str
    quiz_sizes: list[int]
    difficulties: list[DifficultyOut]
    groups: list[ScopeGroupOut]


class QuizOut(BaseModel):
    notice: str
    seed: int
    size: int
    difficulty: QuizDifficulty
    cases: list[CaseOut]


class AnswerIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(max_length=120)
    choice: str | None = Field(None, max_length=40, description="Option id, or null to see the answer")


class TraceStepOut(BaseModel):
    criterion: str
    reference: str
    value: str
    result: Literal["met", "not_met", "not_assessed"]
    result_label: str
    explanation: str


class AnswerOut(BaseModel):
    case_id: str
    outcome: Literal["correct", "wrong", "revealed"]
    title: str
    correct: bool
    answer_id: str
    answer_label: str
    class_name_pt: str | None
    class_codes: list[str]
    steps: list[TraceStepOut]
    conclusion: str
    references: list[str]
    limits: list[str]
    review_status: ReviewStatus
    notice: str


SEED_MAX = MAX_SEED
