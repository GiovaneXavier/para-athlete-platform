"""Study mode (K2): trace consistency with the engine, determinism, scope, quiz and texts."""
import itertools
import re
from dataclasses import replace
from pathlib import Path

import pytest

from para_triage.data.generator import sample_true_profiles
from para_triage.education import cases, scope
from para_triage.education import texts_pt as T
from para_triage.education.trace import build_trace
from para_triage.rules import Impairment, Posture, Profile, RuleEngine, Sex

EDUCATION_DIR = Path(cases.__file__).parent
ENGINE = RuleEngine()
MAX_DISCARD_SHARE = 0.01  # above this, stop and review the sampler


def limb_profile(group, levels, **extra):
    lower_left, lower_right, upper_left, upper_right = levels
    posture = Posture.STANDING if group == "limb_standing" else Posture.PROSTHESIS
    return Profile(
        impairments=frozenset({Impairment.LIMB_DEFICIENCY}),
        posture=posture,
        lower_left=lower_left,
        lower_right=lower_right,
        upper_left=upper_left,
        upper_right=upper_right,
        **extra,
    )


# --- the trace agrees with the engine ---------------------------------------------------------------------


@pytest.mark.parametrize("group", ["limb_standing", "limb_prosthesis"])
def test_amputation_table_matches_the_engine_for_every_combination_of_levels(group):
    checked = 0
    for levels in itertools.product(range(4), range(4), range(3), range(3)):
        profile = limb_profile(group, levels)
        expected = cases.engine_answer(group, profile)
        assert expected is not None, levels
        assert build_trace(group, profile).answer == expected, (group, levels)
        checked += 1
    assert checked == 144


@pytest.mark.parametrize("group", ["limb_standing", "limb_prosthesis"])
def test_amputation_table_matches_the_engine_when_a_level_is_missing(group):
    for hidden in range(4):
        for levels in itertools.product(range(4), range(4), range(3), range(3)):
            values = list(levels)
            values[hidden] = None
            profile = limb_profile(group, tuple(values))
            assert build_trace(group, profile).answer == cases.engine_answer(group, profile) == scope.OPTION_INSUFFICIENT


def report(group, mismatches, total):
    return f"{group}: {mismatches} of {total} cases would be discarded"


@pytest.mark.parametrize("group", ["visual", "short_stature"])
def test_numeric_trace_matches_the_engine_on_sampled_profiles(group):
    drawn = sample_true_profiles(80, [group], seed=11)
    mismatches = [p for p in drawn.profiles if build_trace(group, p).answer != cases.engine_answer(group, p)]
    assert len(drawn.profiles) >= 200
    assert len(mismatches) / len(drawn.profiles) <= MAX_DISCARD_SHARE, report(group, len(mismatches), len(drawn.profiles))
    assert not mismatches  # expected: none at all


def test_visual_trace_matches_the_engine_around_every_threshold():
    values = [-0.1, 0.99, 1.0, 1.01, 1.39, 1.4, 1.41, 1.49, 1.5, 1.51, 2.59, 2.6, 2.61, 3.0]
    fields = [None, 1.0, 9.9, 10.0, 10.1, 39.9, 40.0, 40.1, 120.0]
    for acuity, field in itertools.product([None, *values], fields):
        profile = Profile(
            impairments=frozenset({Impairment.VISUAL}),
            posture=Posture.STANDING,
            logmar_best_eye=acuity,
            visual_field_deg=field,
        )
        expected = cases.engine_answer("visual", profile)
        if expected is None:
            continue
        assert build_trace("visual", profile).answer == expected, (acuity, field)


def test_short_stature_trace_matches_the_engine_around_every_limit():
    checked = 0
    for sex, limits in (
        (Sex.MALE, ((130, 59, 180), (145, 66, 200))),
        (Sex.FEMALE, ((125, 57, 173), (137, 63, 190))),
    ):
        for height_limit, arm_limit, sum_limit in limits:
            for height, arm in itertools.product(
                (height_limit - 0.1, height_limit, height_limit + 0.1, sum_limit - arm_limit),
                (arm_limit - 0.1, arm_limit, arm_limit + 0.1, sum_limit - height_limit),
            ):
                profile = Profile(
                    sex=sex,
                    impairments=frozenset({Impairment.SHORT_STATURE}),
                    posture=Posture.STANDING,
                    height_cm=round(height, 1),
                    longest_arm_cm=round(arm, 1),
                )
                assert build_trace("short_stature", profile).answer == cases.engine_answer("short_stature", profile)
                checked += 1
    assert checked >= 60


def test_masked_variants_match_the_engine_and_ask_for_the_missing_field():
    for group, fields in cases.MASKABLE_FIELDS.items():
        base = cases.bank(group, 5).pools["easy"][0].profile
        for field in fields:
            masked = replace(base, **{field: None})
            expected = cases.engine_answer(group, masked)
            assert build_trace(group, masked).answer == expected


# --- the bank -----------------------------------------------------------------------------------------------


@pytest.mark.parametrize("seed", [0, 1, 2])
@pytest.mark.parametrize("group", scope.ALLOWED_GROUPS)
def test_bank_offers_every_level_and_reports_no_discarded_cases(group, seed):
    bank = cases.bank(group, seed)
    stats = bank.stats
    assert all(len(pool) >= 2 for pool in bank.pools.values()), {k: len(v) for k, v in bank.pools.items()}
    assert stats.discarded / max(stats.offered + stats.discarded, 1) <= MAX_DISCARD_SHARE
    assert stats.discarded == 0 and stats.not_offered == 0  # expected for the groups in scope


def test_limb_standing_cases_are_only_by_amputation_level():
    for seed in (0, 1):
        for pool in cases.bank("limb_standing", seed).pools.values():
            for candidate in pool:
                assert candidate.profile.impairments == frozenset({Impairment.LIMB_DEFICIENCY})
                assert candidate.profile.ankle_pf_mrc is None and candidate.profile.leg_length_diff_cm is None


def test_answers_follow_the_engine_and_difficulty_matches_the_pool():
    for group in scope.ALLOWED_GROUPS:
        for level in scope.DIFFICULTIES:
            for candidate in cases.bank(group, 3).pools[level][:25]:
                assert candidate.answer == cases.engine_answer(group, candidate.profile)
                if candidate.masked:
                    assert level == "hard" and candidate.answer == scope.OPTION_INSUFFICIENT
                    assert getattr(candidate.profile, candidate.masked) is None
                elif level == "hard":
                    assert candidate.answer == scope.OPTION_SPECIALIST
                else:
                    assert candidate.answer != scope.OPTION_SPECIALIST
                    assert cases.difficulty_of(group, candidate.profile, candidate.answer) == level


def test_easy_visual_cases_are_far_from_every_threshold_and_medium_ones_are_not():
    criteria = {cid: spec.criteria for cid, spec in cases._catalog().classes.items()}
    for candidate in cases.bank("visual", 0).pools["easy"]:
        logmar, field = cases._margin_visual(candidate.profile, criteria)
        assert logmar >= scope.VISUAL_LOGMAR_MARGIN and field >= scope.VISUAL_FIELD_MARGIN
    for candidate in cases.bank("visual", 0).pools["medium"]:
        logmar, field = cases._margin_visual(candidate.profile, criteria)
        assert logmar < scope.VISUAL_LOGMAR_MARGIN or field < scope.VISUAL_FIELD_MARGIN


# --- determinism, ids and scope -----------------------------------------------------------------------------


def test_same_seed_same_cases_and_other_seeds_differ():
    def snapshot(seed):
        return [
            (c.case_id, c.presentation, c.answer)
            for group in scope.ALLOWED_GROUPS
            for level in scope.DIFFICULTIES
            for c in (cases.get_case(group, level, seed, i) for i in range(5))
        ]

    cases.bank.cache_clear()
    first = snapshot(4)
    cases.bank.cache_clear()
    assert snapshot(4) == first
    assert snapshot(5) != first


def test_case_ids_rebuild_the_same_case_and_bad_ids_are_refused():
    case = cases.get_case("short_stature", "medium", 12, 3)
    assert case.case_id == f"k2.{scope.CASE_VERSION}.short_stature.medium.12.3"
    assert cases.case_from_id(case.case_id) == case
    for bad in (
        "",
        "k2.v1.visual.easy.1",
        "k2.v0.visual.easy.1.0",
        "k2.v1.visual.impossible.1.0",
        "k3.v1.visual.easy.1.0",
        f"k2.{scope.CASE_VERSION}.visual.easy.-1.0",
    ):
        with pytest.raises(KeyError):
            cases.case_from_id(bad)


@pytest.mark.parametrize("group", scope.EXCLUDED_GROUPS)
def test_groups_outside_the_scope_are_unreachable(group):
    with pytest.raises(KeyError):
        cases.get_case(group, "easy", 0, 0)
    with pytest.raises(KeyError):
        cases.bank(group, 0)
    with pytest.raises(KeyError):
        cases.case_from_id(f"k2.{scope.CASE_VERSION}.{group}.easy.0.0")


def test_scope_is_exactly_the_four_groups_and_excludes_the_rest():
    assert set(scope.ALLOWED_GROUPS) == {"visual", "short_stature", "limb_standing", "limb_prosthesis"}
    assert not set(scope.ALLOWED_GROUPS) & set(scope.EXCLUDED_GROUPS)
    in_scope = {cid for g in scope.GROUPS for cid in g.classes}
    assert not in_scope & set(scope.EXCLUDED_CLASSES)
    catalog_groups = {spec.group for spec in cases._catalog().classes.values()}
    assert set(scope.ALLOWED_GROUPS) | set(scope.EXCLUDED_GROUPS) >= catalog_groups - {"neuro"}


def test_every_case_is_a_draft_until_the_specialist_reviews_it():
    for group in scope.ALLOWED_GROUPS:
        assert cases.get_case(group, "easy", 0, 0).review_status == "draft"


# --- the quiz -----------------------------------------------------------------------------------------------


def test_quiz_is_deterministic_without_repeats_and_follows_the_mix():
    first = cases.build_quiz(9, 10, scope.ALLOWED_GROUPS, "mixed")
    assert [c.case_id for c in first] == [c.case_id for c in cases.build_quiz(9, 10, scope.ALLOWED_GROUPS, "mixed")]
    assert len({c.case_id for c in first}) == 10
    assert {c.group for c in first} == set(scope.ALLOWED_GROUPS)
    counts = {level: sum(1 for c in first if c.difficulty == level) for level in scope.DIFFICULTIES}
    assert counts == {"easy": 4, "medium": 4, "hard": 2}


@pytest.mark.parametrize("size", scope.QUIZ_SIZES)
@pytest.mark.parametrize("groups", [("limb_prosthesis",), ("limb_standing", "limb_prosthesis"), scope.ALLOWED_GROUPS])
def test_quiz_never_repeats_a_case_even_when_a_group_has_few_distinct_cases(size, groups):
    for seed in (0, 3):
        quiz = cases.build_quiz(seed, size, groups, "mixed")
        assert len(quiz) == size and len({c.case_id for c in quiz}) == size
        assert {c.group for c in quiz} <= set(groups)
        assert all(cases.case_from_id(c.case_id) == c for c in quiz)


def test_single_level_quiz_uses_that_level_while_the_pool_lasts():
    quiz = cases.build_quiz(1, 5, ("visual",), "hard")
    assert {c.difficulty for c in quiz} == {"hard"}


# --- texts ----------------------------------------------------------------------------------------------------


def all_case_texts(case):
    trace = cases.trace_of(case)
    texts = [case.presentation.summary, *(f"{f.label} {f.value}" for f in case.presentation.facts)]
    for step in trace.steps:
        texts += [step.criterion, step.reference, step.value, step.explanation]
    return texts, trace


def test_no_engine_reason_in_english_reaches_the_learner():
    for group in scope.ALLOWED_GROUPS:
        for level in scope.DIFFICULTIES:
            for index in range(6):
                case = cases.get_case(group, level, 2, index)
                result = ENGINE.evaluate(case.candidate.profile)
                reasons = {r for v in result.verdicts.values() for r in v.reasons}
                texts, trace = all_case_texts(case)
                shown = " | ".join([*texts, trace.conclusion, *trace.limits])
                assert not any(reason in shown for reason in reasons), (case.case_id, reasons)
                assert not re.search(r"\b(the|is|are|not|provided|criteria|amputation)\b", shown), case.case_id


def test_the_case_text_does_not_reveal_the_answer():
    for group in scope.ALLOWED_GROUPS:
        for level in scope.DIFFICULTIES:
            for index in range(8):
                case = cases.get_case(group, level, 6, index)
                shown = " ".join(all_case_texts(case)[0][: 1 + len(case.presentation.facts)])
                assert not re.search(r"[Cc]lasse\s+\d", shown) and "T4" not in shown and "F4" not in shown
                assert "limítrofe" not in shown.lower() and "especialista" not in shown.lower()


def test_every_trace_has_steps_a_conclusion_limits_and_a_booklet_page():
    for group in scope.ALLOWED_GROUPS:
        for level in scope.DIFFICULTIES:
            case = cases.get_case(group, level, 8, 0)
            trace = cases.trace_of(case)
            assert trace.steps and trace.conclusion and trace.limits and trace.source_pages
            assert trace.answer == case.answer
            assert all(step.result in T.RESULT_LABELS for step in trace.steps)


def test_education_files_never_tie_the_word_for_user_performance_to_the_quiz():
    for path in EDUCATION_DIR.glob("*.py"):
        text = path.read_text(encoding="utf-8").lower()
        assert "acurácia" not in text and "accuracy" not in text, path.name


def test_the_fixed_notice_is_the_one_in_the_brief():
    assert scope.NOTICE == (
        "Material de estudo, com dados fictícios. Não ensina a classificar oficialmente. "
        "Regras do livreto do CPB (2024) em leitura nossa, ainda a validar com a especialista."
    )
