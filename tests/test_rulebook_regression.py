"""Side-by-side regression of the rule book against the current engine (steps 1 and 2): zero divergences."""
import pytest

from para_triage.rulebook import Rulebook
from para_triage.rulebook.__main__ import main
from para_triage.rulebook.compare import Case, diff_variants, format_diff, format_report, regress, sample_cases, sweep_cases
from para_triage.rules.catalog import load_catalog

SEEDS = range(3)  # about 4 thousand profiles per group; `python -m para_triage.rulebook regress --seeds 20` is the big one


@pytest.fixture(scope="module")
def books():
    return {name: Rulebook.load(name) for name in ("visual", "short_stature")}


@pytest.mark.parametrize("group", ["visual", "short_stature"])
def test_the_rule_book_gives_the_same_status_and_missing_fields_as_the_current_engine(books, group):
    book = books[group]
    cases = sample_cases(book, SEEDS) + sweep_cases(book)
    report = regress(book, cases)
    assert len(cases) >= 2500 and report.clean, format_report(report)
    sources = set(report.total)
    assert {"k2", "k2-nothing", "sweep", "other"} <= sources and any(s.startswith("k2-no-") for s in sources)


def test_the_visual_sweep_covers_every_limit_the_gap_and_missing_measures(books):
    book = books["visual"]
    cases = sweep_cases(book)
    acuities = {c.measures.get("logmar_best_eye") for c in cases if c.source == "sweep"}
    fields = {c.measures.get("visual_field_deg") for c in cases if c.source == "sweep"}
    for limit in (1.0, 1.4, 1.5, 2.6):
        assert {round(limit + o, 2) for o in (-0.01, 0.0, 0.01, 0.05)} <= acuities
    assert {round(1.4 + 0.01 * k, 2) for k in range(11)} <= acuities  # the whole gap, one hundredth at a time
    for limit in (10, 40):
        assert {round(limit + o, 2) for o in (-0.01, 0.0, 0.01, 0.05)} <= fields
    assert None in acuities and None in fields


EXACT = {
    "M": {40: (130, 59, 180), 41: (145, 66, 200)},
    "F": {40: (125, 57, 173), 41: (137, 63, 190)},
}


def exact_limit_cases():
    """Every limit of each sex, exactly, one hundredth below and above, and sums that land on the limit."""
    cases = []
    for sex, classes in EXACT.items():
        for height_limit, arm_limit, sum_limit in classes.values():
            heights = {height_limit, height_limit - 0.01, height_limit + 0.01, sum_limit - arm_limit, sum_limit - arm_limit + 0.01}
            arms = {arm_limit, arm_limit - 0.01, arm_limit + 0.01, sum_limit - height_limit + 0.01}
            for height in heights:
                for arm in arms | {round(sum_limit - height, 2), round(sum_limit - height + 0.01, 2), round(sum_limit - height - 0.01, 2)}:
                    cases.append(Case(f"exact-{len(cases)}", "exact", {"sex": sex, "height_cm": round(height, 2), "longest_arm_cm": round(arm, 2)}, ("short_stature",)))
    return cases


def test_the_exact_limits_of_each_sex_and_the_sums_on_the_limit_agree_with_the_engine(books):
    cases = exact_limit_cases()
    report = regress(books["short_stature"], cases)
    assert len(cases) > 100 and report.clean, format_report(report)


def test_float_sums_that_look_equal_to_the_limit_are_compared_like_the_current_engine(books):
    # 0.1 + 0.2 style traps: heights and arms in tenths whose sum is the limit on paper
    cases = []
    for sex, (h40, a40, s40) in ((s, c[40]) for s, c in EXACT.items()):
        for tenth in range(900, 1400):
            height = tenth / 10
            cases.append(Case(f"tenth-{sex}-{tenth}", "tenths", {"sex": sex, "height_cm": height, "longest_arm_cm": round(s40 - height, 1)}, ("short_stature",)))
    report = regress(books["short_stature"], cases)
    assert report.clean, format_report(report)


def test_missing_sex_or_measures_and_other_impairments_agree_with_the_engine(books):
    book = books["short_stature"]
    cases = [
        Case("a", "x", {"height_cm": 110.0, "longest_arm_cm": 48.0}, ("short_stature",)),
        Case("b", "x", {"sex": "F", "longest_arm_cm": 48.0}, ("short_stature",)),
        Case("c", "x", {"sex": "M", "height_cm": 110.0}, ("short_stature",)),
        Case("d", "x", {}, ("short_stature",)),
        Case("e", "x", {"sex": "M", "height_cm": 110.0, "longest_arm_cm": 48.0}, ("visual",)),
        Case("f", "x", {"sex": "M", "height_cm": 110.0, "longest_arm_cm": 48.0}, ()),
    ]
    assert regress(book, cases).clean


def test_the_regression_detects_a_divergence_when_the_book_is_wrong(books):
    wrong = Rulebook.load("visual")
    report = regress(wrong, sample_cases(wrong, range(1)), overrides={"logmar_gt_11": 2.7})
    assert not report.clean and report.examples and "divergences" in format_report(report)


# --- numbers in the two copies ---------------------------------------------------------------------------------------


def test_the_parameters_of_the_rule_book_equal_the_criteria_of_the_catalog(books):
    catalog = load_catalog()
    visual, on = books["visual"], __import__("datetime").date(2024, 10, 1)
    crit = {cid: catalog.classes[cid].criteria for cid in (11, 12, 13)}
    expected = {
        "logmar_gt_11": crit[11]["logmar_gt"],
        "logmar_min_12": crit[12]["logmar_min"], "logmar_max_12": crit[12]["logmar_max"], "field_lt_12": crit[12]["field_lt_deg"],
        "logmar_min_13": crit[13]["logmar_min"], "logmar_max_13": crit[13]["logmar_max"], "field_lt_13": crit[13]["field_lt_deg"],
    }
    assert {name: visual.value(name, on) for name in expected} == expected
    short = books["short_stature"]
    for cid in (40, 41):
        for raw, key in (("M", "male"), ("F", "female")):
            limits = catalog.classes[cid].criteria[key]
            assert short.value(f"max_height_class_{cid}", on, key) == limits["max_height_cm"]
            assert short.value(f"max_arm_class_{cid}", on, key) == limits["max_arm_cm"]
            assert short.value(f"max_sum_class_{cid}", on, key) == limits["max_sum_cm"]


# --- variants: the diff -----------------------------------------------------------------------------------------------


def test_the_variant_diff_reproduces_the_numbers_of_the_k20_experiment(books):
    book = books["visual"]
    cases = sample_cases(book, range(5)) + sweep_cases(book)
    reading = diff_variants(book, cases, overrides_b={"boundary_in_class_11": True})
    assert reading.changed == 29 and reading.transitions == {(11, "not_met", "meets"): 29, (12, "meets", "not_met"): 29}
    limit = diff_variants(book, cases, overrides_b={"logmar_gt_11": 2.70})
    assert limit.changed == 234
    assert "class 11: meets -> not_met" in format_diff(limit)
    same = diff_variants(book, cases)
    assert same.changed == 0 and same.transitions == {}


# --- commands --------------------------------------------------------------------------------------------------------


def test_the_commands_test_regress_and_diff_work_and_report_through_the_exit_code(capsys):
    assert main(["test"]) == 0
    assert main(["regress", "--group", "visual", "--seeds", "1"]) == 0
    assert main(["diff", "--group", "visual", "--seeds", "1", "--set", "boundary_in_class_11=true"]) == 0
    out = capsys.readouterr().out
    assert "0 divergences" in out and "profiles change" in out and "class 11: not_met -> meets" in out
