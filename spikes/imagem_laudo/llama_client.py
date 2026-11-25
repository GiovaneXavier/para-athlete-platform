"""Runs `llama-server` bound to 127.0.0.1 only, and asks it for JSON that obeys a schema.

Nothing here touches the network beyond the loopback address: the server is started with `--host 127.0.0.1`.
"""
from __future__ import annotations

import base64
import ctypes
import json
import subprocess
import time
from ctypes import wintypes
from pathlib import Path

import httpx

from paths import LLAMA_SERVER, RESULTS

HOST = "127.0.0.1"


class _Counters(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t), ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]


def memory_mb(pid: int) -> tuple[float, float]:
    """(current, peak) working set of a process, in MB (Windows only)."""
    kernel, psapi = ctypes.windll.kernel32, ctypes.windll.psapi
    kernel.OpenProcess.restype = wintypes.HANDLE
    handle = kernel.OpenProcess(0x0410, False, pid)  # QUERY_INFORMATION | VM_READ
    if not handle:
        return (float("nan"), float("nan"))
    try:
        c = _Counters()
        c.cb = ctypes.sizeof(c)
        psapi.GetProcessMemoryInfo(handle, ctypes.byref(c), c.cb)
        return (c.WorkingSetSize / 2**20, c.PeakWorkingSetSize / 2**20)
    finally:
        kernel.CloseHandle(handle)


class LlamaServer:
    def __init__(self, model: Path, mmproj: Path | None = None, port: int = 8081, context: int = 4096, threads: int | None = None, name: str = "model"):
        self.model, self.mmproj, self.port, self.context, self.threads, self.name = model, mmproj, port, context, threads, name
        self.process: subprocess.Popen | None = None
        self.peak_mb = 0.0

    def __enter__(self) -> "LlamaServer":
        RESULTS.mkdir(parents=True, exist_ok=True)
        args = [str(LLAMA_SERVER), "-m", str(self.model), "--host", HOST, "--port", str(self.port), "-c", str(self.context), "--no-webui"]
        if self.mmproj:
            args += ["--mmproj", str(self.mmproj)]
        if self.threads:
            args += ["-t", str(self.threads)]
        log = open(RESULTS / f"server_{self.name}.log", "w", encoding="utf-8")
        self.process = subprocess.Popen(args, stdout=log, stderr=subprocess.STDOUT)
        deadline = time.time() + 600
        while time.time() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError(f"llama-server stopped at start (see server_{self.name}.log)")
            try:
                if httpx.get(f"http://{HOST}:{self.port}/health", timeout=5).status_code == 200:
                    return self
            except httpx.HTTPError:
                pass
            time.sleep(2)
        raise RuntimeError("llama-server did not become ready in 10 minutes")

    def __exit__(self, *exc) -> None:
        if self.process:
            self.sample_memory()
            self.process.terminate()
            try:
                self.process.wait(30)
            except subprocess.TimeoutExpired:
                self.process.kill()

    def sample_memory(self) -> float:
        current, peak = memory_mb(self.process.pid)
        self.peak_mb = max(self.peak_mb, peak)
        return current

    def chat(self, parts: list[dict], schema: dict, system: str | None = None, max_tokens: int = 120, reuse_prefix: bool = False) -> tuple[dict, float]:
        """One request; returns (parsed JSON, seconds). The grammar makes the model answer inside the schema."""
        messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": parts}]
        body = {"messages": messages, "temperature": 0, "max_tokens": max_tokens, "cache_prompt": reuse_prefix,
                "response_format": {"type": "json_schema", "json_schema": {"name": "attrs", "strict": True, "schema": schema}}}
        t = time.time()
        r = httpx.post(f"http://{HOST}:{self.port}/v1/chat/completions", json=body, timeout=1800)
        seconds = time.time() - t
        r.raise_for_status()
        self.sample_memory()
        return json.loads(r.json()["choices"][0]["message"]["content"]), seconds


def image_part(png: bytes) -> dict:
    return {"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(png).decode()}}
