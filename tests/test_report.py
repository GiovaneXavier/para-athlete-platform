import http.server
import json
import threading
from pathlib import Path

import numpy as np
import pytest

from para_triage.data import generate_dataset, record_to_profile
from para_triage.models import TrainConfig
from para_triage.models.predict import Predictor
from para_triage.models.train import prepare, run_once, save_checkpoint
from para_triage.report import (
    LLMUnavailable,
    OllamaClient,
    build_context,
    check_report,
    generate_report,
    render_template,
)
from para_triage.report.context import VALUE_PT, profile_facts
from para_triage.rules import (
    ArmFunction,
    CpDistribution,
    Impairment,
    LegFunction,
    LowerLimbLevel,
    Posture,
    Profile,
    Propulsion,
    RuleEngine,
    Severity,
    TrunkFunction,
    UpperLimbLevel,
)

engine = RuleEngine()


def prosthesis_profile():
    return Profile(
        impairments=frozenset({Impairment.LIMB_DEFICIENCY}),
        posture=Posture.PROSTHESIS,
        lower_left=LowerLimbLevel.BELOW_KNEE,
        lower_right=LowerLimbLevel.NONE,
        upper_left=UpperLimbLevel.NONE,
        upper_right=UpperLimbLevel.NONE,
    )


def fake_probabilities():
    classes = np.array([-1, 0, 63, 64])
    return np.array([0.02, 0.01, 0.07, 0.90]), classes


# --- context -------------------------------------------------------------------------------------------


def test_every_integer_enum_member_has_a_portuguese_label():
    for cls in (LowerLimbLevel, UpperLimbLevel, Severity, Propulsion, ArmFunction, TrunkFunction, LegFunction):
        for member in cls:
            assert f"{cls.__name__}.{member.name}" in VALUE_PT
    for member in CpDistribution:
        assert member.value in VALUE_PT


def test_none_means_different_things_in_different_scales():
    facts = profile_facts(
        Profile(
            impairments=frozenset({Impairment.MUSCLE_POWER}),
            posture=Posture.SEATED,
            leg_function=LegFunction.NONE,
            trunk_function=TrunkFunction.NONE,
            lower_left=LowerLimbLevel.NONE,
        )
    )
    assert "função das pernas: sem função" in facts
    assert "função de tronco: sem função" in facts
    assert "membro inferior esquerdo: sem amputação" in facts


def test_context_from_rules_only_has_no_probabilities():
    ctx = build_context(prosthesis_profile(), engine)
    assert [o.class_id for o in ctx.options] == [64]
    assert ctx.options[0].probability is None
    assert ctx.options[0].codes == ("T64", "F64")
    assert ctx.options[0].equipment == ("prótese de corrida",)


def test_context_with_probabilities_ranks_and_checks_agreement():
    probs, classes = fake_probabilities()
    ctx = build_context(prosthesis_profile(), engine, probs, classes)
    assert [o.class_id for o in ctx.options] == [64, 63]
    assert ctx.p_none == pytest.approx(0.01)
    assert ctx.rules_primary == 64 and ctx.rules_model_agree is True

    disagreeing = build_context(prosthesis_profile(), engine, np.array([0, 0, 0.9, 0.1]), classes)
    assert disagreeing.rules_model_agree is False
    assert "as regras e o modelo apontam classes diferentes" in disagreeing.flags


def test_missing_data_and_rule_abstention_are_reported():
    profile = Profile(impairments=frozenset({Impairment.SHORT_STATURE}), height_cm=124)
    probs, classes = np.array([0.1, 0.9]), np.array([0, 41])
    ctx = build_context(profile, engine, probs, classes)
    assert "comprimento do braço mais longo (cm)" in ctx.missing
    assert any("não conseguiram decidir" in f for f in ctx.flags)


# --- template and checks --------------------------------------------------------------------------------------


def test_template_is_always_faithful_to_its_own_facts():
    probs, classes = fake_probabilities()
    for ctx in (
        build_context(prosthesis_profile(), engine),
        build_context(prosthesis_profile(), engine, probs, classes),
        build_context(Profile(), engine),
    ):
        assert check_report(render_template(ctx), ctx) == []


def test_check_report_catches_unfaithful_drafts():
    probs, classes = fake_probabilities()
    ctx = build_context(prosthesis_profile(), engine, probs, classes)
    good = render_template(ctx)

    assert {i.kind for i in check_report(good.replace("T64", "T99"), ctx)} == {"unknown_class"}
    assert {i.kind for i in check_report(good + "\nClasse 12.", ctx)} == {"unknown_class"}
    assert {i.kind for i in check_report(good + "\nChance de 55%.", ctx)} == {"unknown_percentage"}
    assert {i.kind for i in check_report(good.replace("## Equipamentos", "## Outro"), ctx)} == {"missing_section"}
    assert {i.kind for i in check_report(good.replace("não substitui", "complementa"), ctx)} == {"missing_disclaimer"}


# --- generation with a guard ---------------------------------------------------------------------------------------


class ScriptedLLM:
    def __init__(self, *replies):
        self.replies, self.prompts = list(replies), []

    def chat(self, system, user):
        self.prompts.append(user)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


@pytest.fixture
def ctx():
    probs, classes = fake_probabilities()
    return build_context(prosthesis_profile(), engine, probs, classes)


def test_without_an_llm_the_template_is_used(ctx):
    report = generate_report(ctx)
    assert report.source == "template" and report.attempts == 0


def test_valid_llm_draft_is_kept(ctx):
    draft = render_template(ctx) + "\nT64 e F64 têm 90%."
    report = generate_report(ctx, ScriptedLLM(draft))
    assert report.source == "llm" and report.text == draft and report.attempts == 1


def test_bad_draft_is_retried_with_the_problems_listed(ctx):
    bad = render_template(ctx) + "\nTambém pode ser a T99."
    good = render_template(ctx)
    llm = ScriptedLLM(bad, good)
    report = generate_report(ctx, llm)
    assert report.source == "llm" and report.attempts == 2
    assert "T99" in llm.prompts[1] and "rejeitado" in llm.prompts[1]


def test_two_bad_drafts_fall_back_to_the_template(ctx):
    bad = "texto sem seções"
    report = generate_report(ctx, ScriptedLLM(bad, bad))
    assert report.source == "template" and report.rejected == bad
    assert report.issues and report.text == render_template(ctx)


def test_unavailable_llm_falls_back_to_the_template(ctx):
    report = generate_report(ctx, ScriptedLLM(LLMUnavailable("down")))
    assert report.source == "template"
    assert report.issues[0].kind == "llm_unavailable"


# --- Ollama client against a local stub ---------------------------------------------------------------------------------


@pytest.fixture
def stub_server():
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _send(self, body):
            data = json.dumps(body).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            self._send({"models": [{"name": "stub:1b"}]})

        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            self._send({"message": {"content": f"  eco: {payload['messages'][1]['content']}  "}})

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


def test_client_chat_and_availability(stub_server):
    client = OllamaClient(model="stub:1b", host=stub_server)
    assert client.is_available()
    assert client.chat("sistema", "olá") == "eco: olá"
    assert not OllamaClient(model="other:7b", host=stub_server).is_available()


def test_client_raises_when_the_server_is_down():
    client = OllamaClient(host="http://127.0.0.1:9", timeout=2)
    assert not client.is_available()
    with pytest.raises(LLMUnavailable):
        client.chat("s", "u")


# --- checkpoint round trip --------------------------------------------------------------------------------------------------


def test_predictor_reproduces_the_trained_model(tmp_path):
    df = generate_dataset(n_per_label=12, seed=11, groups=["limb_prosthesis", "short_stature"])
    cfg = TrainConfig(epochs=3, seed=0)
    _, artifacts = run_once(df, cfg, prepare(df))
    path = tmp_path / "model.pt"
    save_checkpoint(artifacts, cfg, path)

    predictor = Predictor.load(path)
    profiles = [record_to_profile(r) for r in df.head(5).to_dict("records")]
    proba = predictor.predict_proba(profiles)
    assert proba.shape == (5, len(artifacts["classes"]))
    assert np.allclose(proba.sum(axis=1), 1.0, atol=1e-5)
    assert list(predictor.classes) == list(artifacts["classes"])
    assert np.isclose(predictor.temperature, artifacts["temperature"])


# --- review notes and stricter structure checks ---------------------------------------------------------------


def combined_deficiency_profile():
    return Profile(
        impairments=frozenset({Impairment.LIMB_DEFICIENCY}),
        posture=Posture.STANDING,
        lower_left=LowerLimbLevel.THROUGH_OR_ABOVE_KNEE,
        lower_right=LowerLimbLevel.NONE,
        upper_left=UpperLimbLevel.ELBOW_OR_ABOVE,
        upper_right=UpperLimbLevel.NONE,
    )


def test_a_case_the_rules_cannot_decide_is_not_reported_as_nothing_eligible():
    classes = np.array([-1, 0, 42, 44])
    ctx = build_context(combined_deficiency_profile(), engine, np.array([1.0, 0.0, 0.0, 0.0]), classes)
    assert ctx.options == ()
    assert ctx.review_notes == ("deficiência combinada de membro superior e inferior",)
    assert not any("nenhuma classe elegível foi identificada" in f for f in ctx.flags)
    assert "as regras pedem avaliação de especialista" in ctx.flags

    text = render_template(ctx)
    assert "exigem avaliação de especialista" in text
    assert "deficiência combinada" in text
    assert check_report(text, ctx) == []


def test_review_notes_are_translated_and_unknown_ones_fall_back():
    from para_triage.report.context import review_note_pt

    assert review_note_pt("hemiplegia while standing; seated classes may apply") == (
        "hemiplegia em pé: as classes sentadas podem se aplicar"
    )
    assert review_note_pt("something new") == "something new"


GOOD_SKELETON = {
    "Resumo": "Resumo do caso.",
    "Classes prováveis": "Nenhuma classe candidata.",
    "Provas sugeridas": "Nenhuma prova a sugerir.",
    "Equipamentos": "Nenhum equipamento a indicar.",
    "Dados que faltam ou são incertos": "Nada em aberto.",
    "Próximos passos": "Procurar um Centro de Referência do CPB.",
    "Aviso": "Este relatório não substitui a classificação oficial.",
}


def draft(**overrides):
    sections = {**GOOD_SKELETON, **overrides}
    return "\n\n".join(f"## {title}\n{body}" for title, body in sections.items())


def test_structure_checks_catch_the_bad_llm_output_seen_in_practice():
    ctx = build_context(Profile(), engine)
    assert check_report(draft(), ctx) == []

    pasted = draft(**{"Provas sugeridas": "Procurar um Centro de Referência do CPB para a avaliação."})
    assert {i.kind for i in check_report(pasted, ctx)} == {"misplaced_text"}

    duplicated = draft() + "\n\n## Aviso\nEste relatório não substitui a classificação oficial."
    assert {i.kind for i in check_report(duplicated, ctx)} == {"duplicate_section"}

    empty = draft(Equipamentos="")
    assert {i.kind for i in check_report(empty, ctx)} == {"empty_section"}

    sections = list(GOOD_SKELETON.items())
    swapped = "\n\n".join(f"## {t}\n{b}" for t, b in [sections[0], sections[2], sections[1], *sections[3:]])
    assert {i.kind for i in check_report(swapped, ctx)} == {"section_order"}


def test_the_disclaimer_must_be_in_the_notice_section():
    ctx = build_context(Profile(), engine)
    no_notice = draft(Aviso="Texto sem o aviso devido.")
    assert {i.kind for i in check_report(no_notice, ctx)} == {"missing_disclaimer"}


def test_checks_catch_contradictions_and_untranslated_reasons():
    classes = np.array([-1, 0, 63, 64])
    ctx = build_context(prosthesis_profile(), engine, np.array([0.02, 0.01, 0.07, 0.90]), classes)
    good = render_template(ctx)
    assert check_report(good, ctx) == []

    kinds = {i.kind for i in check_report(good + "\nNenhuma classe candidata.", ctx)}
    assert kinds == {"contradiction"}
    kinds = {i.kind for i in check_report(good + "\nNenhum equipamento a indicar.", ctx)}
    assert kinds == {"contradiction"}

    reason = ctx.options[0].rule_reasons[0]
    kinds = {i.kind for i in check_report(good + f"\nRequisitos atendidos: {reason}", ctx)}
    assert kinds == {"untranslated_text"}


def test_the_no_candidates_instruction_only_appears_when_there_are_no_candidates():
    from para_triage.report.prompt import NO_CANDIDATES_INSTRUCTION, SYSTEM_PROMPT, user_prompt

    assert "Nenhuma classe candidata" not in SYSTEM_PROMPT
    with_candidates = build_context(prosthesis_profile(), engine)
    assert NO_CANDIDATES_INSTRUCTION not in user_prompt(with_candidates)
    without = build_context(Profile(), engine)
    assert NO_CANDIDATES_INSTRUCTION in user_prompt(without)


# --- the reference report against the guard, beyond three hand-made contexts ------------------------------------------

EXAMPLES = sorted((Path(__file__).parent.parent / "examples").glob("*.json"))


def _model_classes() -> np.ndarray:
    from para_triage.data.sampling import TARGETS

    return np.array(sorted({c for targets in TARGETS.values() for c in targets}))


def _probabilities(classes: np.ndarray, regime: str, true_label: int, rng: np.random.Generator) -> np.ndarray:
    """A probability vector of the kind the model produces in each situation the report must handle."""
    base = rng.dirichlet(np.full(len(classes), 0.3))
    if regime == "diffuse":
        return base
    target = {
        "confident": true_label,
        "wrong": int(rng.choice([c for c in classes if c != true_label])),
        "ambiguous": -1,
        "none": 0,
    }[regime]
    onehot = (classes == target).astype(float)
    return 0.1 * base + 0.9 * onehot


def _failures(profile, classes, probabilities_list):
    problems = []
    for probs in probabilities_list:
        for top_k in (1, 3):
            ctx = build_context(profile, engine, probs, classes if probs is not None else None, top_k)
            issues = check_report(render_template(ctx), ctx)
            if issues:
                problems.append((top_k, [(i.kind, i.detail) for i in issues]))
    return problems


def test_there_are_six_example_profiles():
    assert len(EXAMPLES) == 6


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.stem)
def test_template_passes_the_guard_on_every_example_profile(path):
    profile = record_to_profile(json.loads(path.read_text(encoding="utf-8")))
    classes = _model_classes()
    rng = np.random.default_rng(0)
    regimes = [None] + [_probabilities(classes, r, 0, rng) for r in ("confident", "wrong", "ambiguous", "none", "diffuse")]
    assert _failures(profile, classes, regimes) == []


def test_template_passes_the_guard_on_a_synthetic_sample_with_every_kind_of_flag():
    df = generate_dataset(n_per_label=3, seed=11)  # every group and every label, with noise and missing fields
    classes = _model_classes()
    rng = np.random.default_rng(1)
    failures, flags = {}, set()
    for i, record in enumerate(df.to_dict("records")):
        profile = record_to_profile(record)
        regimes = [None] + [_probabilities(classes, r, int(record["label"]), rng) for r in ("confident", "wrong", "ambiguous", "none", "diffuse")]
        problems = _failures(profile, classes, regimes)
        if problems:
            failures[i] = problems
        for probs in regimes:
            flags.update(build_context(profile, engine, probs, classes if probs is not None else None).flags)
    assert len(df) > 100
    assert failures == {}, f"{len(failures)} of {len(df)} synthetic profiles fail the guard; first: {next(iter(failures.items()))}"
    # The sample must actually reach the situations the report words differently, or the test proves little.
    for expected in (
        "as regras e o modelo apontam classes diferentes",
        "o perfil é limítrofe: o modelo vê chance relevante de caso ambíguo",
        "a confiança do modelo na classe mais provável é baixa",
        "as regras pedem avaliação de especialista",
    ):
        assert expected in flags, expected
    assert any("não conseguiram decidir" in f for f in flags)
