"""Guards of the transparency panel (K11): the committed JSON, the wording and the evidence level.

- The committed web/public/transparency.json must match the current rule book (else: regenerate).
- It carries level N1 everywhere and no "accuracy" / "acurácia" label, local path or e-mail.
- Any file of the panel (page, components, docs) that says "acurácia" or "accuracy" must have N1 next to it.
"""
import json
import re
from pathlib import Path

import pytest

from para_triage.provenance_info import rules_version

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "web" / "public" / "transparency.json"
PANEL_FILES = [
    *sorted((ROOT / "web" / "src" / "app" / "transparencia").glob("**/*.ts*")),
    *sorted((ROOT / "web" / "src" / "components" / "transparency").glob("**/*.ts*")),
    ROOT / "docs" / "transparencia.md",
    ROOT / "src" / "para_triage" / "transparency" / "README.md",
]
FORBIDDEN = re.compile(r"acur[aá]cia|accuracy", re.IGNORECASE)
LEVEL = re.compile(r"\bN1\b")
WINDOW = 200  # characters on each side in which N1 must appear

REGENERATE = (
    "web/public/transparency.json is out of date. Regenerate it with "
    "`python -m para_triage.transparency.export --runs <path to runs/>` (see docs/transparencia.md)."
)


def accuracy_without_level(text: str) -> list[str]:
    """Snippets where the forbidden word has no N1 within WINDOW characters."""
    found = []
    for match in FORBIDDEN.finditer(text):
        around = text[max(0, match.start() - WINDOW) : match.end() + WINDOW]
        if not LEVEL.search(around):
            found.append(around.strip().replace("\n", " ")[:80])
    return found


# --- the guard itself ------------------------------------------------------------------------------------


def test_the_guard_flags_accuracy_without_the_level_and_accepts_it_with_the_level():
    assert accuracy_without_level("A acurácia do modelo é alta.")
    assert accuracy_without_level("the accuracy is 90%")
    assert not accuracy_without_level("Nível N1: não chamamos de acurácia a concordância com as regras.")
    assert not accuracy_without_level("Sem a palavra proibida, nada a verificar.")
    far = "acurácia" + " " * (WINDOW + 50) + "N1"
    assert accuracy_without_level(far)


@pytest.mark.parametrize("path", PANEL_FILES, ids=lambda p: p.name)
def test_panel_files_never_say_accuracy_without_the_level(path):
    if not path.exists():
        pytest.skip(f"{path.name} not written yet")
    assert accuracy_without_level(path.read_text(encoding="utf-8")) == []


# --- the committed report --------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def committed():
    text = REPORT.read_text(encoding="utf-8")
    return text, json.loads(text)


def test_the_committed_report_matches_the_current_rule_book(committed):
    _, report = committed
    assert report["rules"]["id"] == rules_version().id, REGENERATE


def test_the_changelog_has_an_entry_for_the_current_rule_book(committed):
    _, report = committed
    ids = [entry["rules_id"] for entry in report["changelog"]]
    assert rules_version().id in ids, "add an entry for the new rule book to transparency/rules_changelog.json"


def test_every_experiment_is_marked_n1_and_nothing_is_called_accuracy(committed):
    text, report = committed
    assert report["evidence_level"] == "N1" and "não validade clínica" in report["evidence_notice"]
    assert report["usage_notice"]
    for name, experiment in report["experiments"].items():
        assert experiment["evidence_level"] == "N1", name
    assert not FORBIDDEN.search(text)


def test_the_committed_report_has_no_personal_data_or_local_path(committed):
    text, _ = committed
    assert "@" not in text
    assert not re.search(r"[A-Za-z]:\\\\|/Users/|/home/|\\\\Users", text)
    assert "giova" not in text.lower()


def test_the_committed_report_is_lf_and_compact(committed):
    text, _ = committed
    assert "\r" not in text and len(text.encode("utf-8")) < 200_000


def test_the_committed_report_only_holds_aggregates(committed):
    _, report = committed
    forbidden_keys = {"profiles", "vignette", "vignettes", "labels", "answer_key", "gabarito", "rows"}

    def walk(node):
        if isinstance(node, dict):
            assert not forbidden_keys & set(node), forbidden_keys & set(node)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(report)


def test_the_committed_report_validates_against_the_api_model(committed):
    pytest.importorskip("pydantic")
    from para_triage.api.schemas import TransparencyReport

    text, _ = committed
    TransparencyReport.model_validate_json(text)
