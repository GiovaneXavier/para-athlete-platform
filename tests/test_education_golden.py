"""Golden test: the first cases of every group and level (seed 0) must not change by accident.

It fails when the sampler (data/), the rules, or the case recipe changes. If the change is
intentional (agreed with the course line, and old case ids may now show other cases: consider
bumping CASE_VERSION in education/scope.py), regenerate the file and review the diff:

    python tests/fixtures/make_education_golden.py
    git diff tests/fixtures/education_golden.json
"""
import json
import sys
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"
sys.path.insert(0, str(FIXTURES))

from education_golden import build  # noqa: E402

GOLDEN = json.loads((FIXTURES / "education_golden.json").read_text(encoding="utf-8"))
HOW_TO_UPDATE = (
    "The study-mode cases no longer match tests/fixtures/education_golden.json. If the change is intentional "
    "(generator or rules changed with the course line's agreement), run "
    "`python tests/fixtures/make_education_golden.py`, review the diff and consider bumping CASE_VERSION."
)


def test_rules_and_case_version_match_the_golden_file():
    current = build()
    assert current["case_version"] == GOLDEN["case_version"], HOW_TO_UPDATE
    assert current["rules_id"] == GOLDEN["rules_id"], HOW_TO_UPDATE


def test_first_cases_of_every_group_and_level_match_the_golden_hashes():
    current = build()
    assert current["cases"].keys() == GOLDEN["cases"].keys()
    changed = [key for key in GOLDEN["cases"] if current["cases"][key] != GOLDEN["cases"][key]]
    assert not changed, f"{changed}: {HOW_TO_UPDATE}"
