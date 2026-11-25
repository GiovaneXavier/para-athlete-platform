"""POST /api/report and GET /api/report/{job_id}.

Reports take minutes on CPU, so they run as jobs: POST returns an id at once and the client
polls. One worker, because the local LLM serves one request at a time.
"""
from __future__ import annotations

import threading
import time
import uuid
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, HTTPException, Request

from ...report import OllamaClient, generate_report
from ...report.context import ReportContext
from ..context import context_for
from ..schemas import IssueOut, JobOut, ReportIn, ReportOut

MAX_JOBS = 200

router = APIRouter()


class JobStore:
    """In-memory jobs of one app instance, plus the single-worker executor that runs them."""

    def __init__(self, max_jobs: int = MAX_JOBS):
        self.max_jobs = max_jobs
        self.jobs: OrderedDict[str, JobOut] = OrderedDict()
        self.lock = threading.Lock()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="report")

    def set(self, job: JobOut) -> None:
        with self.lock:
            self.jobs[job.job_id] = job
            while len(self.jobs) > self.max_jobs:
                self.jobs.popitem(last=False)

    def get(self, job_id: str) -> JobOut | None:
        with self.lock:
            return self.jobs.get(job_id)

    def run(self, job_id: str, ctx: ReportContext, client: OllamaClient) -> None:
        self.set(JobOut(job_id=job_id, status="running"))
        started = time.perf_counter()
        try:
            result = generate_report(ctx, client)
            report = ReportOut(
                text=result.text,
                source=result.source,
                attempts=result.attempts,
                issues=[IssueOut(kind=i.kind, detail=i.detail) for i in result.issues],
                elapsed_s=round(time.perf_counter() - started, 1),
                model=client.model if result.source == "llm" else None,
            )
            self.set(JobOut(job_id=job_id, status="done", report=report))
        except Exception as exc:  # the job must always end in a terminal state
            self.set(JobOut(job_id=job_id, status="error", error=f"{type(exc).__name__}: {exc}"))


@router.post("/api/report", response_model=JobOut, status_code=202)
def start_report(payload: ReportIn, request: Request) -> JobOut:
    """Starts the LLM report (with the fidelity guard) and returns a job to poll."""
    app = request.app
    ctx = context_for(app, payload)  # fast; validation and model errors surface here
    default_llm = app.state.llm
    client = default_llm
    if payload.model and payload.model != default_llm.model:
        client = OllamaClient(model=payload.model, host=default_llm.host, temperature=default_llm.temperature)
    job = JobOut(job_id=uuid.uuid4().hex, status="queued")
    store: JobStore = app.state.jobs
    store.set(job)
    store.executor.submit(store.run, job.job_id, ctx, client)
    return job


@router.get("/api/report/{job_id}", response_model=JobOut)
def get_report(job_id: str, request: Request) -> JobOut:
    job = request.app.state.jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return job
