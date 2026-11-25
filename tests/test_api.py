import time

import pytest

pytest.importorskip("fastapi")  # these tests need the "api" extra
from fastapi.testclient import TestClient

from para_triage.api.app import create_app
from para_triage.data import generate_dataset
from para_triage.models import TrainConfig
from para_triage.models.train import prepare, run_once, save_checkpoint
from para_triage.report import LLMUnavailable
from para_triage.report.prompt import render_template

PROSTHESIS = {
    "impairments": ["limb_deficiency"],
    "posture": "prosthesis",
    "lower_left": 2,
    "lower_right": 0,
    "upper_left": 0,
    "upper_right": 0,
}


class FakeLLM:
    model = "fake:1b"
    host = "http://fake"
    temperature = 0.0

    def __init__(self, available=True, reply=None, error=None):
        self.available, self.reply, self.error = available, reply, error

    def is_available(self):
        return self.available

    def chat(self, system, user):
        if self.error:
            raise self.error
        return self.reply


@pytest.fixture(scope="module")
def checkpoint(tmp_path_factory):
    df = generate_dataset(n_per_label=12, seed=3, groups=["limb_prosthesis", "short_stature"])
    cfg = TrainConfig(epochs=3, seed=0)
    _, artifacts = run_once(df, cfg, prepare(df))
    path = tmp_path_factory.mktemp("ckpt") / "model.pt"
    save_checkpoint(artifacts, cfg, path)
    return path


def run_report(c, payload):
    start = c.post("/api/report", json=payload)
    assert start.status_code == 202
    job_id = start.json()["job_id"]
    for _ in range(100):
        job = c.get(f"/api/report/{job_id}").json()
        if job["status"] in ("done", "error"):
            return job
        time.sleep(0.05)
    raise AssertionError("job did not finish")


def client(tmp_path, checkpoint=None, llm=None):
    app = create_app(checkpoint or tmp_path / "missing.pt", llm or FakeLLM())
    return TestClient(app)


def test_health_reports_model_and_ollama(tmp_path, checkpoint):
    with client(tmp_path, checkpoint, FakeLLM(available=False)) as c:
        body = c.get("/api/health").json()
    assert body == {"status": "ok", "model_loaded": True, "ollama_available": False, "ollama_model": "fake:1b"}


def test_triage_without_a_checkpoint_uses_the_rules_only(tmp_path):
    with client(tmp_path) as c:
        body = c.post("/api/triage", json={"profile": PROSTHESIS}).json()
    assert body["model_available"] is False
    assert [o["class_id"] for o in body["options"]] == [64]
    assert body["options"][0]["probability"] is None
    assert body["options"][0]["codes"] == ["T64", "F64"]
    assert "## Aviso" in body["reference_report"]


def test_triage_with_a_checkpoint_returns_probabilities(tmp_path, checkpoint):
    with client(tmp_path, checkpoint) as c:
        body = c.post("/api/triage", json={"profile": PROSTHESIS, "top_k": 2}).json()
    assert body["model_available"] is True
    assert len(body["options"]) <= 2
    assert all(0 <= o["probability"] <= 1 for o in body["options"])
    assert body["p_none"] is not None


def test_invalid_values_are_rejected(tmp_path):
    with client(tmp_path) as c:
        assert c.post("/api/triage", json={"profile": {"posture": "flying"}}).status_code == 422
        assert c.post("/api/triage", json={"profile": {"ankle_pf_mrc": 9}}).status_code == 422
        assert c.post("/api/triage", json={"profile": {"unknown_field": 1}}).status_code == 422
        assert c.post("/api/triage", json={"profile": {"lower_left": 7}}).status_code == 422


def test_an_empty_profile_is_accepted_and_reports_nothing_eligible(tmp_path):
    with client(tmp_path) as c:
        body = c.post("/api/triage", json={"profile": {}}).json()
    assert body["options"] == []
    assert body["flags"]


def test_report_returns_a_verified_llm_text(tmp_path):
    triage_payload = {"profile": PROSTHESIS}
    with client(tmp_path) as c:
        reference = c.post("/api/triage", json=triage_payload).json()["reference_report"]
    with client(tmp_path, llm=FakeLLM(reply=reference)) as c:
        job = run_report(c, triage_payload)
    assert job["status"] == "done"
    body = job["report"]
    assert body["source"] == "llm" and body["attempts"] == 1 and body["model"] == "fake:1b"
    assert body["text"] == reference


def test_report_falls_back_to_the_template_when_the_llm_fails(tmp_path):
    with client(tmp_path, llm=FakeLLM(error=LLMUnavailable("down"))) as c:
        body = run_report(c, {"profile": PROSTHESIS})["report"]
    assert body["source"] == "template" and body["model"] is None
    assert body["issues"][0]["kind"] == "llm_unavailable"


def test_report_rejects_an_unfaithful_draft(tmp_path):
    with client(tmp_path, llm=FakeLLM(reply="Classe T99 com 100%.")) as c:
        body = run_report(c, {"profile": PROSTHESIS})["report"]
    assert body["source"] == "template" and body["attempts"] == 2
    kinds = {i["kind"] for i in body["issues"]}
    assert {"unknown_class", "missing_section"} <= kinds


def test_unknown_job_is_404_and_a_crashing_job_ends_in_error(tmp_path):
    class Boom(FakeLLM):
        def chat(self, system, user):
            raise RuntimeError("boom")

    with client(tmp_path, llm=Boom()) as c:
        assert c.get("/api/report/nope").status_code == 404
        job = run_report(c, {"profile": PROSTHESIS})
    assert job["status"] == "error" and "boom" in job["error"]


def test_a_case_for_a_specialist_returns_the_review_notes(tmp_path):
    combined = {
        "impairments": ["limb_deficiency"],
        "posture": "standing",
        "lower_left": 3,
        "lower_right": 0,
        "upper_left": 2,
        "upper_right": 0,
    }
    with client(tmp_path) as c:
        body = c.post("/api/triage", json={"profile": combined}).json()
    assert body["review_notes"] == ["deficiência combinada de membro superior e inferior"]
    assert "exigem avaliação de especialista" in body["reference_report"]
