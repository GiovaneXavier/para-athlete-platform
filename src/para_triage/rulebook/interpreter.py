"""Interpreter of the YAML rule book (K20, ADR 0020). Read-only on the core; the current engine stays the default.

A group file (data/groups/<group>.yaml) says what is measured, which parameters (values by date, one source and
one status each) and criteria exist, which criteria give evidence to each class (`class_rules`), and an ordered
`decision` list. Evaluating a profile gives a verdict per class, with the seven states of the current engine, and a
trace by criterion. The interpreter knows nothing about any particular group: names come from the YAML.

Constructs of the format (kept few on purpose): criterion test (gt, lt, between, eq, ne; inclusive flags that may be a
parameter or its negation), parameter by sex-like key (`by`), parameter borrowed from another group (`same_as`), the declared impairments as boolean measures
(`impairment_measures`), a rule that decides one group of classes (`class_groups`, `scope`), derived sum, max or min, class rule (any_of, all_of),
`unless` chain, flags, decision rules (all_missing, any_missing, any_class, flag, equals) with results (all, classes,
meets/pick, borderline with a condition, rest) and the fields they report as missing (`report_missing`: those of the list that are missing; `report_always`: the list,
as it is), validity
dates, variants (parameter overrides). A table of levels is a run of decision rules with `equals`, read in order.
"""
from __future__ import annotations

import datetime as dt
import operator
from dataclasses import dataclass, field
from functools import lru_cache, reduce
from pathlib import Path

import yaml

STATUSES = ("meets", "borderline", "needs_review", "insufficient_data", "not_met", "not_applicable", "not_implemented")
REVIEW_STATUSES = ("implemented", "provisional", "contested", "reviewed")
DATA = Path(__file__).parent / "data"
DEFAULT_VARIANT = "cpb-2024"
DERIVE = {"sum": lambda parts: reduce(operator.add, parts), "max": max, "min": min}


class RulebookError(ValueError):
    """The rule book or the request is malformed."""


class NoValueInForce(RulebookError):
    """A parameter has no value on the reference date."""


class _NoKey(Exception):
    """The measure that selects a parameter value (for example the sex) is missing."""


@dataclass(frozen=True)
class Verdict:
    class_id: int
    status: str
    reasons: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()


@dataclass(frozen=True)
class Step:
    criterion: str
    class_id: int | None
    measure: str
    value: object
    test: str
    result: str  # met, not_met, not_assessed, skipped (outside its validity)
    reason: str
    source: dict
    superseded_by: str | None = None
    reference: dict = field(default_factory=dict)  # parameter values the test used


@dataclass
class Evaluation:
    verdicts: dict[int, Verdict]
    trace: list[Step] = field(default_factory=list)
    decision: str = ""

    @property
    def meets(self) -> list[int]:
        return [c for c, v in self.verdicts.items() if v.status == "meets"]


def _read(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=None)
def sources() -> dict:
    return _read(DATA / "sources.yaml")["sources"]


def load_variant(spec: str | Path | dict = DEFAULT_VARIANT) -> dict:
    """A variant by name (data/variants/<name>.yaml), by file path, or as a dict."""
    if isinstance(spec, dict):
        return {"overrides": {}, **spec}
    path = Path(spec) if str(spec).endswith((".yaml", ".yml")) else DATA / "variants" / f"{spec}.yaml"
    if not path.is_file():
        raise RulebookError(f"unknown variant: {spec}")
    return {"overrides": {}, **_read(path)}


def in_force(valid: dict | None, on: dt.date) -> bool:
    if not valid:
        return True
    return (valid.get("from") is None or valid["from"] <= on) and (valid.get("to") is None or on <= valid["to"])


class Rulebook:
    def __init__(self, data: dict, known_sources: dict | None = None):
        self.data = data
        self.name = data["rulebook"]
        self.classes = list(data["classes"])
        self.measures = list(data["measures"])
        for name, spec in data.get("parameters", {}).items():
            if "same_as" in spec:  # a parameter that is another group's: the value lives in one place
                borrowed = Rulebook.load(spec["same_as"]).data["parameters"].get(name)
                if borrowed is None:
                    raise RulebookError(f"{self.name}.parameters.{name}: {spec['same_as']} has no such parameter")
                data["parameters"][name] = borrowed
        self._validate(sources() if known_sources is None else known_sources)

    @classmethod
    def load(cls, group: str) -> Rulebook:
        path = DATA / "groups" / f"{group}.yaml"
        if not path.is_file():
            raise RulebookError(f"unknown group: {group}")
        return cls(_read(path))

    def _validate(self, known: dict) -> None:
        d = self.data
        specs = [d, *d.get("pathways", {}).values()]  # the group file and each pathway
        for kind in ("parameters", "criteria", "flags"):
            for name, spec in [i for s in specs for i in s.get(kind, {}).items()]:
                where = f"{self.name}.{kind}.{name}"
                if (spec.get("source") or {}).get("doc") not in known:
                    raise RulebookError(f"{where}: missing or unknown source")
                if spec.get("status") not in REVIEW_STATUSES:
                    raise RulebookError(f"{where}: status must be one of {REVIEW_STATUSES}")
                if spec["status"] == "reviewed" and not (spec.get("reviewer") and spec.get("reviewed_on")):
                    raise RulebookError(f"{where}: a reviewed item needs reviewer and reviewed_on")
        for spec in specs:
            for cls, rule in spec.get("class_rules", {}).items():
                used = rule.get("all_of") or rule.get("any_of") or []
                if not used or not set(used) <= set(spec.get("criteria", {})):
                    raise RulebookError(f"{self.name}.class_rules.{cls}: unknown or empty criteria")
        for rule in [*d.get("gate", []), *(r for s in specs for r in s.get("decision", []))]:
            if "scope" in rule and rule["scope"] not in d.get("class_groups", {}):
                raise RulebookError(f"{self.name}.decision.{rule['id']}: unknown class group {rule['scope']!r}")
        if "pathways" in d and (d.get("merge") != "best_status" or "decision" in d or not all(p.get("applies_to") for p in d["pathways"].values())):
            raise RulebookError(f"{self.name}: pathways need `merge: best_status`, an `applies_to` each, and no decision of their own")
        for rule in [*d.get("gate", []), *(r for s in specs for r in s.get("decision", []))]:  # a row of a table of levels is a claim about the booklet
            if "equals" in rule.get("when", {}) and ((rule.get("source") or {}).get("doc") not in known or rule.get("status") not in REVIEW_STATUSES):
                raise RulebookError(f"{self.name}.decision.{rule['id']}: a table row needs a known source and a status")
        for case in d.get("tests", []):
            if (case.get("source") or {}).get("doc") not in known:
                raise RulebookError(f"{self.name}.tests.{case.get('name')}: missing or unknown source")

    # --- parameters: values by date, a key (sex), variant overrides ----------------------------------------

    def _key(self, spec: dict, values: dict):
        by = spec.get("by")
        if not by:
            return None
        value = values.get(by["measure"])
        if value is None:
            raise _NoKey
        try:
            return by["map"][value]
        except KeyError:
            raise RulebookError(f"{value!r} is not a value of {by['measure']}") from None

    def value(self, name: str, on: dt.date, key=None, overrides: dict | None = None):
        """The value of a parameter in force on `on` (for a parameter with `by`, the value of `key`)."""
        spec = self.data["parameters"][name]
        if overrides and name in overrides:
            chosen = overrides[name]
            return chosen[key] if isinstance(chosen, dict) else chosen
        entries = spec["values"][key] if "by" in spec else spec["values"]
        live = [e for e in entries if in_force(e, on)]
        if not live:
            raise NoValueInForce(f"{name} has no value in force on {on}")
        return max(live, key=lambda e: e["from"])["value"]

    def _ref(self, spec, on, values, overrides, used: dict):
        if isinstance(spec, dict) and "not" in spec:
            return not self._ref(spec["not"], on, values, overrides, used)
        if isinstance(spec, str) and spec in self.data["parameters"]:
            key = self._key(self.data["parameters"][spec], values)
            used[spec] = self.value(spec, on, key, overrides)
            return used[spec]
        return spec

    def _check(self, test: dict, x, on, values, overrides) -> tuple[bool, str, dict]:
        used: dict = {}

        def get(key, default=None):
            return self._ref(test[key], on, values, overrides, used) if key in test else default

        op = test["op"]
        if op in ("gt", "lt"):
            limit, inclusive = get("value"), get("inclusive", False)
            if op == "gt":
                return (x >= limit if inclusive else x > limit), f"{'>=' if inclusive else '>'} {limit}", used
            return (x <= limit if inclusive else x < limit), f"{'<=' if inclusive else '<'} {limit}", used
        if op in ("eq", "ne"):
            limit = get("value")
            return (x == limit) == (op == "eq"), f"{'==' if op == 'eq' else '!='} {limit}", used
        if op == "between":
            low, high, low_inc, high_inc = get("low"), get("high"), get("low_inclusive", True), get("high_inclusive", True)
            ok = (x >= low if low_inc else x > low) and (x <= high if high_inc else x < high)
            return ok, f"{'[' if low_inc else '('}{low}, {high}{']' if high_inc else ')'}", used
        raise RulebookError(f"unknown op: {op}")

    def _overrides(self, variant: dict, explicit: dict | None) -> dict:
        unknown = set(explicit or {}) - set(self.data["parameters"])
        if unknown:
            raise RulebookError(f"unknown parameter(s): {sorted(unknown)}")
        shared = {k: v for k, v in variant["overrides"].items() if k in self.data["parameters"]}  # a variant spans groups
        return {**shared, **(explicit or {})}

    # --- evaluation ------------------------------------------------------------------------------------------

    def evaluate(self, measures: dict, impairments, *, variant=DEFAULT_VARIANT, overrides: dict | None = None, on: dt.date | None = None) -> Evaluation:
        var = load_variant(variant)
        ov, on = self._overrides(var, overrides), on or var["reference_date"]
        d = self.data
        if not set(d["applies_to"]) & set(impairments):
            return Evaluation({c: Verdict(c, "not_applicable", ("NO_RELEVANT_IMPAIRMENT",)) for c in self.classes}, [], "not_applicable")
        measures = {**measures, **{f"has_{i}": i in impairments for i in d.get("impairment_measures", [])}}  # a set of impairments, tested one by one
        gated = self._run(d, d["gate"], measures, on, ov) if "gate" in d else None
        if gated:
            return gated
        if "pathways" not in d:
            return self._run(d, d["decision"], measures, on, ov, final=True)
        runs = [self._run(p, p["decision"], measures, on, ov, final=True) for p in d["pathways"].values() if set(p["applies_to"]) & set(impairments)]
        verdicts = dict(runs[0].verdicts)  # alternative pathways: per class, the best status (a tie adds the reasons and keeps the first missing)
        for run in runs[1:]:
            for cls, new in run.verdicts.items():
                old = verdicts[cls]
                if STATUSES.index(new.status) < STATUSES.index(old.status):
                    verdicts[cls] = new
                elif new.status == old.status:
                    verdicts[cls] = Verdict(cls, old.status, old.reasons + tuple(r for r in new.reasons if r not in old.reasons), old.missing)
        return Evaluation(verdicts, [s for r in runs for s in r.trace], "+".join(r.decision for r in runs))

    def _run(self, spec: dict, rules: list, measures: dict, on: dt.date, ov: dict, final: bool = False) -> Evaluation | None:
        """The first rule of `rules` that holds, over the measures, derived measures, criteria and flags of `spec` (the group
        file, or one of its pathways). Without `final`, no rule holding is not an error."""
        values = dict(measures)
        for name, how in spec.get("derived", {}).items():
            kind = next(k for k in DERIVE if k in how)
            parts = [values.get(m) for m in how[kind]]
            values[name] = None if any(p is None for p in parts) else DERIVE[kind](parts)
        missing = tuple(m for m in spec.get("measures", self.measures) if values.get(m) is None)
        trace: list[Step] = []
        hit: dict[str, bool] = {}
        owner = {n: cls for cls, rule in spec.get("class_rules", {}).items() for n in (rule.get("all_of") or rule["any_of"])}

        def run(name: str, test: dict) -> bool:
            x = values.get(test["measure"])
            args = (name, owner.get(name), test["measure"], x)
            reason, source = test.get("reason", ""), test["source"]
            if not in_force(test.get("valid"), on):
                trace.append(Step(*args, "", "skipped", reason, source))
                return False
            try:
                ok, text, used = self._check(test["test"], x, on, values, ov) if x is not None else (None, "", {})
            except _NoKey:
                ok, text, used = None, "", {}
            if ok is None:
                trace.append(Step(*args, "", "not_assessed", reason, source))
                return False
            superseded = test.get("unless") if hit.get(test.get("unless")) else None
            trace.append(Step(*args, text, "met" if ok else "not_met", reason, source, superseded, used))
            return ok and superseded is None

        for name, test in spec.get("criteria", {}).items():
            hit[name] = run(name, test)
        flags = {name: run(name, test) for name, test in spec.get("flags", {}).items()}
        evidence = {}
        for cls, rule in spec.get("class_rules", {}).items():
            kind = "all_of" if "all_of" in rule else "any_of"
            results = [hit[n] for n in rule[kind]]
            evidence[cls] = all(results) if kind == "all_of" else any(results)
            trace.append(Step(f"class_{cls}", cls, "", None, kind, "met" if evidence[cls] else "not_met", "", {}))

        for rule in rules:
            when = rule.get("when", {})
            wanted = when.get("flag", [])
            holds = [
                all(values.get(m) is None for m in when["all_missing"]) if "all_missing" in when else True,
                any(values.get(m) is None for m in when["any_missing"]) if "any_missing" in when else True,
                any(evidence.values()) if when.get("any_class") else True,
                all(flags.get(f, False) for f in ([wanted] if isinstance(wanted, str) else wanted)),
                all(values.get(m) == v for m, v in when["equals"].items()) if "equals" in when else True,
            ]
            if all(holds):
                trace.append(Step(f"decision:{rule['id']}", None, "", None, "", "met", rule.get("reason", ""), {}))
                reported = tuple(m for m in rule["report_missing"] if values.get(m) is None) if "report_missing" in rule else missing
                reported = tuple(rule["report_always"]) if "report_always" in rule else reported
                return Evaluation(self._verdicts(spec, rule, evidence, hit, flags, reported), trace, rule["id"])
        if final:
            raise RulebookError(f"{self.name}: no decision rule applies")
        return None

    def _verdicts(self, spec: dict, rule: dict, evidence: dict, hit: dict, flags: dict, missing: tuple[str, ...]) -> dict[int, Verdict]:
        result, default_reason = rule["result"], rule.get("reason", "")
        group = self.data["class_groups"][rule["scope"]] if "scope" in rule else None
        inside = group["classes"] if group else self.classes
        status: dict[int, str] = {}
        reasons: dict[int, tuple[str, ...]] = {}
        if "all" in result:
            status = dict.fromkeys(inside, result["all"])
        else:
            primary = None
            if "meets" in result:
                primary = min(c for c, ok in evidence.items() if ok)  # pick: most_impaired is the lowest class number
                rule_of = spec["class_rules"][primary]
                status[primary] = "meets"
                reasons[primary] = tuple(dict.fromkeys(spec["criteria"][n].get("reason", "") for n in (rule_of.get("all_of") or rule_of["any_of"]) if hit[n]))
            for cls, new in result.get("classes", {}).items():
                status[cls] = new
            for item in result.get("borderline", []):
                cls, cond, why = (item["class"], item.get("if"), item.get("reason")) if isinstance(item, dict) else (item, None, None)
                if cond and not (flags.get(cond["flag"]) and ("primary_above" not in cond or (primary is not None and primary > cond["primary_above"]))):
                    continue
                status[cls], reasons[cls] = "borderline", (why or default_reason,)
            for cls in inside:
                status.setdefault(cls, result.get("rest", "not_met"))
        return {
            c: Verdict(c, status[c], reasons.get(c, (default_reason,) if default_reason else ()), missing) if c in inside else Verdict(c, "not_met", (group["outside_reason"],))
            for c in self.classes
        }

    # --- tests as data ---------------------------------------------------------------------------------------

    def run_tests(self, **options) -> list[str]:
        failures = []
        for case in self.data.get("tests", []):
            given = dict(case["input"])
            impairments = set(given.pop("impairments", self.data["applies_to"]))
            evaluation = self.evaluate(given, impairments, **options)
            for class_id, expected in case["expect"].items():
                got = evaluation.verdicts[class_id].status
                if got != expected:
                    failures.append(f"{case['name']}: class {class_id} expected {expected}, got {got}")
        return failures
