"""Study mode (K2) on the web side: fixed notice, draft mark, scope, no persistence, wording."""
import re
from pathlib import Path

import pytest

from para_triage.education import scope

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web" / "src"
SOURCES = [
    *sorted((WEB / "app" / "educacao").glob("**/*.tsx")),
    *sorted((WEB / "components" / "education").glob("*.tsx")),
    WEB / "lib" / "education-api.ts",
]
PAGES = sorted((WEB / "app" / "educacao").glob("**/page.tsx"))


def read(path):
    return path.read_text(encoding="utf-8")


def test_the_web_notice_is_the_one_of_the_api():
    match = re.search(r'STUDY_NOTICE =\s*"([^"]+)"', read(WEB / "lib" / "education-api.ts"))
    assert match and match.group(1) == scope.NOTICE


def test_there_are_three_study_pages_and_each_one_shows_the_fixed_notice():
    assert [p.parent.name for p in PAGES] == ["educacao", "praticar", "quiz"]
    for page in PAGES:
        assert "StudyPage" in read(page), page  # StudyPage renders StudyNotice
    parts = read(WEB / "components" / "education" / "study-parts.tsx")
    assert "{STUDY_NOTICE}" in parts and "StudyNotice />" in parts
    assert "rascunho até a especialista rever" in parts


def test_every_case_shows_the_draft_mark():
    question = read(WEB / "components" / "education" / "case-question.tsx")
    assert question.count("<DraftBadge") >= 2  # on the case and on the result
    assert 'status === "reviewed" ? "Revisado" : "Rascunho"' in read(WEB / "components" / "education" / "study-parts.tsx")


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: p.name)
def test_no_group_or_class_outside_the_scope_in_the_web_code(path):
    text = read(path)
    for group in scope.EXCLUDED_GROUPS:
        assert group not in text, (path.name, group)
    assert not re.search(r"class:(20|3[1-8]|5[1-7]|7[12])\b", text)
    assert not re.search(r"[Cc]lasse (20|3[1-8]|5[1-7]|7[12])\b", text)


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: p.name)
def test_nothing_is_persisted_in_the_browser(path):
    text = read(path)
    for forbidden in ("localStorage", "sessionStorage", "indexedDB", "document.cookie", "navigator.sendBeacon"):
        assert forbidden not in text, (path.name, forbidden)


def test_the_only_write_request_is_the_answer_check():
    api = read(WEB / "lib" / "education-api.ts")
    assert api.count("postJson<") == 1 and '"/api/education/answer"' in api
    for path in SOURCES:
        text = read(path)
        assert 'method: "POST"' not in text and "method: 'POST'" not in text


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: p.name)
def test_the_quiz_never_uses_the_forbidden_word_for_user_performance(path):
    lowered = read(path).lower()
    assert "acurácia" not in lowered and "accuracy" not in lowered


def test_the_result_is_announced_and_the_group_is_a_fieldset():
    question = read(WEB / "components" / "education" / "case-question.tsx")
    assert 'aria-live="polite"' in question and 'role="status"' in question
    assert "<fieldset" in question and "<legend" in question
    assert 'type="radio"' in question and "focus-visible" in question
