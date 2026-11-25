"""The visual field limits are diameters (CPB booklet); other sources use the radius, which is half.

Wherever a field value or limit in degrees is shown (study mode, guide), the text says "de diâmetro".
"""
import json
import re
from pathlib import Path

from para_triage.education import cases
from para_triage.education import texts_pt as k2_texts
from para_triage.education.trace import build_trace
from para_triage.rules import Impairment, Posture, Profile

ROOT = Path(__file__).resolve().parents[1]
GUIDE = json.loads((ROOT / "web" / "src" / "content" / "guide.json").read_text(encoding="utf-8"))
BARE_DEGREES = re.compile(r"graus(?! de diâmetro)")


def strings(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for value in node.values():
            yield from strings(value)
    elif isinstance(node, list):
        for value in node:
            yield from strings(value)


def test_the_study_mode_says_diameter_for_the_field_value_and_limits():
    profile = Profile(
        impairments=frozenset({Impairment.VISUAL}), posture=Posture.STANDING, logmar_best_eye=0.2, visual_field_deg=35.0
    )
    trace = build_trace("visual", profile)
    field_steps = [s for s in trace.steps if s.criterion.startswith("Campo visual")]
    assert field_steps and all(s.reference.endswith("graus de diâmetro") and s.value.endswith("graus de diâmetro") for s in field_steps)
    for group in ("visual",):
        for level in ("easy", "medium", "hard"):
            for index in range(8):
                case = cases.get_case(group, level, 0, index)
                for fact in case.presentation.facts:
                    assert not BARE_DEGREES.search(fact.value), fact


def test_the_study_mode_limits_text_explains_the_radius():
    text = " ".join(k2_texts.LIMITS["visual"])
    assert "diâmetro" in text and "raio" in text and "metade" in text


def test_no_field_value_in_the_guide_is_in_bare_degrees():
    offenders = [text[:90] for text in strings(GUIDE) if BARE_DEGREES.search(text)]
    assert not offenders, offenders


def test_the_guide_explains_diameter_and_radius_in_the_glossary_and_on_the_visual_pages():
    glossary = next(item for item in GUIDE["glossary"] if item["id"] == "campo-visual")
    text = "".join(segment["t"] for segment in glossary["definition"])
    assert "diâmetro" in text and "raio" in text and "metade" in text
    for page in GUIDE["pages"]:
        if page.get("group") == "visual" and page["kind"] in ("group", "class"):
            page_text = " ".join(strings(page["sections"]))
            assert "raio" in page_text and "diâmetro" in page_text, page["path"]


def test_the_schema_comment_says_diameter_and_nothing_else_changed_in_the_field():
    line = next(
        l for l in (ROOT / "src" / "para_triage" / "rules" / "schema.py").read_text(encoding="utf-8").splitlines() if "visual_field_deg" in l
    )
    assert line.strip() == "visual_field_deg: float | None = None  # diameter, in degrees, as in the CPB booklet"
