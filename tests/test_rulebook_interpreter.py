"""The rule book interpreter (K20 adoption, step 0): states, constructs, validity, variants, messages, size."""
import datetime as dt
from pathlib import Path

import pytest
import yaml

from para_triage.rulebook import NoValueInForce, Rulebook, RulebookError, message
from para_triage.rulebook import interpreter, messages
from para_triage.rulebook.interpreter import DATA, STATUSES, sources

SRC = {"doc": "cpb-booklet-2024", "page": 1}
OK = {"source": SRC, "status": "implemented"}
INTERPRETER_FILES = [Path(interpreter.__file__), Path(messages.__file__)]
MAX_LINES = 500  # the stop rule of ADR 0020
SHIPPED = ("visual", "short_stature", "limb_prosthesis", "limb_standing", "intellectual", "frame_runner", "wheelchair", "neuro")

# The closed vocabulary of the format. A new construct must be added here (and to docs/rulebook.md) on purpose.
VOCABULARY = {
    "group": {"rulebook", "schema", "applies_to", "classes", "measures", "derived", "domains", "fusion", "impairment_measures", "impairment_sets", "class_groups", "parameters", "criteria", "class_rules", "flags", "gate", "pathways", "merge", "decision", "tests"},
    "parameter": {"unit", "values", "by", "same_as", "source", "status", "reviewer", "reviewed_on"},
    "criterion": {"measure", "test", "unless", "reason", "source", "status", "valid", "reviewer", "reviewed_on"},
    "test": {"op", "value", "low", "high", "inclusive", "low_inclusive", "high_inclusive"},
    "when": {"all_missing", "any_missing", "any_class", "flag", "equals"},
    "result": {"all", "classes", "meets", "borderline", "rest"},
    "class_rule": {"all_of", "any_of"},
    "decision": {"id", "when", "result", "reason", "report_missing", "report_always", "scope", "source", "status"},
    "derived": {"sum", "max", "min"},
    "pathway": {"applies_to", "measures", "derived", "criteria", "class_rules", "flags", "decision"},
}


def specs_of(data: dict) -> list[dict]:
    """The group file and each of its pathways: each has its own derived measures, criteria, flags and decision rules."""
    return [data, *data.get("pathways", {}).values()]


def rules_of(data: dict) -> list[dict]:
    return [*data.get("gate", []), *(r for s in specs_of(data) for r in s.get("decision", []))]


def book(**parts) -> Rulebook:
    """A minimal rule book with invented names: the interpreter must not need to know any real group."""
    data = {
        "rulebook": "zzz",
        "applies_to": ["zzz_impairment"],
        "classes": [1, 2, 3],
        "measures": ["m_a", "m_b"],
        "parameters": {},
        "criteria": {},
        "class_rules": {},
        "decision": [{"id": "default", "result": {"all": "not_met"}, "reason": "R_DEFAULT"}],
        **parts,
    }
    return Rulebook(data, sources())


def crit(measure, op="lt", value=10, **extra):
    return {"measure": measure, "test": {"op": op, "value": value, **extra}, "reason": "R_HIT", **OK}


def evaluate(b, measures, **options):
    return {c: v.status for c, v in b.evaluate(measures, set(b.data["applies_to"]), **options).verdicts.items()}


# --- the seven states ------------------------------------------------------------------------------------------------


def test_every_one_of_the_seven_states_can_be_produced_by_the_format():
    b = book(
        criteria={"c1": crit("m_a"), "c2": crit("m_b")},
        class_rules={1: {"any_of": ["c1"]}, 2: {"any_of": ["c2"]}},
        flags={"edge": {"measure": "m_a", "test": {"op": "between", "low": 10, "high": 12, "low_inclusive": False, "high_inclusive": False}, "reason": "R_EDGE", **OK}},
        decision=[
            {"id": "none", "when": {"all_missing": ["m_a", "m_b"]}, "result": {"all": "insufficient_data"}, "reason": "R_NONE"},
            {"id": "met", "when": {"any_class": True}, "result": {"meets": {"pick": "most_impaired"}, "classes": {3: "needs_review"}, "borderline": [{"class": 2, "if": {"flag": "edge", "primary_above": 0}}], "rest": "not_met"}},
            {"id": "edge", "when": {"flag": "edge"}, "result": {"borderline": [1], "classes": {2: "not_implemented"}, "rest": "not_met"}},
            {"id": "one", "when": {"any_missing": ["m_a", "m_b"]}, "result": {"all": "insufficient_data"}},
        ],
    )
    seen = set()
    for measures in ({}, {"m_a": 5, "m_b": 50}, {"m_a": 11, "m_b": 50}, {"m_a": 50}):
        seen |= set(evaluate(b, measures).values())
    seen.add(next(iter(b.evaluate({}, {"other"}).verdicts.values())).status)
    assert seen == set(STATUSES)


def test_not_applicable_comes_before_any_criterion_and_has_no_trace():
    b = book(criteria={"c1": crit("m_a")}, class_rules={1: {"any_of": ["c1"]}})
    result = b.evaluate({"m_a": 1}, {"something_else"})
    assert {v.status for v in result.verdicts.values()} == {"not_applicable"} and result.trace == []
    assert all(v.reasons == ("NO_RELEVANT_IMPAIRMENT",) and v.missing == () for v in result.verdicts.values())


def test_missing_measures_are_listed_in_the_declared_order_on_every_verdict():
    b = book(
        criteria={"c1": crit("m_a")},
        class_rules={1: {"any_of": ["c1"]}},
        decision=[{"id": "met", "when": {"any_class": True}, "result": {"meets": {"pick": "most_impaired"}, "rest": "not_met"}}, {"id": "d", "result": {"all": "not_met"}}],
    )
    verdicts = b.evaluate({"m_a": 5}, {"zzz_impairment"}).verdicts
    assert verdicts[1].status == "meets" and all(v.missing == ("m_b",) for v in verdicts.values())


# --- constructs ------------------------------------------------------------------------------------------------------


def test_any_of_and_all_of_and_the_most_impaired_class_wins():
    b = book(
        criteria={"a": crit("m_a"), "b": crit("m_b")},
        class_rules={1: {"all_of": ["a", "b"]}, 2: {"any_of": ["a", "b"]}},
        decision=[{"id": "met", "when": {"any_class": True}, "result": {"meets": {"pick": "most_impaired"}, "rest": "not_met"}}, {"id": "d", "result": {"all": "not_met"}}],
    )
    assert evaluate(b, {"m_a": 1, "m_b": 1}) == {1: "meets", 2: "not_met", 3: "not_met"}  # both classes have evidence: the lowest wins
    assert evaluate(b, {"m_a": 1, "m_b": 99}) == {1: "not_met", 2: "meets", 3: "not_met"}
    assert evaluate(b, {"m_a": 99, "m_b": 99}) == {1: "not_met", 2: "not_met", 3: "not_met"}


def test_unless_keeps_the_raw_result_in_the_trace_and_stops_the_second_criterion_from_counting():
    b = book(
        criteria={"first": crit("m_a", value=10), "second": {**crit("m_a", value=40), "unless": "first"}},
        class_rules={1: {"any_of": ["first"]}, 2: {"any_of": ["second"]}},
        decision=[{"id": "met", "when": {"any_class": True}, "result": {"meets": {"pick": "most_impaired"}, "rest": "not_met"}}, {"id": "d", "result": {"all": "not_met"}}],
    )
    result = b.evaluate({"m_a": 5, "m_b": 1}, {"zzz_impairment"})
    second = next(s for s in result.trace if s.criterion == "second")
    assert second.result == "met" and second.superseded_by == "first"
    assert [c for c, v in result.verdicts.items() if v.status == "meets"] == [1]
    only_second = b.evaluate({"m_a": 20, "m_b": 1}, {"zzz_impairment"})
    assert only_second.verdicts[2].status == "meets" and next(s for s in only_second.trace if s.criterion == "second").superseded_by is None


def test_a_derived_sum_is_missing_when_a_part_is_missing_and_uses_the_same_addition_as_python():
    b = book(
        derived={"total": {"sum": ["m_a", "m_b"]}},
        measures=["m_a", "m_b"],
        criteria={"t": crit("total", op="lt", value=0.3, inclusive=True)},
        class_rules={1: {"any_of": ["t"]}},
        decision=[{"id": "met", "when": {"any_class": True}, "result": {"meets": {"pick": "most_impaired"}, "rest": "not_met"}}, {"id": "d", "result": {"all": "not_met"}}],
    )
    assert evaluate(b, {"m_a": 0.1, "m_b": 0.2})[1] == ("meets" if 0.1 + 0.2 <= 0.3 else "not_met")  # 0.1 + 0.2 > 0.3 in floating point
    step = next(s for s in b.evaluate({"m_a": 1.0}, {"zzz_impairment"}).trace if s.criterion == "t")
    assert step.result == "not_assessed"


def test_a_parameter_can_be_chosen_by_a_key_measure_and_a_missing_key_is_not_assessed():
    b = book(
        parameters={"limit": {"by": {"measure": "m_b", "map": {"x": "low", "y": "high"}}, "values": {"low": [{"from": dt.date(2020, 1, 1), "value": 5}], "high": [{"from": dt.date(2020, 1, 1), "value": 50}]}, **OK}},
        criteria={"c": crit("m_a", value="limit")},
        class_rules={1: {"any_of": ["c"]}},
        decision=[{"id": "met", "when": {"any_class": True}, "result": {"meets": {"pick": "most_impaired"}, "rest": "not_met"}}, {"id": "d", "result": {"all": "not_met"}}],
    )
    assert evaluate(b, {"m_a": 20, "m_b": "x"})[1] == "not_met" and evaluate(b, {"m_a": 20, "m_b": "y"})[1] == "meets"
    assert next(s for s in b.evaluate({"m_a": 20}, {"zzz_impairment"}).trace if s.criterion == "c").result == "not_assessed"
    with pytest.raises(RulebookError):
        b.evaluate({"m_a": 20, "m_b": "unknown"}, {"zzz_impairment"})


def test_inclusive_flags_can_be_a_parameter_or_its_negation():
    b = book(
        parameters={"edge_in": {"values": [{"from": dt.date(2020, 1, 1), "value": False}], **OK}},
        criteria={"above": crit("m_a", op="gt", value=10, inclusive="edge_in"), "upto": {"measure": "m_a", "test": {"op": "between", "low": 0, "high": 10, "high_inclusive": {"not": "edge_in"}}, "reason": "R", **OK}},
        class_rules={1: {"any_of": ["above"]}, 2: {"any_of": ["upto"]}},
        decision=[{"id": "met", "when": {"any_class": True}, "result": {"meets": {"pick": "most_impaired"}, "rest": "not_met"}}, {"id": "d", "result": {"all": "not_met"}}],
    )
    assert evaluate(b, {"m_a": 10, "m_b": 0}) == {1: "not_met", 2: "meets", 3: "not_met"}
    assert evaluate(b, {"m_a": 10, "m_b": 0}, overrides={"edge_in": True}) == {1: "meets", 2: "not_met", 3: "not_met"}


# --- validation ------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "broken",
    [
        {"parameters": {"p": {"values": [], "status": "implemented"}}},  # no source
        {"parameters": {"p": {"values": [], "source": {"doc": "nowhere"}, "status": "implemented"}}},  # unknown source
        {"parameters": {"p": {"values": [], "source": SRC, "status": "maybe"}}},  # unknown status
        {"parameters": {"p": {"values": [], "source": SRC, "status": "reviewed"}}},  # reviewed needs reviewer and date
        {"criteria": {"c": {"measure": "m_a", "test": {"op": "lt", "value": 1}, "source": SRC}}},  # no status
        {"class_rules": {1: {"any_of": ["unknown"]}}},
        {"tests": [{"name": "t", "input": {}, "expect": {1: "not_met"}}]},  # a test without a source
        {"decision": [{"id": "row", "when": {"equals": {"m_a": 1}}, "result": {"all": "not_met"}}]},  # a table row without source and status
        {"decision": [{"id": "row", "when": {"equals": {"m_a": 1}}, "result": {"all": "not_met"}, "source": SRC, "status": "maybe"}]},
    ],
)
def test_malformed_rule_books_are_refused_with_a_clear_error(broken):
    with pytest.raises(RulebookError):
        book(**broken)


def test_a_reviewed_item_with_reviewer_and_date_is_accepted():
    book(parameters={"p": {"values": [], "source": SRC, "status": "reviewed", "reviewer": "Name", "reviewed_on": dt.date(2026, 1, 1)}})


# --- validity (vigencia) ----------------------------------------------------------------------------------------------


def dated_book(valid=True):
    values = [{"from": dt.date(2020, 1, 1), "to": dt.date(2024, 12, 31), "value": 10}, {"from": dt.date(2025, 1, 1), "to": None, "value": 20}]
    return book(
        parameters={"limit": {"values": values, **OK}},
        criteria={"c": {**crit("m_a", value="limit"), **({"valid": {"from": dt.date(2021, 1, 1), "to": None}} if valid else {})}},
        class_rules={1: {"any_of": ["c"]}},
        decision=[{"id": "met", "when": {"any_class": True}, "result": {"meets": {"pick": "most_impaired"}, "rest": "not_met"}}, {"id": "d", "result": {"all": "not_met"}}],
    )


def test_the_reference_date_picks_the_value_in_force_including_both_edges():
    b = dated_book()
    at = lambda d, x: evaluate(b, {"m_a": x, "m_b": 0}, on=d)[1]  # noqa: E731
    assert at(dt.date(2024, 12, 31), 15) == "not_met" and at(dt.date(2025, 1, 1), 15) == "meets"  # `to` and the next `from`
    assert at(dt.date(2025, 6, 1), 25) == "not_met"
    step = next(s for s in b.evaluate({"m_a": 5, "m_b": 0}, {"zzz_impairment"}, on=dt.date(2022, 1, 1)).trace if s.criterion == "c")
    assert step.reference == {"limit": 10}


def test_the_value_starts_exactly_on_its_from_date_and_a_date_without_a_value_is_an_explicit_error():
    b = dated_book(valid=False)
    with pytest.raises(NoValueInForce):
        b.evaluate({"m_a": 5, "m_b": 0}, {"zzz_impairment"}, on=dt.date(2019, 12, 31))
    assert b.value("limit", dt.date(2020, 1, 1)) == 10


def test_a_criterion_outside_its_validity_is_skipped_in_the_trace():
    b = dated_book()
    trace = b.evaluate({"m_a": 5, "m_b": 0}, {"zzz_impairment"}, on=dt.date(2020, 6, 1)).trace
    assert next(s for s in trace if s.criterion == "c").result == "skipped"


def test_the_shipped_groups_start_their_values_on_the_first_day_of_the_booklet_year_and_use_a_fixed_reference_date():
    for name in ("visual", "short_stature"):
        group = Rulebook.load(name)
        with pytest.raises(NoValueInForce):
            group.evaluate({"sex": "M", "height_cm": 1, "longest_arm_cm": 1, "logmar_best_eye": 1.0, "visual_field_deg": 1}, set(group.data["applies_to"]), on=dt.date(2023, 12, 31))
        group.evaluate({"sex": "M", "height_cm": 1, "longest_arm_cm": 1, "logmar_best_eye": 1.0, "visual_field_deg": 1}, set(group.data["applies_to"]), on=dt.date(2024, 1, 1))
    assert interpreter.load_variant("cpb-2024")["reference_date"] == dt.date(2024, 10, 1)


# --- variants --------------------------------------------------------------------------------------------------------


def test_overrides_by_name_change_the_verdict_and_unknown_names_or_variants_are_errors(tmp_path):
    visual = Rulebook.load("visual")
    probe = {"logmar_best_eye": 2.6, "visual_field_deg": 120}
    assert evaluate(visual, probe)[12] == "meets"
    assert evaluate(visual, probe, overrides={"boundary_in_class_11": True})[11] == "meets"
    with pytest.raises(RulebookError):
        visual.evaluate(probe, {"visual"}, overrides={"no_such_parameter": 1})
    with pytest.raises(RulebookError):
        visual.evaluate(probe, {"visual"}, variant="no-such-variant")
    path = tmp_path / "mine.yaml"
    path.write_text(yaml.safe_dump({"variant": "mine", "reference_date": dt.date(2024, 10, 1), "overrides": {"boundary_in_class_11": True, "a_parameter_of_another_group": 1}}), encoding="utf-8")
    assert evaluate(visual, probe, variant=str(path))[11] == "meets"  # a variant spans groups: names of other groups are ignored


def test_an_override_of_a_parameter_with_a_key_takes_a_scalar_or_one_value_per_key():
    short = Rulebook.load("short_stature")
    probe = {"sex": "M", "height_cm": 131, "longest_arm_cm": 40}
    assert evaluate(short, probe)[40] == "not_met"
    assert evaluate(short, probe, overrides={"max_height_class_40": 140})[40] == "meets"
    assert evaluate(short, probe, overrides={"max_height_class_40": {"male": 140, "female": 1}})[40] == "meets"


# --- messages --------------------------------------------------------------------------------------------------------


def used_reason_codes():
    codes = {"NO_RELEVANT_IMPAIRMENT"}
    for name in SHIPPED:
        data = Rulebook.load(name).data
        for kind in ("criteria", "flags"):
            codes |= {spec["reason"] for s in specs_of(data) for spec in s.get(kind, {}).values() if spec.get("reason")}
        for rule in rules_of(data):
            codes |= {rule["reason"]} if rule.get("reason") else set()
            codes |= {item["reason"] for item in rule["result"].get("borderline", []) if isinstance(item, dict) and item.get("reason")}
    return codes


def test_every_reason_code_used_in_the_groups_has_a_text_in_portuguese_and_english():
    codes = used_reason_codes()
    assert codes and codes <= messages.codes("pt") and codes <= messages.codes("en")
    assert messages.codes("pt") == messages.codes("en")


def test_messages_fill_placeholders_fall_back_to_english_and_keep_unknown_codes():
    assert "2,6" in message("ACUITY_IN_CLASS_RANGE", "pt", value="2,6", test="> 2.6") or "2,6" in message("SS_WITHIN_LIMIT", "pt", value="2,6", test="<= 3")
    assert message("MEASURE_MISSING", "pt", missing="sex") == "Falta medir: sex."
    assert message("MEASURE_MISSING", "es", missing="sex") == "Missing measure: sex."  # no Spanish yet: English
    assert message("NO_SUCH_CODE") == "NO_SUCH_CODE"
    assert message("MEASURE_MISSING", "pt") == "Falta medir: {missing}."  # a placeholder without a value stays visible


# --- the data files, the format and the size --------------------------------------------------------------------------


def test_the_tests_as_data_of_the_shipped_groups_pass_and_each_cites_a_source_and_a_known_criterion():
    for name in SHIPPED:
        group = Rulebook.load(name)
        assert group.run_tests() == []
        known = {n for s in specs_of(group.data) for kind in ("criteria", "flags") for n in s.get(kind, {})} | {r["id"] for r in rules_of(group.data)}
        assert len(group.data["tests"]) >= 8
        assert all(case["criterion"] in known and case["source"]["doc"] in sources() for case in group.data["tests"])


def test_every_criterion_and_parameter_of_the_shipped_groups_has_a_source_a_status_and_the_booklet_as_document():
    for name in SHIPPED:
        data = Rulebook.load(name).data
        for kind in ("parameters", "criteria", "flags"):
            for spec in [i for s in specs_of(data) for i in s.get(kind, {}).values()]:
                assert spec["source"]["doc"] == "cpb-booklet-2024" and spec["status"] in {"implemented", "provisional"}


def test_the_format_vocabulary_is_closed_so_the_language_cannot_grow_by_accident():
    for name in SHIPPED:
        data = yaml.safe_load((DATA / "groups" / f"{name}.yaml").read_text(encoding="utf-8"))
        tested = {f"{i}{n}": c for i, s in enumerate(specs_of(data)) for kind in ("criteria", "flags") for n, c in s.get(kind, {}).items()}
        assert set(data) <= VOCABULARY["group"] and all(set(p) <= VOCABULARY["pathway"] for p in data.get("pathways", {}).values())
        assert not data.get("pathways") or data["merge"] == "best_status"
        assert all(set(p) <= VOCABULARY["parameter"] for p in data["parameters"].values())
        assert all(set(c) <= VOCABULARY["criterion"] for c in tested.values())
        assert all(set(c["test"]) <= VOCABULARY["test"] and c["test"]["op"] in {"gt", "lt", "between", "eq", "ne"} for c in tested.values())
        assert all(set(r) <= VOCABULARY["class_rule"] for s in specs_of(data) for r in s.get("class_rules", {}).values())
        assert all(len(spec) == 1 and set(spec) <= VOCABULARY["derived"] for s in specs_of(data) for spec in s.get("derived", {}).values())
        for rule in rules_of(data):
            assert set(rule) <= VOCABULARY["decision"] and set(rule.get("when", {})) <= VOCABULARY["when"] and set(rule["result"]) <= VOCABULARY["result"]


def code_lines(path: Path) -> int:
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip() and not line.strip().startswith("#"))


def test_the_interpreter_stays_under_the_stop_rule_of_500_lines():
    total = sum(code_lines(p) for p in INTERPRETER_FILES)
    assert total <= MAX_LINES, f"{total} lines: stop and tell the architecture session (ADR 0020)"


def test_the_interpreter_knows_no_group_name():
    text = " ".join(p.read_text(encoding="utf-8").lower() for p in INTERPRETER_FILES)
    for name in ("visual", "short_stature", "acuity", "logmar", "height", "stature", "booklet_gap", "field_"):
        assert name not in text, name


def test_the_shipped_groups_are_the_ones_the_commands_know():
    from para_triage.rulebook.__main__ import GROUPS

    assert set(SHIPPED) == set(GROUPS) == {p.stem for p in (DATA / "groups").glob("*.yaml")}


def test_the_negation_of_a_parameter_is_used_in_exactly_one_place():
    uses = 0
    for name in SHIPPED:
        text = (DATA / "groups" / f"{name}.yaml").read_text(encoding="utf-8")
        uses += text.count("{not: ")
    assert uses == 1  # high_inclusive of acuity_12: the one condition that starts to look like an expression


# --- constructs of the table of levels (step 3a) ----------------------------------------------------------------------


def table_book(**parts):
    """Two level measures turned into an ordered pair, a gate on a categorical measure and a table of rows."""
    row = {"source": SRC, "status": "implemented"}
    return book(**{
        "measures": ["m_a", "m_b", "m_kind"],
        "derived": {"hi": {"max": ["m_a", "m_b"]}, "lo": {"min": ["m_a", "m_b"]}},
        "parameters": {"wanted": {"values": [{"from": dt.date(2024, 1, 1), "to": None, "value": "kind_x"}], **OK}},
        "flags": {"other_kind": {"measure": "m_kind", "test": {"op": "ne", "value": "wanted"}, "reason": "R_KIND", **OK}},
        "decision": [
            {"id": "kind_missing", "when": {"any_missing": ["m_kind"]}, "result": {"all": "insufficient_data"}, "report_missing": ["m_kind"]},
            {"id": "other_kind", "when": {"flag": "other_kind"}, "result": {"all": "not_met"}, "report_missing": []},
            {"id": "levels_missing", "when": {"any_missing": ["m_a", "m_b"]}, "result": {"all": "insufficient_data"}, "report_missing": ["m_a", "m_b"]},
            {"id": "both", "when": {"equals": {"hi": 3, "lo": 3}}, "result": {"classes": {1: "meets"}, "rest": "not_met"}, **row},
            {"id": "one", "when": {"equals": {"hi": 3}}, "result": {"classes": {2: "borderline", 3: "borderline"}, "rest": "not_met"}, **row},
            {"id": "default", "result": {"all": "needs_review"}},
        ],
        **parts,
    })


def table(b, a, bb, kind="kind_x"):
    given = {k: v for k, v in {"m_a": a, "m_b": bb, "m_kind": kind}.items() if v is not None}
    verdicts = b.evaluate(given, {"zzz_impairment"}).verdicts
    return {c: v.status for c, v in verdicts.items()}, verdicts[1].missing


def test_derived_max_and_min_make_an_ordered_pair_and_rows_are_read_in_order_with_equals():
    b = table_book()
    assert table(b, 3, 3)[0] == {1: "meets", 2: "not_met", 3: "not_met"}
    assert table(b, 0, 3)[0] == {1: "not_met", 2: "borderline", 3: "borderline"} == table(b, 3, 0)[0]  # the side does not matter
    assert set(table(b, 1, 2)[0].values()) == {"needs_review"}  # the row without `when` is the "otherwise"
    assert b.evaluate({"m_a": 3, "m_b": 3, "m_kind": "kind_x"}, {"zzz_impairment"}).decision == "both"


def test_eq_and_ne_compare_a_categorical_measure_with_a_parameter_or_a_literal():
    b = table_book()
    assert table(b, 3, 3, "kind_y")[0] == dict.fromkeys((1, 2, 3), "not_met")
    flag = lambda op, value, x: b._check({"op": op, "value": value}, x, dt.date(2024, 10, 1), {}, {})[0]  # noqa: E731
    assert flag("eq", 0, 0) and not flag("eq", 0, 1) and flag("ne", 0, 1) and not flag("ne", 0, 0) and flag("eq", True, True)
    assert flag("eq", "wanted", "kind_x") and not flag("ne", "wanted", "kind_x")


def test_report_missing_says_which_missing_measures_a_verdict_reports_and_omitted_means_all_of_them():
    b = table_book()
    assert table(b, None, None, None)[1] == ("m_kind",)  # only the measure the rule is about, though three are missing
    assert table(b, None, None, "kind_y")[1] == ()  # a rule that reports nothing, though two are missing
    assert table(b, None, 3)[1] == ("m_a",)  # filtered to the ones really missing, in the order of the list
    assert table(b, 1, 1)[1] == ()
    omitted = book(measures=["m_a", "m_b"], decision=[{"id": "d", "result": {"all": "not_met"}}])
    assert omitted.evaluate({}, {"zzz_impairment"}).verdicts[1].missing == ("m_a", "m_b")


def test_report_always_lists_the_fields_as_they_are_even_when_they_are_present():
    b = book(measures=["m_a", "m_b"], decision=[{"id": "d", "result": {"all": "not_met"}, "report_always": ["m_b", "m_a"]}])
    assert b.evaluate({"m_a": 1, "m_b": 2}, {"zzz_impairment"}).verdicts[1].missing == ("m_b", "m_a")  # present, and listed in the order written
    assert b.evaluate({}, {"zzz_impairment"}).verdicts[1].missing == ("m_b", "m_a")


def test_criteria_and_class_rules_are_optional_when_the_group_is_only_a_table():
    b = Rulebook({"rulebook": "zzz", "applies_to": ["zzz_impairment"], "classes": [1, 2], "measures": ["m_a"], "parameters": {}, "decision": [{"id": "d", "result": {"all": "not_met"}}]}, sources())
    assert b.evaluate({"m_a": 1}, {"zzz_impairment"}).verdicts[1].status == "not_met"


def test_a_row_of_the_table_that_is_not_the_otherwise_needs_a_known_source_and_a_status():
    with pytest.raises(RulebookError, match="table row"):
        table_book(decision=[{"id": "r", "when": {"equals": {"hi": 3}}, "result": {"all": "not_met"}, "source": {"doc": "nowhere"}, "status": "implemented"}])


# --- constructs of the pathways (step 3b) -----------------------------------------------------------------------------


def pathway_book(**parts):
    """A gate and two pathways, with invented names: `up` reads m_a and `down` reads m_b; each says what it reports as missing."""
    data = {
        "rulebook": "zzz",
        "applies_to": ["imp_a", "imp_b"],
        "classes": [1, 2],
        "measures": ["m_gate", "m_a", "m_b"],
        "parameters": {},
        "flags": {"closed": {"measure": "m_gate", "test": {"op": "eq", "value": 0}, "reason": "R_CLOSED", **OK}},
        "gate": [{"id": "closed", "when": {"flag": "closed"}, "result": {"all": "not_met"}, "report_missing": [], "reason": "R_CLOSED"}],
        "merge": "best_status",
        "pathways": {
            "up": {
                "applies_to": ["imp_a"],
                "measures": ["m_a"],
                "decision": [
                    {"id": "a_missing", "when": {"any_missing": ["m_a"]}, "result": {"all": "insufficient_data"}, "report_missing": ["m_a"], "reason": "R_A_MISSING"},
                    {"id": "a_high", "when": {"equals": {"m_a": 9}}, "result": {"classes": {1: "meets"}, "rest": "not_met"}, "reason": "R_UP", **OK},
                    {"id": "a_rest", "result": {"all": "not_met"}, "reason": "R_UP_REST"},
                ],
            },
            "down": {
                "applies_to": ["imp_b"],
                "measures": ["m_b"],
                "flags": {"low": {"measure": "m_b", "test": {"op": "lt", "value": 5}, **OK}, "tiny": {"measure": "m_b", "test": {"op": "lt", "value": 2}, **OK}},
                "decision": [
                    {"id": "b_missing", "when": {"any_missing": ["m_b"]}, "result": {"all": "insufficient_data"}, "reason": "R_B_MISSING"},
                    {"id": "b_low", "when": {"flag": ["low", "tiny"]}, "result": {"borderline": [1, {"class": 2, "if": {"flag": "low"}}], "rest": "not_met"}, "reason": "R_DOWN"},
                    {"id": "b_rest", "result": {"all": "not_met"}, "reason": "R_DOWN_REST"},
                ],
            },
        },
        **parts,
    }
    return Rulebook(data, sources())


def pathway(b, impairments, **measures):
    evaluation = b.evaluate(measures, set(impairments))
    return {c: (v.status, v.reasons, v.missing) for c, v in evaluation.verdicts.items()}, evaluation.decision


def test_a_gate_ends_the_evaluation_before_any_pathway_and_a_pathway_runs_only_when_its_impairment_is_declared():
    b = pathway_book()
    closed, decision = pathway(b, ["imp_a", "imp_b"], m_gate=0, m_a=9, m_b=1)
    assert decision == "closed" and {s for s, _, _ in closed.values()} == {"not_met"}
    only_down, decision = pathway(b, ["imp_b"], m_gate=1, m_a=9, m_b=1)  # the `up` pathway is not run: m_a is not read
    assert decision == "b_low" and only_down[1][0] == "borderline"


def test_pathways_are_merged_per_class_by_the_best_status_and_the_winner_brings_its_own_reasons_and_missing():
    b = pathway_book()
    merged, decision = pathway(b, ["imp_a", "imp_b"], m_gate=1, m_a=9, m_b=1)
    assert merged[1] == ("meets", ("R_UP",), ()) and merged[2][0] == "borderline"  # class 1: meets beats borderline; class 2: borderline beats not_met
    assert decision == "a_high+b_low"  # the rules that decided, in the order of the pathways
    better_down, _ = pathway(b, ["imp_a", "imp_b"], m_gate=1, m_b=1)  # `up` asks for m_a, `down` is borderline: borderline beats insufficient_data
    assert better_down[1][0] == "borderline" and better_down[1][2] == ()


def test_a_tie_adds_the_reasons_without_repeating_them_and_keeps_the_missing_of_the_first_pathway():
    b = pathway_book()
    tie, _ = pathway(b, ["imp_a", "imp_b"], m_gate=1, m_a=3, m_b=7)
    assert tie[1] == ("not_met", ("R_UP_REST", "R_DOWN_REST"), ())
    both_missing, _ = pathway(b, ["imp_a", "imp_b"], m_gate=1)
    assert both_missing[1] == ("insufficient_data", ("R_A_MISSING", "R_B_MISSING"), ("m_a",))  # not ("m_a", "m_b"): the first one wins
    swapped = pathway_book()
    swapped.data["pathways"] = dict(reversed(list(swapped.data["pathways"].items())))
    assert pathway(swapped, ["imp_a", "imp_b"], m_gate=1)[0][1][2] == ("m_b",)  # the order of the file is the order of the tie


def test_a_list_of_flags_needs_all_of_them_and_a_borderline_condition_needs_no_primary_class():
    b = pathway_book()
    assert pathway(b, ["imp_b"], m_gate=1, m_b=1)[0][2][0] == "borderline"  # low and tiny, so 2 is borderline by its own condition
    assert pathway(b, ["imp_b"], m_gate=1, m_b=3)[1] == "b_rest"  # low, but not tiny: the rule does not hold


def test_a_group_with_pathways_is_refused_without_the_merge_or_with_a_decision_of_its_own():
    bad = [{"merge": "other"}, {"decision": [{"id": "d", "result": {"all": "not_met"}}]}]
    for broken in bad:
        with pytest.raises(RulebookError, match="pathways"):
            pathway_book(**broken)


# --- constructs of the two postures and the set of impairments (step 5c) ------------------------------------------------------


def scope_book(**parts):
    """Two groups of classes decided by different rules, and a rule that reads which impairments are declared; invented names."""
    row = {"source": SRC, "status": "implemented"}
    data = {
        "rulebook": "zzz",
        "applies_to": ["imp_a", "imp_b", "imp_c"],
        "classes": [1, 2, 3, 4],
        "measures": ["m_a", "m_b"],
        "parameters": {},
        "impairment_measures": ["imp_a", "imp_b"],
        "derived": {"has_either": {"max": ["has_imp_a", "has_imp_b"]}},
        "class_groups": {"low": {"classes": [1, 2], "outside_reason": "R_HIGH"}, "high": {"classes": [3, 4], "outside_reason": "R_LOW"}},
        "flags": {
            "only_a": {"measure": "has_imp_a", "test": {"op": "eq", "value": True}, **OK},
            "no_b": {"measure": "has_imp_b", "test": {"op": "eq", "value": False}, **OK},
            "either": {"measure": "has_either", "test": {"op": "eq", "value": True}, **OK},
        },
        "decision": [
            {"id": "low_needs_m_a", "scope": "low", "when": {"any_missing": ["m_a"]}, "result": {"all": "insufficient_data"}, "report_missing": ["m_a"], "reason": "R_MISSING"},
            {"id": "a_alone", "scope": "high", "when": {"flag": ["only_a", "no_b"]}, "result": {"classes": {3: "meets"}, "rest": "not_met"}, "report_missing": [], "reason": "R_A"},
            {"id": "either", "scope": "high", "when": {"flag": "either"}, "result": {"borderline": [4], "rest": "needs_review"}, "report_missing": ["m_b"], "reason": "R_E"},
            {"id": "rest", "result": {"all": "not_met"}, "reason": "R_REST"},
        ],
        **parts,
    }
    return Rulebook(data, sources())


def scoped(b, impairments, **measures):
    evaluation = b.evaluate(measures, set(impairments))
    return {c: (v.status, v.reasons, v.missing) for c, v in evaluation.verdicts.items()}, evaluation.decision


def test_the_declared_impairments_become_boolean_measures_that_flags_and_derived_measures_can_read():
    b = scope_book()
    only_a, decision = scoped(b, ["imp_a"], m_a=1)
    assert decision == "a_alone" and only_a[3][0] == "meets"  # imp_a declared and imp_b not
    both, decision = scoped(b, ["imp_a", "imp_b"], m_a=1)
    assert decision == "either" and both[4][0] == "borderline"  # the derived max of two booleans
    only_c, decision = scoped(b, ["imp_c"], m_a=1)
    assert decision == "rest"  # nothing about imp_a or imp_b: the booleans are false, never missing
    assert "has_imp_a" not in b.measures


def test_a_rule_with_a_scope_decides_only_its_classes_and_the_others_are_not_met_with_the_reason_of_their_group_and_nothing_asked():
    b = scope_book()
    low, decision = scoped(b, ["imp_c"])
    assert decision == "low_needs_m_a"
    assert low[1] == ("insufficient_data", ("R_MISSING",), ("m_a",)) and low[2][0] == "insufficient_data"
    assert low[3] == ("not_met", ("R_HIGH",), ()) and low[4] == ("not_met", ("R_HIGH",), ())  # outside: the reason the group gives for them, no missing field
    high, _ = scoped(b, ["imp_a", "imp_b"], m_a=1)
    assert high[1] == ("not_met", ("R_LOW",), ()) and high[4][2] == ("m_b",)  # the rest of the group is decided by the rule, the others by the group


def test_a_scope_that_is_not_a_class_group_is_refused():
    with pytest.raises(RulebookError, match="class group"):
        scope_book(decision=[{"id": "d", "scope": "nowhere", "result": {"all": "not_met"}}])
