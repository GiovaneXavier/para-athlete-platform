"""Report generation with a faithfulness guard and a deterministic fallback."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from .client import LLMUnavailable
from .context import ReportContext
from .prompt import SYSTEM_PROMPT, Issue, check_report, render_template, user_prompt


class ChatModel(Protocol):
    def chat(self, system: str, user: str) -> str: ...


@dataclass(frozen=True)
class Report:
    text: str
    source: str  # "llm" or "template"
    issues: list[Issue] = field(default_factory=list)  # why the LLM text was not used
    attempts: int = 0
    rejected: str | None = None  # last LLM draft that failed the checks


def generate_report(ctx: ReportContext, llm: ChatModel | None = None, max_attempts: int = 2) -> Report:
    """LLM report when it passes the checks; otherwise the deterministic one.

    A draft that cites an unknown class or probability, drops a section or the
    disclaimer is sent back once with the problems listed. If the second draft
    fails too, the template (faithful by construction) is returned.
    """
    reference = render_template(ctx)
    if llm is None:
        return Report(reference, "template")

    issues: list[Issue] = []
    draft = None
    for attempt in range(1, max_attempts + 1):
        try:
            draft = llm.chat(SYSTEM_PROMPT, user_prompt(ctx, issues or None))
        except LLMUnavailable as exc:
            return Report(reference, "template", [Issue("llm_unavailable", str(exc))], attempt)
        issues = check_report(draft, ctx)
        if not issues:
            return Report(draft, "llm", [], attempt)
    return Report(reference, "template", issues, max_attempts, rejected=draft)
