import pytest

pytest.importorskip("fastapi")  # these tests need the "api" extra
from fastapi.testclient import TestClient  # noqa: E402

from para_triage.api.app import create_app  # noqa: E402


def client(tmp_path, checkpoint=None):
    return TestClient(create_app(checkpoint or tmp_path / "missing.pt"))


def test_transparency_serves_the_committed_report_and_checks_the_live_rule_book(tmp_path):
    with client(tmp_path) as c:
        response = c.get("/api/transparency")
    assert response.status_code == 200
    body = response.json()
    assert body["report"]["evidence_level"] == "N1"
    assert body["report"]["experiments"]["E1"]["evidence_level"] == "N1"
    assert body["live"]["rules_match_report"] is True
    assert body["live"]["rules_id"] == body["report"]["rules"]["id"]
    assert body["live"]["served_model"] is None and body["live"]["served_model_matches_card"] is None


def test_a_checkpoint_other_than_the_one_in_the_card_is_reported_as_a_mismatch(tmp_path):
    other = tmp_path / "model.pt"
    other.write_bytes(b"some other weights")
    # Predictor.load cannot read this file, so the live block is built directly.
    from para_triage.api.routers.transparency import DEFAULT_REPORT, load_transparency

    result = load_transparency(DEFAULT_REPORT, other)
    assert result.live.served_model.known is False and result.live.served_model.status == "unknown"
    if result.report.model_card is not None:
        assert result.live.served_model_matches_card is False


def test_report_unavailable_gives_503_and_leaves_triage_working(tmp_path, monkeypatch):
    monkeypatch.setenv("PARA_TRANSPARENCY_JSON", str(tmp_path / "nowhere.json"))
    with client(tmp_path) as c:
        response = c.get("/api/transparency")
        assert response.status_code == 503 and "unavailable" in response.json()["detail"]
        assert c.post("/api/triage", json={"profile": {}}).status_code == 200


def test_an_invalid_report_file_gives_503(tmp_path, monkeypatch):
    broken = tmp_path / "broken.json"
    broken.write_text('{"schema_version": 1}', encoding="utf-8")
    monkeypatch.setenv("PARA_TRANSPARENCY_JSON", str(broken))
    with client(tmp_path) as c:
        assert c.get("/api/transparency").status_code == 503
