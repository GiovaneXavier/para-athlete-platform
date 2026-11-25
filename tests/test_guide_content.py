"""Class guide (K18): scope, freshness, claims against the engine, prose without numbers, tone, links."""
import json
import re
from pathlib import Path

import pytest

from para_triage.education import cases as k2_cases
from para_triage.education import scope as k2_scope
from para_triage.guide import scope, texts_pt
from para_triage.guide.build import TERM, build_content, slug_key
from para_triage.guide.export import REPO_ROOT, build, dumps
from para_triage.provenance_info import rules_version
from para_triage.rules import Impairment, Posture, Profile, Sex

GUIDE_JSON = REPO_ROOT / "web" / "src" / "content" / "guide.json"
REGENERATE = (
    "web/src/content/guide.json is out of date. Regenerate it with `python -m para_triage.guide.export`, "
    "review the diff and commit."
)


@pytest.fixture(scope="module")
def committed():
    return json.loads(GUIDE_JSON.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def fresh():
    return build("2000-01-01")


def strings(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for value in node.values():
            yield from strings(value)
    elif isinstance(node, (list, tuple)):
        for value in node:
            yield from strings(value)


def walk(node):
    yield node
    if isinstance(node, dict):
        for value in node.values():
            yield from walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from walk(value)


# --- scope -----------------------------------------------------------------------------------------------


def test_the_guide_has_exactly_the_pages_of_the_four_groups(committed):
    expected = {scope.HUB_PATH, scope.GLOSSARY_PATH}
    for group in k2_scope.ALLOWED_GROUPS:
        expected.add(scope.group_path(group))
        expected |= {scope.class_path(group, cid) for cid in scope.class_ids(group)}
    assert {p["path"] for p in committed["pages"]} == expected and len(committed["pages"]) == 21
    assert sum(1 for p in committed["pages"] if p["kind"] == "class") == 15


def test_the_scope_is_the_one_of_the_study_mode():
    assert scope.GROUPS == k2_scope.ALLOWED_GROUPS
    assert set(scope.GROUP_SLUGS) == set(k2_scope.ALLOWED_GROUPS)
    assert not set(scope.GROUP_SLUGS) & set(k2_scope.EXCLUDED_GROUPS)


def test_nothing_outside_the_scope_is_in_the_content(committed):
    text = "\n".join(strings(committed))
    for group in k2_scope.EXCLUDED_GROUPS:
        assert group not in text
    assert not re.search(r"[Cc]lasse (20|3[1-8]|5[1-7]|7[12])\b", text)
    assert not re.search(r"class:(20|3[1-8]|5[1-7]|7[12])\b", text)


def test_every_page_carries_the_draft_mark_until_the_specialist_reviews_it(committed):
    assert committed["notice"] == scope.NOTICE
    assert {p["review_status"] for p in committed["pages"]} == {"draft"}
    reviewed = build_content("2000-01-01", {"texts_reviewed": True, "reviewed_pages": [scope.HUB_PATH]})
    status = {p["path"]: p["review_status"] for p in reviewed["pages"]}
    assert status[scope.HUB_PATH] == "reviewed" and status[scope.GLOSSARY_PATH] == "draft"
    only_pages = build_content("2000-01-01", {"texts_reviewed": False, "reviewed_pages": [scope.HUB_PATH]})
    assert {p["review_status"] for p in only_pages["pages"]} == {"draft"}


# --- freshness -------------------------------------------------------------------------------------------------


def test_the_committed_content_matches_the_current_rule_book(committed):
    assert committed["rules_id"] == rules_version().id, REGENERATE


def test_the_committed_content_is_what_the_build_produces_today(committed, fresh):
    def without_date(content):
        return {key: value for key, value in content.items() if key != "generated_on"}

    assert without_date(json.loads(dumps(fresh))) == without_date(committed), REGENERATE


def test_the_committed_file_is_lf_and_has_a_date(committed):
    assert "\r" not in GUIDE_JSON.read_text(encoding="utf-8")
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", committed["generated_on"])


# --- claims: what the pages imply, run through the engine ------------------------------------------------------


def profile_of(claim) -> Profile:
    fields = dict(claim["fields"])
    group = claim["group"]
    if group == "visual":
        return Profile(impairments=frozenset({Impairment.VISUAL}), posture=Posture.STANDING, **fields)
    if group == "short_stature":
        fields["sex"] = Sex(fields["sex"])
        return Profile(impairments=frozenset({Impairment.SHORT_STATURE}), posture=Posture.STANDING, **fields)
    posture = Posture.STANDING if group == "limb_standing" else Posture.PROSTHESIS
    return Profile(impairments=frozenset({Impairment.LIMB_DEFICIENCY}), posture=posture, **fields)


def test_every_claim_of_every_page_agrees_with_the_rule_engine(committed):
    claims = committed["claims"]
    assert len(claims) > 200 and len({c["id"] for c in claims}) == len(claims)
    wrong = [
        (c["id"], c["group"], c["note"], c["expected"], k2_cases.engine_answer(c["group"], profile_of(c)))
        for c in claims
        if k2_cases.engine_answer(c["group"], profile_of(c)) != c["expected"]
    ]
    assert not wrong, f"the guide says something the engine does not: {wrong[:3]}. {REGENERATE}"


def test_claims_cover_every_class_and_the_gap_of_the_visual_scale(committed):
    expected = {c["expected"] for c in committed["claims"]}
    for group in scope.GROUPS:
        for class_id in scope.class_ids(group):
            assert f"class:{class_id}" in expected, class_id
    assert {"none", "specialist"} <= expected


def test_the_patterns_listed_for_amputation_classes_are_the_ones_of_the_engine(committed):
    # pattern -> class pages: every pattern sentence of a class page must be answered by that class in the engine
    claims = [c for c in committed["claims"] if c["group"].startswith("limb")]
    for page in committed["pages"]:
        if page["kind"] == "class" and page["group"].startswith("limb"):
            answered = {c["expected"] for c in claims if c["group"] == page["group"]}
            assert f"class:{page['class_id']}" in answered


# --- prose without numbers, tone, terms --------------------------------------------------------------------------


def module_strings():
    for name in dir(texts_pt):
        if name.startswith("_") or not name.isupper():
            continue
        value = getattr(texts_pt, name)
        if name == "TONE_AVOID":
            continue
        yield from ((name, s) for s in strings(value if not isinstance(value, dict) else list(value.values())))


def test_the_prose_has_no_digits_so_every_number_on_a_page_is_generated():
    offenders = []
    for name, text in module_strings():
        cleaned = re.sub(r"\$\{[a-z0-9_]+\}", "", text)  # placeholders may name a value (c11, logmar_gt_11)
        cleaned = TERM.sub(lambda m: m.group(2), cleaned)
        if re.search(r"\d", cleaned.replace("2024", "")):
            offenders.append((name, cleaned[:60]))
    assert not offenders, offenders


def test_tone_stays_neutral_and_respectful(committed):
    avoid = texts_pt.TONE_AVOID
    for name, text in module_strings():
        lowered = text.lower()
        assert not any(word in lowered for word in avoid), (name, text[:60])
    for text in strings(committed):
        if text in committed["notice"]:
            continue
        assert not any(word in text.lower() for word in avoid), text[:80]


def test_the_word_for_user_performance_is_never_used(committed):
    for text in strings(committed):
        assert "acurácia" not in text.lower() and "accuracy" not in text.lower()
    assert "acurácia" not in Path(texts_pt.__file__).read_text(encoding="utf-8").lower()


def test_terms_exist_and_every_glossary_term_is_used(committed):
    ids = {item["id"] for item in committed["glossary"]}
    used = set()
    for page in committed["pages"]:
        for node in walk(page["sections"] + [page["intro"]]):
            if isinstance(node, dict) and "term" in node:
                assert node["term"] in ids, node
                used.add(node["term"])
        assert set(page["terms"]) <= ids
    assert used == ids, f"unused glossary terms: {sorted(ids - used)}"
    assert len(ids) == 30
    terms = [i["term"] for i in committed["glossary"]]
    assert terms == sorted(terms, key=slug_key)


def test_every_page_lists_the_definitions_of_its_terms(committed):
    for page in committed["pages"]:
        if page["kind"] == "glossary":
            continue
        assert [d["id"] for d in page["term_definitions"]] == page["terms"]


# --- figures -------------------------------------------------------------------------------------------------------


def test_every_figure_has_a_title_a_long_description_and_all_its_numbers_in_it(committed):
    referenced = {
        block["id"]
        for page in committed["pages"]
        for section in page["sections"]
        for block in section["blocks"]
        if block["kind"] == "figure"
    }
    assert referenced == set(committed["figures"]) or referenced <= set(committed["figures"])
    for figure_id in referenced:
        figure = committed["figures"][figure_id]
        assert figure["title"].strip() and len(figure["long"]) > 60 and figure["caption"]
        for number in figure["numbers"]:
            assert number in figure["long"], (figure_id, number)


def test_every_amputation_class_has_a_pattern_figure_and_it_matches_its_pattern(committed):
    for page in committed["pages"]:
        if page["kind"] == "class" and page["group"].startswith("limb"):
            ids = [b["id"] for s in page["sections"] for b in s["blocks"] if b["kind"] == "figure"]
            assert ids and all(i.startswith("fig-pattern-") for i in ids), page["path"]
            for figure_id in ids:
                figure = committed["figures"][figure_id]
                levels = figure["data"]["levels"]
                profile = profile_of({"group": page["group"], "fields": levels})
                assert k2_cases.engine_answer(page["group"], profile) == f"class:{page['class_id']}"


# --- links and examples ----------------------------------------------------------------------------------------------


def test_internal_links_resolve(committed):
    paths = {p["path"] for p in committed["pages"]}
    glossary_ids = {i["id"] for i in committed["glossary"]}
    allowed_other = {"/educacao", "/transparencia#regras"}
    for page in committed["pages"]:
        hrefs = [c["href"] for c in page.get("classes", [])] + [c["href"] for c in page.get("neighbors", [])]
        hrefs += [b["href"] for node in walk(page) if isinstance(node, dict) for b in [node] if "href" in b and node.get("href")]
        for href in hrefs:
            base = href.split("#")[0].split("?")[0]
            if href in allowed_other or base in paths:
                continue
            assert base == "/educacao/praticar" and re.fullmatch(
                r"/educacao/praticar\?grupo=[a-z_]+&nivel=easy&semente=0&caso=0", href
            ), (page["path"], href)
            assert href.split("grupo=")[1].split("&")[0] in k2_scope.ALLOWED_GROUPS
    assert glossary_ids


def test_each_class_page_has_a_study_mode_example_whose_answer_is_that_class(committed):
    for page in committed["pages"]:
        if page["kind"] != "class":
            continue
        examples = [b for s in page["sections"] for b in s["blocks"] if b["kind"] == "example"]
        assert len(examples) == 1, page["path"]
        case = k2_cases.case_from_id(examples[0]["case_id"])
        assert case.answer == f"class:{page['class_id']}" and case.group == page["group"]
        assert examples[0]["summary"] == case.presentation.summary


def test_class_pages_cite_the_booklet_page_of_the_catalog_and_the_codes_note(committed):
    from para_triage.rules.catalog import load_catalog

    catalog = load_catalog()
    for page in committed["pages"]:
        if page["kind"] == "class":
            assert page["source_page"] == catalog.classes[page["class_id"]].source_page
            text = " ".join(strings(page["sections"]))
            assert f"p. {page['source_page']}" in text
            assert "códigos T e F vêm do catálogo" in text


def test_the_review_sheet_builds_from_the_committed_content_and_asks_about_tone(committed):
    from para_triage.guide.review_sheet import build as sheet

    text = sheet(committed)
    assert "Tom:" in text and "atleta com deficiência" in text
    assert text.count("\n## ") >= 21  # one section per page except the glossary, plus the questions and the glossary
    assert committed["rules_id"] in text
