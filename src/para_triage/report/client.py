"""Minimal Ollama chat client (standard library only)."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass


class LLMUnavailable(RuntimeError):
    """The model server could not be reached or returned an error."""


@dataclass
class OllamaClient:
    model: str = "qwen2.5:7b"
    host: str = "http://localhost:11434"
    temperature: float = 0.2
    timeout: float = 600.0

    def _request(self, path: str, payload: dict | None = None, timeout: float | None = None) -> dict:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.host + path, data=data, headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout or self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            raise LLMUnavailable(f"Ollama at {self.host}: {exc}") from exc

    def is_available(self) -> bool:
        try:
            names = {m["name"] for m in self._request("/api/tags", timeout=5).get("models", [])}
        except LLMUnavailable:
            return False
        return self.model in names

    def chat(self, system: str, user: str) -> str:
        reply = self._request(
            "/api/chat",
            {
                "model": self.model,
                "stream": False,
                "options": {"temperature": self.temperature},
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
        )
        try:
            return reply["message"]["content"].strip()
        except (KeyError, TypeError) as exc:
            raise LLMUnavailable(f"unexpected reply from Ollama: {reply!r}") from exc
