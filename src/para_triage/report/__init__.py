"""LLM report generation over the rule engine and model output."""
from .client import LLMUnavailable, OllamaClient
from .context import ReportContext, build_context
from .generate import Report, generate_report
from .prompt import Issue, check_report, render_template

__all__ = [
    "Issue",
    "LLMUnavailable",
    "OllamaClient",
    "Report",
    "ReportContext",
    "build_context",
    "check_report",
    "generate_report",
    "render_template",
]
