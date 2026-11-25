"""Model extractors for the K34 pipeline. An image extractor is `png bytes -> Attrs`, a report extractor `text -> Attrs`.

Every answer is cached in a JSONL file keyed by the input's SHA-1, so a long run can be stopped and resumed, and so that
the table of results can be rebuilt without asking a model again. A request that fails (HTTP error or broken JSON) is
counted in `failures` and read as all-`?`; it is reported, never hidden.

The prompts are fixed here BEFORE any result is seen and are not tuned on the results.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Callable

from para_triage.consistency.png import decode_png, encode_png
from para_triage.consistency.schema import ATTRIBUTES, DOMAINS, Attrs, UNKNOWN

from llama_client import LlamaServer, image_part

SCHEMA = {
    "type": "object",
    "properties": {name: {"enum": [str(v) for v in DOMAINS[name]]} for name in ATTRIBUTES},
    "required": list(ATTRIBUTES),
    "additionalProperties": False,
}

IMAGE_PROMPT = (
    "This is a synthetic drawing of one person (a figure, not a photograph). Describe only what is visible. "
    "Fill in the JSON. For each limb give the amputation level, or ? if it cannot be determined from the image. "
    "Lower limb: 0 = complete leg, 1 = partial foot missing, 2 = missing below the knee, 3 = missing at or above the knee. "
    "Upper limb: 0 = complete arm, 1 = missing at or below the elbow (forearm or hand), 2 = missing at or above the elbow. "
    "lower_left, lower_right, upper_left and upper_right are the PERSON's own left and right, not the viewer's: "
    "the person's left is on the right-hand side of the picture when the person faces the viewer. "
    "wheelchair: yes if the person uses a wheelchair, no if not, ? if unclear. "
    "prosthesis: yes if a prosthesis (artificial limb) is visible, no if not, ? if unclear."
)

REPORT_SYSTEM = (
    "You read short medical-style reports written in Portuguese and extract what they say about the limbs of one person. "
    "Answer only with the JSON. Use ? for anything the report does not say. Never guess. "
    "Lower limb (perna, membro inferior, MI): 0 = complete or intact (membro íntegro, completo, ausência de amputação), "
    "1 = partial foot amputation (amputação parcial do pé), 2 = below the knee (transtibial, abaixo do joelho), "
    "3 = through or above the knee (transfemoral, desarticulação do joelho, acima do joelho). "
    "Upper limb (braço, membro superior, MS): 0 = complete or intact, 1 = wrist or below the elbow (transradial, abaixo do cotovelo, punho), "
    "2 = elbow or above (transumeral, acima do cotovelo, desarticulação do cotovelo). "
    "esquerdo/esq. = left, direito/dir. = right. A side that the report does not mention is ?. "
    "wheelchair and prosthesis: yes or no only if the report says so, otherwise ?."
)


LIMB_OF = {"left_leg": "lower_left", "right_leg": "lower_right", "left_arm": "upper_left", "right_arm": "upper_right"}


def to_attrs(raw: dict) -> Attrs:
    if "statements" in raw:  # v3 report answer: a list of statements; a limb not listed stays `?`; the first statement about a limb wins
        out: dict = {}
        for st in raw["statements"]:
            name, level = LIMB_OF[st["limb"]], int(st["level"])
            if name not in out and level in DOMAINS[name]:  # a level outside the domain (an arm at 3) is ignored
                out[name] = level
        for flag in ("wheelchair", "prosthesis"):
            out[flag] = raw[flag]
        return Attrs.from_mapping(out)
    out = {}
    for name in ATTRIBUTES:
        value = raw[name]
        out[name] = UNKNOWN if value == UNKNOWN else (value if value in ("yes", "no") else int(value))
    return Attrs.from_mapping(out)


class Cache:
    def __init__(self, path: Path):
        self.path = path
        self.data: dict[str, dict] = {}
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                row = json.loads(line)
                self.data[row["key"]] = row

    def put(self, key: str, row: dict) -> None:
        row = {"key": key, **row}
        self.data[key] = row
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


class ModelExtractor:
    """Wraps a running server. `__call__` takes png bytes (image kind) or text (report kind)."""

    def __init__(self, server: LlamaServer, kind: str, cache_path: Path, version: str = "v1"):
        assert kind in ("image", "report")
        self.server, self.kind, self.version = server, kind, version
        self.cache = Cache(cache_path)
        self.failures = 0
        self.seconds: list[float] = []  # of the requests actually made in this run

    def raw(self, item) -> dict:
        data = item if isinstance(item, bytes) else item.encode("utf-8")
        key = hashlib.sha1(data).hexdigest()
        if key in self.cache.data:
            return self.cache.data[key]
        try:
            from prompts import PROMPTS  # here, because prompts.py imports this module

            p = PROMPTS[self.version]
            if self.kind == "image":
                answer, seconds = self.server.chat([{"type": "text", "text": p["image_text"]}, image_part(item)], p["image_schema"], max_tokens=p["image_tokens"])
            else:  # the system text is the same for every report: let the server keep its processed prefix
                answer, seconds = self.server.chat([{"type": "text", "text": item}], p["report_schema"], system=p["report_system"], max_tokens=120, reuse_prefix=True)
            row = {"answer": answer, "seconds": round(seconds, 2), "ok": True}
            self.seconds.append(seconds)
        except Exception as error:  # reported, never hidden
            row = {"answer": None, "seconds": 0.0, "ok": False, "error": repr(error)[:200]}
        self.cache.put(key, row)
        return row

    def __call__(self, item) -> Attrs:
        row = self.raw(item)
        if not row["ok"]:
            self.failures += 1
            return Attrs()
        return to_attrs(row["answer"])


def mirrored(png: bytes) -> bytes:
    """The picture reflected left to right (the person's sides swap in the label)."""
    return encode_png(decode_png(png)[:, ::-1].copy())


def cached_only(kind: str, cache_path: Path) -> Callable:
    """A reader that never calls a model: answers from the cache, and `?` for anything not there (counted)."""
    cache = Cache(cache_path)
    miss = {"n": 0}

    def read(item) -> Attrs:
        data = item if isinstance(item, bytes) else item.encode("utf-8")
        row = cache.data.get(hashlib.sha1(data).hexdigest())
        if not row or not row["ok"]:
            miss["n"] += 1
            return Attrs()
        return to_attrs(row["answer"])

    read.misses = miss  # type: ignore[attr-defined]
    return read
