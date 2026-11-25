"""Builds the content of the class guide (K18) from the catalog and the rule engine. Read-only.

Prose comes from texts_pt.py and has no numbers. Every number on a page is generated here from the
catalog `criteria` or from the engine, and every page carries `claims`: profiles and the answer the
page implies, which tests run through the engine so a page cannot drift from the rules.
"""
from __future__ import annotations

import itertools
import re
import unicodedata
from typing import Any

from ..education import cases as k2_cases
from ..education import texts_pt as k2_texts
from ..education.trace import build_trace
from ..provenance_info import rules_version
from ..rules import Impairment, Posture, Profile, Sex
from ..rules.catalog import Catalog, load_catalog
from . import scope
from . import texts_pt as T

Segments = list[dict[str, Any]]

PLACEHOLDER = re.compile(r"\$\{([a-z0-9_]+)\}")
TERM = re.compile(r"\{\{([a-z0-9-]+)\|([^}]+)\}\}")
LIMB_LEVEL_FIELDS = ("lower_left", "lower_right", "upper_left", "upper_right")
POSTURES = {"limb_standing": Posture.STANDING, "limb_prosthesis": Posture.PROSTHESIS}


# --- text helpers ----------------------------------------------------------------------------------------


def fmt(value: float, digits: int) -> str:
    return k2_texts.fmt(float(value), digits)


def plain(text: str) -> str:
    """Text without glossary markup."""
    return TERM.sub(lambda m: m.group(2), text)


def fill(text: str, values: dict[str, Any]) -> str:
    def replace(match: re.Match) -> str:
        return str(values[match.group(1)])

    return PLACEHOLDER.sub(replace, text)


def rich(text: str, values: dict[str, Any] | None = None) -> Segments:
    """Substitutes `${name}` and splits `{{term|text}}` into segments (text or term link)."""
    text = fill(text, values or {})
    segments: Segments = []
    position = 0
    for match in TERM.finditer(text):
        if match.start() > position:
            segments.append({"t": text[position : match.start()]})
        segments.append({"t": match.group(2), "term": match.group(1)})
        position = match.end()
    if position < len(text):
        segments.append({"t": text[position:]})
    return segments


def para(text: str, values: dict[str, Any] | None = None) -> dict:
    return {"kind": "p", "text": rich(text, values)}


def bullets(items: list[str] | tuple[str, ...], values: dict[str, Any] | None = None) -> dict:
    return {"kind": "ul", "items": [rich(item, values) for item in items]}


def terms_in(node: Any) -> list[str]:
    """Glossary term ids used anywhere in a structure, in order of first appearance."""
    found: list[str] = []

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            if "term" in value and value["term"] not in found:
                found.append(value["term"])
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(node)
    return found


def slug_key(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


# --- review status -----------------------------------------------------------------------------------------


def review_status(path: str, review: dict) -> str:
    reviewed = bool(review.get("texts_reviewed")) and path in set(review.get("reviewed_pages", []))
    return scope.REVIEW_REVIEWED if reviewed else scope.REVIEW_DRAFT


# --- numbers from the catalog -----------------------------------------------------------------------------


def criteria(catalog: Catalog) -> dict[int, dict]:
    return {cid: spec.criteria for cid, spec in catalog.classes.items()}


def visual_values(crit: dict[int, dict]) -> dict[str, str]:
    c11, c12, c13 = crit[11], crit[12], crit[13]
    return {
        "c11": "11",
        "c12": "12",
        "c13": "13",
        "logmar_gt_11": fmt(c11["logmar_gt"], 2),
        "logmar_min_12": fmt(c12["logmar_min"], 2),
        "logmar_max_12": fmt(c12["logmar_max"], 2),
        "field_lt_12": fmt(c12["field_lt_deg"], 0),
        "logmar_min_13": fmt(c13["logmar_min"], 2),
        "logmar_max_13": fmt(c13["logmar_max"], 2),
        "field_lt_13": fmt(c13["field_lt_deg"], 0),
    }


# --- limb patterns from the engine ------------------------------------------------------------------------


def limb_patterns(group: str) -> dict[str, list[tuple[int, int, int, int]]]:
    """Answer id -> canonical level patterns (lower hi/lo, upper hi/lo), enumerating the 144 combinations on the engine."""
    out: dict[str, set[tuple[int, int, int, int]]] = {}
    for lower_left, lower_right, upper_left, upper_right in itertools.product(range(4), range(4), range(3), range(3)):
        profile = Profile(
            impairments=frozenset({Impairment.LIMB_DEFICIENCY}),
            posture=POSTURES[group],
            lower_left=lower_left,
            lower_right=lower_right,
            upper_left=upper_left,
            upper_right=upper_right,
        )
        answer = k2_cases.engine_answer(group, profile)
        lower = sorted((lower_left, lower_right), reverse=True)
        upper = sorted((upper_left, upper_right), reverse=True)
        out.setdefault(answer or "none", set()).add((lower[0], lower[1], upper[0], upper[1]))
    return {answer: sorted(patterns) for answer, patterns in out.items()}


def capital(text: str) -> str:
    return text[:1].upper() + text[1:]


def describe_pair(kind: str, hi: int, lo: int) -> str:
    levels = T.LOWER_LEVELS if kind == "lower" else T.UPPER_LEVELS
    if hi == 0:
        return T.LIMB_NONE[kind]
    if lo == 0:
        return T.LIMB_ONE[kind].format(hi=levels[hi])
    if hi == lo:
        return T.LIMB_BOTH_EQUAL[kind].format(hi=levels[hi])
    return T.LIMB_BOTH_DIFFERENT[kind].format(hi=levels[hi], lo=levels[lo])


def describe_pattern(group: str, pattern: tuple[int, int, int, int]) -> str:
    lower = describe_pair("lower", pattern[0], pattern[1])
    if group == "limb_prosthesis":
        return capital(T.PATTERN_SENTENCE_LOWER_ONLY.format(lower=lower))
    return capital(T.PATTERN_SENTENCE.format(lower=lower, upper=describe_pair("upper", pattern[2], pattern[3])))


def arrangement(pattern: tuple[int, int, int, int]) -> dict[str, int]:
    """One drawing of a canonical pattern: the more affected limb on the left."""
    return {"lower_left": pattern[0], "lower_right": pattern[1], "upper_left": pattern[2], "upper_right": pattern[3]}


# --- figures ----------------------------------------------------------------------------------------------


def figure_logmar(crit: dict[int, dict]) -> dict:
    c11, c12, c13 = crit[11], crit[12], crit[13]
    axis_max = 3.0
    values = {
        "axis_min": fmt(0, 0),
        "axis_max": fmt(axis_max, 2),
        "low13": fmt(c13["logmar_min"], 2),
        "high13": fmt(c13["logmar_max"], 2),
        "low12": fmt(c12["logmar_min"], 2),
        "high12": fmt(c12["logmar_max"], 2),
        "gt11": fmt(c11["logmar_gt"], 2),
        "c11": "11",
        "c12": "12",
        "c13": "13",
    }
    bands = [
        {"label": "Classe 13", "from": c13["logmar_min"], "to": c13["logmar_max"], "pattern": "dots"},
        {"label": "Sem classe no livreto", "from": c13["logmar_max"], "to": c12["logmar_min"], "pattern": "cross"},
        {"label": "Classe 12", "from": c12["logmar_min"], "to": c12["logmar_max"], "pattern": "diagonal"},
        {"label": "Classe 11", "from": c11["logmar_gt"], "to": axis_max, "pattern": "vertical"},
    ]
    numbers = sorted({values[k] for k in ("axis_min", "axis_max", "low13", "high13", "low12", "high12", "gt11")})
    return {
        "id": "fig-logmar",
        "kind": "logmar_scale",
        "title": T.FIG_LOGMAR_TITLE,
        "caption": rich(T.FIG_LOGMAR_CAPTION),
        "long": plain(fill(T.FIG_LOGMAR_LONG, values)),
        "numbers": numbers,
        "data": {"axis": {"min": 0, "max": axis_max, "ticks": [0, 1, 2, 3]}, "bands": bands},
    }


def figure_field(crit: dict[int, dict]) -> dict:
    f12, f13 = crit[12]["field_lt_deg"], crit[13]["field_lt_deg"]
    values = {"field12": fmt(f12, 0), "field13": fmt(f13, 0), "c12": "12", "c13": "13"}
    return {
        "id": "fig-field",
        "kind": "field_circles",
        "title": T.FIG_FIELD_TITLE,
        "caption": rich(T.FIG_FIELD_CAPTION),
        "long": plain(fill(T.FIG_FIELD_LONG, values)),
        "numbers": sorted({values["field12"], values["field13"]}),
        "data": {"limits": [f12, f13], "labels": ["Classe 12", "Classe 13"]},
    }


def figure_stature() -> dict:
    return {
        "id": "fig-stature",
        "kind": "stature_measures",
        "title": T.FIG_STATURE_TITLE,
        "caption": rich(T.FIG_STATURE_CAPTION),
        "long": plain(T.FIG_STATURE_LONG),
        "numbers": [],
        "data": {"labels": {"height": "Estatura", "arm": "Braço mais longo"}},
    }


def figure_levels(kind: str) -> dict:
    lower = kind == "lower"
    return {
        "id": f"fig-levels-{kind}",
        "kind": "levels_lower" if lower else "levels_upper",
        "title": T.FIG_LEVELS_LOWER_TITLE if lower else T.FIG_LEVELS_UPPER_TITLE,
        "caption": rich(T.FIG_LEVELS_LOWER_CAPTION if lower else T.FIG_LEVELS_UPPER_CAPTION),
        "long": T.FIG_LEVELS_LOWER_LONG if lower else T.FIG_LEVELS_UPPER_LONG,
        "numbers": [],
        "data": {
            "marks": [
                {"level": level, "label": T.FIG_LEVEL_SHORT[(kind, level)]} for level in ((1, 2, 3) if lower else (1, 2))
            ]
        },
    }


def figure_pattern(group: str, class_id: int, index: int, pattern: tuple[int, int, int, int]) -> dict:
    levels = arrangement(pattern)
    values = {"class_id": str(class_id)}
    parts = [T.FIG_PATTERN_LONG_START]
    labels: dict[str, str | None] = {}
    for limb in LIMB_LEVEL_FIELDS:
        if group == "limb_prosthesis" and limb.startswith("upper"):
            continue
        level = levels[limb]
        kind = "lower" if limb.startswith("lower") else "upper"
        names = T.LOWER_LEVELS if kind == "lower" else T.UPPER_LEVELS
        if level == 0:
            state = T.FIG_PATTERN_STATE_NONE
            labels[limb] = None
        else:
            state = T.FIG_PATTERN_STATE_CUT.format(level=plain(names[level]))
            labels[limb] = T.FIG_LEVEL_SHORT[(kind, level)]
        parts.append(T.FIG_PATTERN_LIMB.format(limb=T.FIG_PATTERN_LIMB_NAMES[limb], state=state))
    long = " ".join(parts)
    prosthesis = group == "limb_prosthesis"
    if prosthesis:
        long += T.FIG_PATTERN_PROSTHESIS
    return {
        "id": f"fig-pattern-{class_id}-{index + 1}",
        "kind": "pattern",
        "title": fill(T.FIG_PATTERN_TITLE, values),
        "caption": rich(T.FIG_PATTERN_CAPTION, values),
        "long": long,
        "numbers": [],
        "data": {"levels": levels, "labels": labels, "prosthesis": prosthesis, "show_upper": not prosthesis},
    }


# --- claims (checked against the engine by tests) ----------------------------------------------------------


def visual_claims(crit: dict[int, dict]) -> list[dict]:
    c11, c12, c13 = crit[11], crit[12], crit[13]
    wide = 120.0  # a field far above every limit, so only the acuity decides

    def claim(note: str, acuity: float | None, field: float | None, expected: str) -> dict:
        return {
            "group": "visual",
            "note": note,
            "fields": {"logmar_best_eye": acuity, "visual_field_deg": field},
            "expected": expected,
        }

    mid12 = round((c12["logmar_min"] + c12["logmar_max"]) / 2, 2)
    mid13 = round((c13["logmar_min"] + c13["logmar_max"]) / 2, 2)
    gap_mid = round((c13["logmar_max"] + c12["logmar_min"]) / 2, 2)
    return [
        claim("above the class 11 limit", round(c11["logmar_gt"] + 0.1, 2), wide, "class:11"),
        claim("exactly at the class 11 limit (read as class 12)", c11["logmar_gt"], wide, "class:12"),
        claim("class 12 lower end", c12["logmar_min"], wide, "class:12"),
        claim("class 12 middle", mid12, wide, "class:12"),
        claim("class 12 upper end", c12["logmar_max"], wide, "class:12"),
        claim("between the classes 13 and 12", gap_mid, wide, "specialist"),
        claim("class 13 upper end", c13["logmar_max"], wide, "class:13"),
        claim("class 13 middle", mid13, wide, "class:13"),
        claim("class 13 lower end", c13["logmar_min"], wide, "class:13"),
        claim("below the class 13 range", round(c13["logmar_min"] - 0.1, 2), wide, "none"),
        claim("field just under the class 12 limit", 0.0, round(c12["field_lt_deg"] - 0.1, 1), "class:12"),
        claim("field at the class 12 limit", 0.0, c12["field_lt_deg"], "class:13"),
        claim("field just under the class 13 limit", 0.0, round(c13["field_lt_deg"] - 0.1, 1), "class:13"),
        claim("field at the class 13 limit", 0.0, c13["field_lt_deg"], "none"),
        claim("acuity in the gap and field in the class 13 band", gap_mid, round(c13["field_lt_deg"] - 1, 1), "specialist"),
    ]


def short_answer(crit: dict[int, dict], sex: str, height: float, arm: float) -> str:
    """The statement of the page: nested classes, three limits at the same time, most impaired first."""
    for class_id in (40, 41):
        limit = crit[class_id][sex]
        if height <= limit["max_height_cm"] and arm <= limit["max_arm_cm"] and height + arm <= limit["max_sum_cm"]:
            return f"class:{class_id}"
    return "none"


def short_claims(crit: dict[int, dict]) -> list[dict]:
    out = []
    for sex in ("male", "female"):
        for class_id in (40, 41):
            limit = crit[class_id][sex]
            height = limit["max_sum_cm"] - limit["max_arm_cm"]
            arm = limit["max_arm_cm"]
            for note, h in (("on the sum limit", height), ("one cm over the sum limit", height + 1)):
                out.append(
                    {
                        "group": "short_stature",
                        "note": f"class {class_id}, {sex}, {note}",
                        "fields": {"sex": "M" if sex == "male" else "F", "height_cm": float(h), "longest_arm_cm": float(arm)},
                        "expected": short_answer(crit, sex, h, arm),
                    }
                )
        for class_id in (40, 41):
            limit = crit[class_id][sex]
            h, a = round(limit["max_height_cm"] * 0.8, 1), round(limit["max_arm_cm"] * 0.8, 1)
            out.append(
                {
                    "group": "short_stature",
                    "note": f"inside the class {class_id} limits, {sex}",
                    "fields": {"sex": "M" if sex == "male" else "F", "height_cm": h, "longest_arm_cm": a},
                    "expected": short_answer(crit, sex, h, a),
                }
            )
    return out


def limb_claims(group: str, patterns: dict[str, list[tuple[int, int, int, int]]]) -> list[dict]:
    out = []
    for answer, plist in sorted(patterns.items()):
        for pattern in plist:
            for mirrored in (False, True):
                levels = arrangement(pattern)
                if mirrored:
                    levels = {
                        "lower_left": levels["lower_right"],
                        "lower_right": levels["lower_left"],
                        "upper_left": levels["upper_right"],
                        "upper_right": levels["upper_left"],
                    }
                profile = Profile(
                    impairments=frozenset({Impairment.LIMB_DEFICIENCY}), posture=POSTURES[group], **levels
                )
                # Independent of the engine: the table of the study mode (education/trace.py).
                out.append(
                    {
                        "group": group,
                        "note": f"pattern {pattern}{' mirrored' if mirrored else ''}",
                        "fields": levels,
                        "expected": build_trace(group, profile).answer,
                    }
                )
    return out


# --- k2 example --------------------------------------------------------------------------------------------


def example_for(group: str, class_id: int) -> dict | None:
    """First fictitious case of the study mode (seed 0) whose answer is this class."""
    answer = f"class:{class_id}"
    for level in ("easy", "medium", "hard"):
        for index, candidate in enumerate(k2_cases.bank(group, 0).pools[level]):
            if candidate.answer == answer and candidate.masked is None:
                case = k2_cases.get_case(group, level, 0, index)
                trace = k2_cases.trace_of(case)
                return {
                    "case_id": case.case_id,
                    "summary": case.presentation.summary,
                    "facts": [{"label": f.label, "value": f.value} for f in case.presentation.facts],
                    "conclusion": trace.conclusion,
                }
    return None


# --- pages ---------------------------------------------------------------------------------------------------


def crumb(label: str, href: str | None = None) -> dict:
    return {"label": label, "href": href}


def hub_page(review: dict) -> dict:
    sections = []
    for section_id, (heading, paragraphs) in T.HUB_SECTIONS.items():
        blocks: list[dict] = [para(text) for text in paragraphs]
        if section_id == "grupos":
            blocks.append(
                {
                    "kind": "cards",
                    "items": [
                        {
                            "title": T.GROUP_TITLES[group],
                            "href": scope.group_path(group),
                            "text": rich(T.HUB_GROUP_CARD[group]),
                            "classes": list(scope.class_ids(group)),
                        }
                        for group in scope.GROUPS
                    ],
                }
            )
        if section_id == "usar":
            blocks.append({"kind": "link", "href": "/educacao", "label": "Ir para o modo educação"})
            blocks.append({"kind": "link", "href": scope.GLOSSARY_PATH, "label": "Ver o glossário"})
        sections.append({"id": section_id, "heading": heading, "blocks": blocks})
    page = {
        "path": scope.HUB_PATH,
        "kind": "hub",
        "title": T.HUB_TITLE,
        "intro": rich(T.HUB_INTRO),
        "breadcrumbs": [crumb("Guia")],
        "sections": sections,
    }
    return finish(page, review)


def finish(page: dict, review: dict) -> dict:
    page["terms"] = terms_in(page["sections"] + [page.get("intro", [])])
    page["review_status"] = review_status(page["path"], review)
    return page


def limb_table_rows(group: str, patterns: dict[str, list[tuple[int, int, int, int]]]) -> list[list]:
    rows = []
    for class_id in scope.class_ids(group):
        plist = patterns.get(f"class:{class_id}", [])
        if plist:
            rows.append(
                [
                    {"t": T.CLASS_LABEL.replace("${class_id}", str(class_id)), "href": scope.class_path(group, class_id)},
                    rich(describe_pattern(group, plist[0])),
                ]
            )
    return rows


def group_page(group: str, catalog: Catalog, crit: dict[int, dict], patterns: dict, review: dict) -> dict:
    ids = scope.class_ids(group)
    path = scope.group_path(group)
    sections: list[dict] = [{"id": "o-que-decide", "heading": "O que decide a classe neste grupo", "blocks": [para(p) for p in T.GROUP_DECIDES[group]]}]
    figures: list[str] = []
    limit_values: dict[str, Any] = {}

    if group == "visual":
        values = visual_values(crit)
        limit_values = values
        rows = [
            [
                {"t": T.CLASS_LABEL.replace("${class_id}", "11"), "href": scope.class_path(group, 11)},
                " / ".join(catalog.classes[11].codes),
                rich(T.VISUAL_RULE_11, values),
            ]
        ]
        for class_id in (12, 13):
            rows.append(
                [
                    {"t": T.CLASS_LABEL.replace("${class_id}", str(class_id)), "href": scope.class_path(group, class_id)},
                    " / ".join(catalog.classes[class_id].codes),
                    rich(
                        T.VISUAL_RULE_RANGE,
                        {
                            "logmar_min": values[f"logmar_min_{class_id}"],
                            "logmar_max": values[f"logmar_max_{class_id}"],
                            "field_lt": values[f"field_lt_{class_id}"],
                        },
                    ),
                ]
            )
        diffs = [bullets(T.VISUAL_DIFFS, values)]
        figures = ["fig-logmar", "fig-field"]
    elif group == "short_stature":
        values = {"c40": "40", "c41": "41"}
        limit_values = values
        rows = [
            [
                {"t": T.CLASS_LABEL.replace("${class_id}", str(class_id)), "href": scope.class_path(group, class_id)},
                " / ".join(catalog.classes[class_id].codes),
                rich(T.SHORT_RULE),
            ]
            for class_id in ids
        ]
        diffs = [para(T.SHORT_DIFFS_INTRO, values), short_table(crit)]
        figures = ["fig-stature"]
    else:
        values = {"c44": "44"}
        limit_values = values
        rows = limb_table_rows(group, patterns)
        diffs = [bullets(T.LIMB_DIFFS[group])]
        rows = [[row[0], row[1]] for row in rows]
        figures = ["fig-levels-lower"] + (["fig-levels-upper"] if group == "limb_standing" else [])

    if group in ("limb_standing", "limb_prosthesis"):
        headers = T.LIMB_TABLE_HEADERS
        caption = T.LIMB_TABLE_CAPTION
    else:
        headers = T.GROUP_TABLE_HEADERS
        caption = T.GROUP_TABLE_CAPTION
    sections.append({"id": "classes-lado-a-lado", "heading": caption, "blocks": [{"kind": "table", "caption": caption, "headers": list(headers), "rows": rows}]})
    sections.append({"id": "como-se-diferenciam", "heading": "Como as classes vizinhas se diferenciam", "blocks": diffs})
    if group in ("limb_standing", "limb_prosthesis"):
        specialist = sorted(patterns.get("specialist", []))
        sections[-1]["blocks"].append(
            {
                "kind": "details",
                "summary": T.LIMB_SPECIALIST_HEADING,
                "blocks": [para(T.LIMB_SPECIALIST_INTRO), {"kind": "ul", "items": [rich(describe_pattern(group, p)) for p in specialist]}],
            }
        )
    sections.append({"id": "ilustracoes", "heading": "Ilustrações", "blocks": [{"kind": "figure", "id": fig} for fig in figures]})
    sections.append(limits_section(group, limit_values))
    sections.append(practice_section(group))
    page = {
        "path": path,
        "kind": "group",
        "group": group,
        "title": T.GROUP_TITLES[group],
        "intro": rich(T.HUB_GROUP_CARD[group]),
        "breadcrumbs": [crumb("Guia", scope.HUB_PATH), crumb(T.GROUP_TITLES[group])],
        "classes": [{"class_id": cid, "href": scope.class_path(group, cid)} for cid in ids],
        "sections": sections,
    }
    return finish(page, review)


def short_table(crit: dict[int, dict]) -> dict:
    rows = []
    for sex in ("male", "female"):
        for class_id in (40, 41):
            limit = crit[class_id][sex]
            rows.append(
                [
                    T.SEX_LABELS[sex],
                    f"Classe {class_id}",
                    f"{fmt(limit['max_height_cm'], 0)} cm",
                    f"{fmt(limit['max_arm_cm'], 0)} cm",
                    f"{fmt(limit['max_sum_cm'], 0)} cm",
                ]
            )
    return {"kind": "table", "caption": T.SHORT_TABLE_CAPTION, "headers": list(T.SHORT_TABLE_HEADERS), "rows": rows}


def limits_section(group: str, values: dict[str, Any]) -> dict:
    merged = {**values, "c11": "11", "c12": "12", "c44": "44"}
    blocks = [bullets(list(T.LIMITS[group]) + [T.LIMITS_COMMON], merged)]
    return {"id": "nao-cobre", "heading": T.LIMITS_HEADING, "blocks": blocks}


def practice_section(group: str) -> dict:
    return {
        "id": "praticar",
        "heading": T.PRACTICE_HEADING,
        "blocks": [
            para(T.PRACTICE_TEXT),
            {"kind": "link", "href": scope.practice_path(group), "label": T.PRACTICE_LINK},
            {"kind": "link", "href": scope.RULES_PATH, "label": T.TRANSPARENCY_LINK},
        ],
    }


def class_page(group: str, class_id: int, catalog: Catalog, crit: dict[int, dict], patterns: dict, review: dict) -> tuple[dict, list[dict]]:
    spec = catalog.classes[class_id]
    ids = scope.class_ids(group)
    values = {"class_id": str(class_id)}
    figures: list[dict] = []
    limit_values: dict[str, Any] = {}
    sections: list[dict] = [
        {"id": "em-uma-frase", "heading": "Em uma frase", "blocks": [para(T.CLASS_ONE_SENTENCE[class_id])]}
    ]
    rule_blocks: list[dict] = []
    diff_blocks: list[dict] = []

    if group == "visual":
        vv = visual_values(crit)
        limit_values = vv
        if class_id == 11:
            rule = fill(T.VISUAL_RULE_11, vv)
        else:
            rule = fill(
                T.VISUAL_RULE_RANGE,
                {"logmar_min": vv[f"logmar_min_{class_id}"], "logmar_max": vv[f"logmar_max_{class_id}"], "field_lt": vv[f"field_lt_{class_id}"]},
            )
        rule_blocks = [para(T.CLASS_NUMERIC_VISUAL[0].replace("{rule}", rule), values)]
        diff_blocks = [bullets(T.VISUAL_DIFFS, vv)]
        figures = [figure_logmar(crit)] + ([figure_field(crit)] if class_id in (12, 13) else [])
    elif group == "short_stature":
        limit_values = {}
        rule_blocks = [para(T.CLASS_NUMERIC_SHORT[0], values), short_table(crit)]
        diff_blocks = [para(T.SHORT_DIFFS_INTRO, {"c40": "40", "c41": "41"})]  # the table is above, once
        figures = [figure_stature()]
    else:
        plist = patterns.get(f"class:{class_id}", [])
        rule_blocks = [
            para(T.CLASS_PATTERNS_INTRO, values),
            {"kind": "ul", "items": [rich(describe_pattern(group, p)) for p in plist]},
        ]
        rows = []
        for other in ids:
            other_patterns = patterns.get(f"class:{other}", [])
            if other_patterns:
                rows.append(
                    [
                        {"t": T.CLASS_LABEL.replace("${class_id}", str(other)) + (f" ({T.CLASS_DIFF_THIS})" if other == class_id else ""), "href": scope.class_path(group, other)},
                        rich(describe_pattern(group, other_patterns[0])),
                    ]
                )
        diff_blocks = [bullets(T.LIMB_DIFFS[group]), {"kind": "table", "caption": T.CLASS_DIFF_LIMB_TABLE, "headers": list(T.LIMB_TABLE_HEADERS), "rows": rows}]
        figures = [figure_pattern(group, class_id, i, p) for i, p in enumerate(plist)]
        limit_values = {"c44": "44"}

    sections.append({"id": "o-que-a-regra-pede", "heading": T.CLASS_RULE_HEADING, "blocks": rule_blocks + [para(T.CLASS_CODES_NOTE)]})
    sections.append({"id": "como-se-diferencia", "heading": T.CLASS_DIFF_HEADING, "blocks": diff_blocks})
    sections.append({"id": "ilustracao", "heading": T.CLASS_FIGURE_HEADING, "blocks": [{"kind": "figure", "id": f["id"]} for f in figures]})
    example = example_for(group, class_id)
    if example:
        sections.append(
            {
                "id": "exemplo",
                "heading": T.CLASS_EXAMPLE_HEADING,
                "blocks": [
                    para(T.CLASS_EXAMPLE_INTRO, values),
                    {"kind": "example", **example},
                    {"kind": "link", "href": scope.practice_path(group), "label": T.CLASS_EXAMPLE_LINK},
                ],
            }
        )
    sections.append(limits_section(group, limit_values))
    reference_blocks = [para(T.CLASS_REFERENCE, {"page": str(spec.source_page)}), {"kind": "link", "href": scope.RULES_PATH, "label": T.TRANSPARENCY_LINK}]
    sections.append({"id": "referencia", "heading": T.CLASS_REFERENCE_HEADING, "blocks": reference_blocks})

    page = {
        "path": scope.class_path(group, class_id),
        "kind": "class",
        "group": group,
        "class_id": class_id,
        "title": f"Classe {class_id} ({'/'.join(spec.codes)})",
        "source_page": spec.source_page,
        "intro": [],
        "breadcrumbs": [
            crumb("Guia", scope.HUB_PATH),
            crumb(T.GROUP_TITLES[group], scope.group_path(group)),
            crumb(f"Classe {class_id}"),
        ],
        "neighbors": [
            {"class_id": cid, "href": scope.class_path(group, cid)} for cid in ids if abs(ids.index(cid) - ids.index(class_id)) == 1
        ],
        "sections": sections,
    }
    return finish(page, review), figures


def glossary_page(review: dict) -> dict:
    page = {
        "path": scope.GLOSSARY_PATH,
        "kind": "glossary",
        "title": T.GLOSSARY_TITLE,
        "intro": rich(T.GLOSSARY_INTRO),
        "breadcrumbs": [crumb("Guia", scope.HUB_PATH), crumb(T.GLOSSARY_TITLE)],
        "sections": [],
    }
    page["terms"] = []
    page["review_status"] = review_status(page["path"], review)
    return page


# --- assembly -----------------------------------------------------------------------------------------------


def build_content(generated_on: str, review: dict | None = None) -> dict:
    review = review if review is not None else {"texts_reviewed": False, "reviewed_pages": []}
    catalog = load_catalog()
    crit = criteria(catalog)
    rules = rules_version()

    patterns = {g: limb_patterns(g) for g in ("limb_standing", "limb_prosthesis")}
    pages = [hub_page(review)]
    figures: dict[str, dict] = {}
    for group in scope.GROUPS:
        pages.append(group_page(group, catalog, crit, patterns.get(group, {}), review))
        for class_id in scope.class_ids(group):
            page, page_figures = class_page(group, class_id, catalog, crit, patterns.get(group, {}), review)
            pages.append(page)
            for figure in page_figures:
                figures[figure["id"]] = figure
    pages.append(glossary_page(review))

    for figure in (figure_logmar(crit), figure_field(crit), figure_stature(), figure_levels("lower"), figure_levels("upper")):
        figures[figure["id"]] = figure

    claims = visual_claims(crit) + short_claims(crit)
    for group in ("limb_standing", "limb_prosthesis"):
        claims += limb_claims(group, patterns[group])
    for number, claim in enumerate(claims, start=1):
        claim["id"] = f"claim-{number:03d}"

    glossary = [
        {"id": term_id, "term": term, "definition": rich(definition)}
        for term_id, (term, definition) in sorted(T.GLOSSARY.items(), key=lambda item: slug_key(item[1][0]))
    ]
    for page in pages:
        if page["kind"] == "glossary":
            page["terms"] = [item["id"] for item in glossary]
    page_terms_definitions = {item["id"]: item for item in glossary}
    for page in pages:
        page["term_definitions"] = [page_terms_definitions[t] for t in page["terms"]] if page["kind"] != "glossary" else []

    return {
        "content_version": scope.CONTENT_VERSION,
        "notice": scope.NOTICE,
        "rules_id": rules.id,
        "generated_on": generated_on,
        "rules_path": scope.RULES_PATH,
        "glossary_path": scope.GLOSSARY_PATH,
        "footer": T.FOOTER_VERSION,
        "freshness_warning": T.FRESHNESS_WARNING,
        "groups": [
            {"id": g, "slug": scope.GROUP_SLUGS[g], "title": T.GROUP_TITLES[g], "href": scope.group_path(g), "classes": list(scope.class_ids(g))}
            for g in scope.GROUPS
        ],
        "pages": pages,
        "figures": figures,
        "glossary": glossary,
        "claims": claims,
    }
