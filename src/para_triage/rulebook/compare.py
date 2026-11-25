"""Side-by-side regression against the current engine, and the diff between variants (R-6, R-7).

Tools, not part of the interpreter: they build the profiles (the study-mode sample, a sweep generated from the
rule book's own parameters, hidden measures, other impairments), run `RuleEngine.evaluate` and the interpreter on
each, and compare the status and the missing fields per class.
"""
from __future__ import annotations

import datetime as dt
import itertools
import random
import re
import time
from collections import Counter
from dataclasses import dataclass, field

from ..data.generator import sample_true_profiles
from ..rules import Impairment, Posture, Profile, RuleEngine, Sex
from ..rules.schema import ArmFunction, CpDistribution, LegFunction, Propulsion, Severity, TrunkFunction
from .engine import GROUPS, ShadowEngine, measures_of, onset_flag
from .interpreter import DEFAULT_VARIANT, Rulebook, load_variant

OFFSETS = (-0.01, 0.0, 0.01, 0.05)
PER_LABEL = {"visual": 40, "short_stature": 70}  # about 200 profiles per seed
SAMPLERS_OF = {"neuro": ["neuro_seated", "neuro_standing"]}  # the study-mode samplers of a group that has one for each posture
OTHER_IMPAIRMENTS = (("intellectual",), ("limb_deficiency",), ())
FLOAT_STEP = 0.1
SUM_LINE_POINTS = 60  # pairs per limit of a derived sum, in steps of FLOAT_STEP
GAP_STEP = 0.01

Row = dict[int, tuple[str, tuple[str, ...]]]
POSTURE_GROUPS = ("neuro", "limb_standing", "wheelchair", "limb_prosthesis", "frame_runner")  # the groups whose books read the posture


@dataclass(frozen=True)
class Case:
    id: str
    source: str
    measures: dict
    impairments: tuple[str, ...]


@dataclass
class Report:
    group: str
    total: Counter = field(default_factory=Counter)
    divergences: Counter = field(default_factory=Counter)
    examples: list = field(default_factory=list)
    seconds: Counter = field(default_factory=Counter)

    @property
    def clean(self) -> bool:
        return sum(self.divergences.values()) == 0


# --- profiles and verdicts ------------------------------------------------------------------------------------


# The measures of a case are plain values; these fields are enums in the profile (the engine compares some of them by identity).
ENUMS = {"sex": Sex, "neuro_severity": Severity, "cp_distribution": CpDistribution, "chair_propulsion": Propulsion, "arm_function": ArmFunction, "trunk_function": TrunkFunction, "leg_function": LegFunction}
ENGINE_NAME = {"onset_age": "onset_before_22"}  # the field that the engine lists as missing


def profile_of(case: Case, book: Rulebook | None = None, reads_posture: bool | None = None) -> Profile:
    """The profile of a case. A group that reads the posture gets it from the case (missing: unknown); the others, standing."""
    fields = {name: (ENUMS[name](value) if name in ENUMS else value) for name, value in case.measures.items() if name not in ("posture", "onset_age")}
    if "onset_age" in case.measures:
        fields["onset_before_22"] = onset_flag(case.measures["onset_age"])
    reads = reads_posture if reads_posture is not None else bool(book and "posture" in book.measures)
    posture = case.measures.get("posture", None if reads else Posture.STANDING.value)
    return Profile(impairments=frozenset(Impairment(i) for i in case.impairments), posture=Posture(posture) if posture else None, **fields)


def engine_row(engine: RuleEngine, profile: Profile, classes: list[int]) -> Row:
    verdicts = engine.evaluate(profile).verdicts
    return {c: (verdicts[c].status.value, tuple(verdicts[c].missing)) for c in classes}


def book_row(book: Rulebook, case: Case, **options) -> Row:
    evaluation = book.evaluate(case.measures, set(case.impairments), **options)
    return {c: (v.status, tuple(ENGINE_NAME.get(m, m) for m in v.missing)) for c, v in evaluation.verdicts.items()}


# --- cases ------------------------------------------------------------------------------------------------------


def sample_cases(book: Rulebook, seeds=range(5), per_label: int | None = None) -> list[Case]:
    """The study-mode sample of the group, complete, with each measure hidden, and with all of them hidden."""
    cases = []
    for seed in seeds:
        drawn = sample_true_profiles(per_label or PER_LABEL.get(book.name, 40), SAMPLERS_OF.get(book.name, [book.name]), seed=seed)
        for index, profile in enumerate(drawn.profiles):
            base, kinds = measures_of(profile, book.measures), tuple(sorted(i.value for i in profile.impairments))
            cases.append(Case(f"k2-{seed}-{index}", "k2", base, kinds))
            for hidden in book.measures:
                cases.append(Case(f"k2-{seed}-{index}-no-{hidden}", f"k2-no-{hidden}", {k: v for k, v in base.items() if k != hidden}, kinds))
            cases.append(Case(f"k2-{seed}-{index}-nothing", "k2-nothing", {}, kinds))
    return cases


def _thresholds(book: Rulebook, on: dt.date, overrides: dict | None) -> dict[str, dict]:
    """measure -> {key -> [limits]} from the parameters the criteria and flags use (key: the `by` key, or None)."""
    found: dict[str, dict] = {}
    specs = [book.data, *book.data.get("pathways", {}).values()]
    for spec in [i for s in specs for kind in ("criteria", "flags") for i in s.get(kind, {}).values()]:
        for ref in (spec["test"].get(k) for k in ("value", "low", "high")):
            if isinstance(ref, str) and ref in book.data["parameters"]:
                param = book.data["parameters"][ref]
                for key in (param["values"] if "by" in param else [None]):
                    found.setdefault(spec["measure"], {}).setdefault(key, set()).add(book.value(ref, on, key, overrides))
    return found


def sweep_cases(book: Rulebook, on: dt.date | None = None, overrides: dict | None = None) -> list[Case]:
    """A sweep around every limit of the rule book (limit minus 0.01, equal, plus 0.01 and 0.05), the whole interior of
    gaps between close limits, missing measures, and, for sums, pairs that land on each limit (including float steps)."""
    on = on or load_variant(DEFAULT_VARIANT)["reference_date"]
    limits = _thresholds(book, on, overrides)
    by_params = [p["by"] for p in book.data["parameters"].values() if "by" in p]
    categories = {b["measure"]: b for b in by_params}
    derived = book.data.get("derived", {})
    values: dict[str, list] = {}
    for measure in book.measures:
        if measure in categories:
            values[measure] = [*categories[measure]["map"], None]
            continue
        flat = sorted({x for per_key in limits.get(measure, {}).values() for x in per_key})
        grid = {round(x + o, 2) for x in flat for o in OFFSETS}
        for low, high in zip(flat, flat[1:]):
            if 0 < high - low <= 0.2:
                grid |= {round(low + GAP_STEP * k, 2) for k in range(round((high - low) / GAP_STEP) + 1)}
        if flat:
            grid |= {round(flat[0] - 1, 2), round(flat[-1] + 1, 2), 0.0, round((flat[0] + flat[-1]) / 2, 2)}
        values[measure] = [*sorted(grid), None]

    grids = [[(m, v) for v in values[m]] for m in book.measures]
    combos = [dict(c) for c in __import__("itertools").product(*grids)]
    for name, spec in derived.items():  # pairs that land on each limit of a derived sum
        first, second = spec["sum"]
        for key, sums in limits.get(name, {}).items():
            sexes = [raw for raw, k in categories[next(iter(categories))]["map"].items() if k == key] if categories else [None]
            for total in sums:
                for step in range(round(total * 0.6 / FLOAT_STEP), round(total * 0.6 / FLOAT_STEP) + SUM_LINE_POINTS):
                    a = round(step * FLOAT_STEP, 1)
                    for offset in OFFSETS:
                        combo = {first: a, second: round(total + offset - a, 2)}
                        combos += [{**combo, next(iter(categories)): s} if categories else combo for s in sexes]
    cases = [Case(f"sweep-{i}", "sweep", {k: v for k, v in c.items() if v is not None}, tuple(book.data["applies_to"])) for i, c in enumerate(combos)]
    cases += [Case(f"other-{i}-{j}", "other", m, kinds) for i, kinds in enumerate(OTHER_IMPAIRMENTS) for j, m in enumerate([{}, {k: 1.0 for k in book.measures if k not in categories}])]
    return cases


def _values(book: Rulebook, name: str, limits: dict) -> list:
    """The values of a measure: its `domains` entry, or a grid around the limits the criteria and flags compare it with; and missing."""
    if name in book.data["domains"]:
        return [*book.data["domains"][name], None]
    nums = sorted({x for per_key in limits.get(name, {}).values() for x in per_key if isinstance(x, (int, float)) and not isinstance(x, bool)})
    if not nums:
        return [None]
    grid = {round(x + o, 2) for x in nums for o in OFFSETS} | {round(nums[0] - 1, 2), round(nums[-1] + 1, 2), 0.0}
    return [*sorted(grid), None]


def _product(names: list[str], columns: list[list], kinds: list[tuple], source: str, limit: int | None) -> list[Case]:
    """Every combination of the columns for each set of impairments; with a `limit`, a pseudo-random subset (fixed seed) of about `limit` remains."""
    total = 1
    for column in columns:
        total *= len(column)
    keep = 1.0 if limit is None else min(1.0, limit / total)  # a fixed seed, not every n-th: that would visit only some values of the last measure
    chosen = random.Random(0)
    return [
        Case(f"{source}-{i}-{n}", source, {m: v for m, v in zip(names, combo) if v is not None}, impairments)
        for i, impairments in enumerate(kinds)
        for n, combo in enumerate(c for c in itertools.product(*columns) if keep == 1.0 or chosen.random() < keep)
    ]


def domain_cases(book: Rulebook, every_impairment_set: bool = False) -> list[Case]:
    """Every combination of the values each discrete measure can take (`domains` of the group file) and the missing
    value, with the impairments that make the group applicable; `every_impairment_set` adds the group with another
    impairment next to it, another impairment alone and none, and, to a group with pathways, the whole products
    (otherwise about 5 thousand profiles of each). For a group with pathways: each pathway with the measures of the gate,
    and both at once (`fusion` in the group file lists the values of the measures, as written, when two pathways run)."""
    data, limits = book.data, _thresholds(book, load_variant(DEFAULT_VARIANT)["reference_date"], None)
    limit = None if every_impairment_set else 5000
    others = [(*data["applies_to"], "visual"), ("visual",), ()] if every_impairment_set else []
    if "pathways" not in data:
        names = list(book.measures)  # a measure that is not in `domains` is a number compared with a limit: a grid around it
        columns = [_values(book, m, limits) for m in names]
        groups = [tuple(s) for s in data.get("impairment_sets", [data["applies_to"]])]  # a group may depend on which impairments, not just on any
        rest = [tuple(o) for o in others]
        return _product(names, columns, groups, "domain", limit) + _product(names, columns, rest, "domain-other", limit)
    paths = data["pathways"]
    gate = [m for m in book.measures if not any(m in p["measures"] for p in paths.values())]
    cases = []
    for name, path in paths.items():
        names = [*gate, *path["measures"]]
        kinds = [(path["applies_to"][0],), *([tuple(path["applies_to"])] if every_impairment_set else [])]
        cases += _product(names, [_values(book, m, limits) for m in names], kinds, f"domain-{name}", limit)
    names = [*gate, *(m for p in paths.values() for m in p["measures"])]
    columns = [data["fusion"][m] if m in data.get("fusion", {}) else _values(book, m, limits) for m in names]
    both = [tuple(p["applies_to"][0] for p in paths.values())] + ([tuple(i for p in paths.values() for i in p["applies_to"])] if every_impairment_set else [])
    first = next(iter(paths.values()))["measures"]
    cases += _product(names, columns, both, "domain-fusion", limit)
    cases += _product([*gate, *first], [_values(book, m, limits) for m in [*gate, *first]], [tuple(o) for o in others], "domain-other", 5000)
    return cases


# --- regression and diff --------------------------------------------------------------------------------------


def regress(book: Rulebook, cases: list[Case], engine: RuleEngine | None = None, **options) -> Report:
    engine, report = engine or RuleEngine(), Report(book.name)
    for case in cases:
        report.total[case.source] += 1
        expected, got = engine_row(engine, profile_of(case, book), book.classes), book_row(book, case, **options)
        if expected != got:
            report.divergences[case.source] += 1
            if len(report.examples) < 5:
                report.examples.append((case, expected, got))
    return report


def format_report(report: Report) -> str:
    lines = [f"{report.group}: {sum(report.total.values())} profiles, {sum(report.divergences.values())} divergences from the current engine"]
    for source in sorted(report.total):
        lines.append(f"  {source:22s} {report.divergences[source]:6d} of {report.total[source]:6d}")
    for case, expected, got in report.examples:
        lines.append(f"  e.g. {case.id} {case.measures} {case.impairments}\n       engine {expected}\n       book   {got}")
    return "\n".join(lines)


@dataclass
class Diff:
    group: str
    total: int
    changed: int
    transitions: Counter
    examples: list


def diff_variants(book: Rulebook, cases: list[Case], a=DEFAULT_VARIANT, b=DEFAULT_VARIANT, overrides_a=None, overrides_b=None) -> Diff:
    """How many profiles change class status between two variants (or two sets of overrides), and how."""
    changed, transitions, examples = 0, Counter(), []
    for case in cases:
        before = book_row(book, case, variant=a, overrides=overrides_a)
        after = book_row(book, case, variant=b, overrides=overrides_b)
        if before != after:
            changed += 1
            for cls in before:
                if before[cls] != after[cls]:
                    transitions[(cls, before[cls][0], after[cls][0])] += 1
            if len(examples) < 3:
                examples.append((case.measures, {c: before[c][0] for c in before}, {c: after[c][0] for c in after}))
    return Diff(book.name, len(cases), changed, transitions, examples)


def format_diff(diff: Diff) -> str:
    lines = [f"{diff.group}: {diff.changed} of {diff.total} profiles change"]
    for (cls, was, now), count in sorted(diff.transitions.items()):
        lines.append(f"  class {cls}: {was} -> {now}: {count}")
    for measures, before, after in diff.examples:
        lines.append(f"  e.g. {measures}: {before} -> {after}")
    return "\n".join(lines)


# --- the whole engine, in shadow (step 6) ------------------------------------------------------------------------------
# The same profiles go through `RuleEngine.evaluate` and `ShadowEngine.evaluate`: the 33 classes at once, with the order of
# the classes, `meets`, `primary_class` and `candidates`. The statuses are compared by value (`Status` is a str enum, the
# shadow engine's are plain strings), and the missing field `onset_age` is called by the name the engine knows.

MIXED_PER_SUBSET = 10  # profiles per combination of groups (247 combinations of two to eight groups)
POOL = 20000  # cases of each group kept to build the mixed profiles


def group_items(exhaustive: bool = False, mixed_per_subset: int | None = None):
    """(source, case, profile) of everything the per-group regression generates, then of profiles with the impairments of
    several groups at once, which the per-group regression does not exercise: each is drawn from the cases of the groups
    of the combination, and their measures and impairments are joined."""
    rng = random.Random(0)
    pools: dict[str, list[Case]] = {}
    seeds, per_label = (range(20), 400) if exhaustive else (range(5), None)
    for name in GROUPS:
        book = Rulebook.load(name)
        cases = sample_cases(book, seeds, per_label) + (domain_cases(book, exhaustive) if "domains" in book.data else sweep_cases(book))
        for case in cases:
            yield f"{name}:{case.source}", case, profile_of(case, book)
        pools[name] = rng.sample(cases, min(len(cases), POOL))
    per_subset = mixed_per_subset or (200 if exhaustive else MIXED_PER_SUBSET)
    for size in range(2, len(GROUPS) + 1):
        for subset in itertools.combinations(GROUPS, size):
            reads_posture = any(g in POSTURE_GROUPS for g in subset)
            for i in range(per_subset):
                parts = [rng.choice(pools[g]) for g in subset]
                measures = {k: v for part in parts for k, v in part.measures.items()}
                case = Case(f"mixed-{'+'.join(subset)}-{i}", "mixed", measures, tuple(sorted({x for part in parts for x in part.impairments})))
                yield f"mixed-{size}", case, profile_of(case, reads_posture=reads_posture)


def _row(verdict) -> tuple:
    return (getattr(verdict.status, "value", verdict.status), tuple(ENGINE_NAME.get(m, m) for m in verdict.missing))


def engine_diff(expected, got) -> dict | None:
    """What differs between an `EligibilityResult` and a `ShadowResult`, or None."""
    diff: dict = {}
    if list(expected.verdicts) != list(got.verdicts):
        diff["classes"] = (list(expected.verdicts), list(got.verdicts))
    for cid, verdict in expected.verdicts.items():
        other = got.verdicts.get(cid)
        if other is None or _row(verdict) != _row(other):
            diff[cid] = (_row(verdict), None if other is None else _row(other))
    for name in ("meets", "primary_class", "candidates"):
        if getattr(expected, name) != getattr(got, name):
            diff[name] = (getattr(expected, name), getattr(got, name))
    return diff or None


def regress_engine(items, engine: RuleEngine | None = None, shadow: ShadowEngine | None = None) -> Report:
    engine, shadow, report = engine or RuleEngine(), shadow or ShadowEngine(), Report("engine")
    for source, case, profile in items:
        report.total[source.split(":")[0] if source.startswith("mixed") else source] += 1
        start = time.perf_counter()
        expected = engine.evaluate(profile)
        middle = time.perf_counter()
        got = shadow.evaluate(profile)
        report.seconds["engine"] += middle - start
        report.seconds["shadow"] += time.perf_counter() - middle
        if diff := engine_diff(expected, got):
            report.divergences[source] += 1
            if len(report.examples) < 5:
                report.examples.append((case, {k: v[0] for k, v in diff.items()}, {k: v[1] for k, v in diff.items()}))
    return report


def reasons_table(items, engine: RuleEngine | None = None, shadow: ShadowEngine | None = None) -> dict:
    """Over the same profiles: each sentence of the engine against the code of the book in the same position of the verdict."""
    engine, shadow = engine or RuleEngine(), shadow or ShadowEngine()
    pairs: Counter = Counter()
    misaligned: Counter = Counter()
    for _, _, profile in items:
        expected, got = engine.evaluate(profile).verdicts, shadow.evaluate(profile).verdicts
        for cid, verdict in expected.items():
            sentences, codes = tuple(verdict.reasons), tuple(got[cid].reasons)
            if len(sentences) != len(codes):
                misaligned[(len(sentences), len(codes))] += 1
                continue
            for sentence, code in zip(sentences, codes):
                pairs[(sentence, code)] += 1
    return {"pairs": pairs, "misaligned": misaligned}


NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


def reasons_summary(table: dict) -> dict:
    """Counts for the decision about the reasons: templates (the numbers of a sentence replaced by #), codes, and how they pair."""
    by_template: dict[str, set] = {}
    by_code: dict[str, set] = {}
    raw = {sentence for sentence, _ in table["pairs"]}
    for sentence, code in table["pairs"]:
        template = NUMBER.sub("#", sentence)
        by_template.setdefault(template, set()).add(code)
        by_code.setdefault(code, set()).add(template)
    return {
        "sentences": len(raw), "templates": len(by_template), "codes": len(by_code),
        "with_values": sum(1 for t in by_template if "#" in t),
        "one_to_one": sum(1 for t, codes in by_template.items() if len(codes) == 1 and len(by_code[next(iter(codes))]) == 1),
        "templates_with_several_codes": sum(1 for codes in by_template.values() if len(codes) > 1),
        "codes_with_several_templates": sum(1 for templates in by_code.values() if len(templates) > 1),
        "misaligned_verdicts": sum(table["misaligned"].values()),
        "verdicts": sum(table["pairs"].values()) + sum(table["misaligned"].values()),
    }


def format_engine_report(report: Report) -> str:
    lines = [f"engine: {sum(report.total.values())} profiles, {sum(report.divergences.values())} divergences from the current engine (33 classes at once)"]
    for source in sorted(report.total):
        lines.append(f"  {source:34s} {report.divergences[source]:6d} of {report.total[source]:7d}")
    lines.append(f"  time: current engine {report.seconds['engine']:.1f} s, shadow engine {report.seconds['shadow']:.1f} s")
    for case, expected, got in report.examples:
        lines.append(f"  e.g. {case.id} {case.measures} {case.impairments}\n       engine {expected}\n       shadow {got}")
    return "\n".join(lines)


def timing(repeat: int = 200) -> dict[str, tuple[float, float]]:
    """Microseconds per profile of the current engine and of the shadow engine (books loaded once), for a typical complete
    profile of each group: the first complete profile of the study-mode sample."""
    engine, shadow, out = RuleEngine(), ShadowEngine(), {}
    for name in GROUPS:
        book = shadow.books[name]
        case = next(c for c in sample_cases(book, range(1)) if c.source == "k2")
        profile = profile_of(case, book)
        for label, run in (("engine", engine.evaluate), ("shadow", shadow.evaluate)):
            start = time.perf_counter()
            for _ in range(repeat):
                run(profile)
            out.setdefault(name, []).append((time.perf_counter() - start) / repeat * 1e6)
    return {name: tuple(values) for name, values in out.items()}
