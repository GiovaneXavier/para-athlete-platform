"""Study mode (K2) over HTTP: scope, refusals, answer key protection, determinism."""
import json
import re

import pytest

pytest.importorskip("fastapi")  # these tests need the "api" extra
from fastapi.testclient import TestClient  # noqa: E402

from para_triage.api.app import create_app  # noqa: E402
from para_triage.education import scope  # noqa: E402
from para_triage.education.cases import engine_answer, get_case  # noqa: E402
from para_triage.provenance_info import rules_version  # noqa: E402
from para_triage.rules.catalog import load_catalog  # noqa: E402

LEAK_KEYS = {"answer", "answer_id", "answer_label", "correct", "trace", "steps", "class_id", "verdict", "conclusion", "outcome"}
FORBIDDEN_GROUPS = [*scope.EXCLUDED_GROUPS, "neuro", "unknown", ""]


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    missing = tmp_path_factory.mktemp("nockpt") / "missing.pt"
    with TestClient(create_app(missing)) as c:
        yield c


def keys_of(node):
    if isinstance(node, dict):
        for key, value in node.items():
            yield key
            yield from keys_of(value)
    elif isinstance(node, list):
        for value in node:
            yield from keys_of(value)


def case_params(group="visual", difficulty="easy", seed=3, index=0):
    return {"group": group, "difficulty": difficulty, "seed": seed, "index": index}


# --- scope --------------------------------------------------------------------------------------------------


def test_scope_lists_the_four_groups_the_notice_and_the_rule_book_version(client):
    body = client.get("/api/education/scope").json()
    assert body["notice"] == scope.NOTICE
    assert body["rules_version"] == rules_version().id and body["case_version"] == scope.CASE_VERSION
    assert [g["id"] for g in body["groups"]] == list(scope.ALLOWED_GROUPS)
    assert body["quiz_sizes"] == [5, 10, 15]
    standing = next(g for g in body["groups"] if g["id"] == "limb_standing")
    assert "7 cm" in standing["warning"]
    options = [o["id"] for o in standing["options"]]
    assert options[-3:] == ["none", "specialist", "insufficient"] and options[0] == "class:42"


def test_nothing_outside_the_scope_is_mentioned_by_the_api(client):
    texts = [
        client.get("/api/education/scope").text,
        *(client.get("/api/education/case", params=case_params(g, d, 5, i)).text for g in scope.ALLOWED_GROUPS for d in scope.DIFFICULTIES for i in range(3)),
        client.get("/api/education/quiz", params={"seed": 5}).text,
    ]
    shown = "\n".join(texts)
    for group in scope.EXCLUDED_GROUPS:
        assert group not in shown
    assert not re.search(r"[Cc]lasse (20|3[1-8]|5[1-7]|7[12])\b", shown)
    assert not re.search(r"class:(20|3[1-8]|5[1-7]|7[12])\b", shown)


def test_openapi_only_lists_the_groups_of_the_study_mode(client):
    document = client.get("/openapi.json").json()
    schemas = document["components"]["schemas"]

    def group_enum(parameter):
        schema = parameter["schema"]
        schema = schema.get("items", schema)
        if "anyOf" in schema:
            schema = next(s for s in schema["anyOf"] if s.get("type") == "array")["items"]
        return set(schema.get("enum", []))

    case_group = next(p for p in document["paths"]["/api/education/case"]["get"]["parameters"] if p["name"] == "group")
    quiz_groups = next(p for p in document["paths"]["/api/education/quiz"]["get"]["parameters"] if p["name"] == "groups")
    assert group_enum(case_group) == set(scope.ALLOWED_GROUPS)
    assert group_enum(quiz_groups) == set(scope.ALLOWED_GROUPS)
    assert set(schemas["CaseOut"]["properties"]["group"]["enum"]) == set(scope.ALLOWED_GROUPS)


# --- refusals -----------------------------------------------------------------------------------------------


@pytest.mark.parametrize("group", FORBIDDEN_GROUPS)
def test_groups_outside_the_scope_are_refused_on_every_route(client, group):
    assert client.get("/api/education/case", params=case_params(group)).status_code == 422
    assert client.get("/api/education/quiz", params={"seed": 1, "groups": group}).status_code == 422
    assert client.get("/api/education/quiz", params={"seed": 1, "groups": ["visual", group]}).status_code == 422
    answer = client.post("/api/education/answer", json={"case_id": f"k2.{scope.CASE_VERSION}.{group}.easy.1.0", "choice": "none"})
    assert answer.status_code == 404


def test_bad_inputs_are_refused(client):
    assert client.get("/api/education/case", params=case_params(difficulty="mixed")).status_code == 422
    assert client.get("/api/education/case", params=case_params(seed=-1)).status_code == 422
    assert client.get("/api/education/quiz", params={"seed": 1, "size": 7}).status_code == 422
    assert client.get("/api/education/quiz", params={"size": 5}).status_code == 422
    assert client.post("/api/education/answer", json={"case_id": "nonsense", "choice": None}).status_code == 404
    case_id = client.get("/api/education/case", params=case_params()).json()["case_id"]
    assert client.post("/api/education/answer", json={"case_id": case_id, "choice": "class:99"}).status_code == 422
    assert client.post("/api/education/answer", json={"case_id": case_id, "choice": "class:44", "extra": 1}).status_code == 422


# --- the answer key does not leak ---------------------------------------------------------------------------


def test_case_and_quiz_responses_carry_no_answer(client):
    catalog = load_catalog()
    names = {spec.name_pt for spec in catalog.classes.values()}
    for group in scope.ALLOWED_GROUPS:
        for level in scope.DIFFICULTIES:
            for index in range(4):
                body = client.get("/api/education/case", params=case_params(group, level, 7, index)).json()
                assert not LEAK_KEYS & set(keys_of(body)), body.keys()
                assert body["notice"] == scope.NOTICE and body["review_status"] == "draft"
                assert not any(name in json.dumps(body, ensure_ascii=False) for name in names)
    quiz = client.get("/api/education/quiz", params={"seed": 7, "size": 15}).json()
    assert not LEAK_KEYS & set(keys_of(quiz)) and len(quiz["cases"]) == 15
    assert not any(name in json.dumps(quiz, ensure_ascii=False) for name in names)


def test_the_options_are_the_same_at_every_level_of_a_group(client):
    for group in scope.ALLOWED_GROUPS:
        lists = [
            client.get("/api/education/case", params=case_params(group, level, 2, 0)).json()["options"]
            for level in scope.DIFFICULTIES
        ]
        assert lists[0] == lists[1] == lists[2]


def test_the_case_text_is_independent_of_the_choice_and_calls_do_not_change_it(client):
    params = case_params("short_stature", "medium", 9, 2)
    first = client.get("/api/education/case", params=params).json()
    client.post("/api/education/answer", json={"case_id": first["case_id"], "choice": None})
    assert client.get("/api/education/case", params=params).json() == first


# --- answering ----------------------------------------------------------------------------------------------


def test_correct_wrong_and_revealed_answers_come_with_the_trace_and_the_limits(client):
    for group in scope.ALLOWED_GROUPS:
        case = client.get("/api/education/case", params=case_params(group, "medium", 4, 1)).json()
        truth = get_case(group, "medium", 4, 1).answer
        assert engine_answer(group, get_case(group, "medium", 4, 1).candidate.profile) == truth
        wrong = next(o["id"] for o in case["options"] if o["id"] != truth)

        right = client.post("/api/education/answer", json={"case_id": case["case_id"], "choice": truth}).json()
        assert right["outcome"] == "correct" and right["correct"] is True and right["answer_id"] == truth
        assert right["steps"] and right["conclusion"] and right["limits"] and right["references"]
        assert right["notice"] == scope.NOTICE and right["review_status"] == "draft"
        assert all(s["result_label"] in {"atende", "não atende", "não avaliado"} for s in right["steps"])

        miss = client.post("/api/education/answer", json={"case_id": case["case_id"], "choice": wrong}).json()
        assert miss["outcome"] == "wrong" and miss["correct"] is False and miss["answer_id"] == truth

        shown = client.post("/api/education/answer", json={"case_id": case["case_id"], "choice": None}).json()
        assert shown["outcome"] == "revealed" and shown["correct"] is False and shown["answer_id"] == truth


def test_the_class_name_appears_only_in_the_answer(client):
    case = client.get("/api/education/case", params=case_params("limb_prosthesis", "easy", 1, 0)).json()
    answer = client.post("/api/education/answer", json={"case_id": case["case_id"], "choice": None}).json()
    assert answer["answer_id"].startswith("class:") and answer["class_name_pt"] and answer["class_codes"]
    assert answer["references"][0].startswith("Cartilha do CPB (2024), p. ")


def test_hard_cases_with_a_hidden_field_have_the_missing_data_answer(client):
    seen = set()
    for index in range(60):
        case = get_case("short_stature", "hard", 1, index)
        seen.add(case.answer)
    assert seen == {scope.OPTION_INSUFFICIENT}
    body = client.get("/api/education/case", params=case_params("short_stature", "hard", 1, 0)).json()
    assert "não medido" in json.dumps(body, ensure_ascii=False)


# --- determinism ---------------------------------------------------------------------------------------------


def test_same_parameters_same_responses_and_a_different_seed_differs(client):
    one = client.get("/api/education/quiz", params={"seed": 21, "size": 10}).json()
    assert client.get("/api/education/quiz", params={"seed": 21, "size": 10}).json() == one
    assert client.get("/api/education/quiz", params={"seed": 22, "size": 10}).json() != one
    ids = [c["case_id"] for c in one["cases"]]
    assert len(set(ids)) == 10 and all(i.startswith(f"k2.{scope.CASE_VERSION}.") for i in ids)


def test_quiz_can_be_limited_to_some_groups_and_one_level(client):
    body = client.get("/api/education/quiz", params={"seed": 2, "size": 5, "groups": ["visual", "short_stature"], "difficulty": "easy"}).json()
    assert {c["group"] for c in body["cases"]} == {"visual", "short_stature"}
    assert {c["difficulty"] for c in body["cases"]} == {"easy"}
