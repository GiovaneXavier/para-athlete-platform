"""Contract with the core (rules): fails if the rule logic changes.

The expected verdicts in fixtures/core_contract.json were generated once from the rule engine
(fixtures/make_core_contract.py). The core belongs to the course line; this repository only reads it.
If a change is INTENTIONAL, regenerate the file and review the diff:

    python tests/fixtures/make_core_contract.py
    git diff tests/fixtures/core_contract.json
"""
import json
import sys
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
sys.path.insert(0, str(FIXTURES))

from core_contract_profiles import PROFILES, build_profile  # noqa: E402

from para_triage.rules import RuleEngine, Status  # noqa: E402

CONTRACT = json.loads((FIXTURES / "core_contract.json").read_text(encoding="utf-8"))
HOW_TO_UPDATE = (
    "The rule engine no longer matches tests/fixtures/core_contract.json. If the change is intentional "
    "(agreed with the course line), run `python tests/fixtures/make_core_contract.py` and review the diff."
)
REQUIRED_GROUPS = {
    "visual",
    "intellectual",
    "short_stature",
    "limb_standing",
    "limb_prosthesis",
    "neuro",
    "frame_runner",
    "wheelchair",
}

engine = RuleEngine()


def test_contract_covers_every_group_and_matches_the_profile_list():
    assert {c["group"] for c in CONTRACT["cases"]} >= REQUIRED_GROUPS
    assert [(c["name"], c["group"], c["profile"]) for c in CONTRACT["cases"]] == PROFILES


@pytest.mark.parametrize("case", CONTRACT["cases"], ids=lambda c: c["name"])
def test_engine_matches_the_contract(case):
    result = engine.evaluate(build_profile(case["profile"]))
    statuses = {str(cid): v.status.value for cid, v in result.verdicts.items() if v.status is not Status.NOT_APPLICABLE}
    assert result.primary_class == case["primary_class"], HOW_TO_UPDATE
    assert result.meets == case["meets"], HOW_TO_UPDATE
    assert statuses == case["statuses"], HOW_TO_UPDATE
