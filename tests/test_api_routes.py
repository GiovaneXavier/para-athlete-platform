"""The HTTP contract that the web depends on: same routes and methods after the split into routers."""
import pytest

pytest.importorskip("fastapi")  # these tests need the "api" extra

from para_triage.api.app import create_app  # noqa: E402


def test_openapi_exposes_exactly_the_documented_routes():
    paths = create_app().openapi()["paths"]
    routes = {(path, method) for path, ops in paths.items() for method in ops}
    assert routes == {
        ("/api/health", "get"),
        ("/api/triage", "post"),
        ("/api/report", "post"),
        ("/api/report/{job_id}", "get"),
        ("/api/transparency", "get"),
        ("/api/education/scope", "get"),
        ("/api/education/case", "get"),
        ("/api/education/quiz", "get"),
        ("/api/education/answer", "post"),
    }


def test_report_start_keeps_the_202_status_code():
    assert "202" in create_app().openapi()["paths"]["/api/report"]["post"]["responses"]
