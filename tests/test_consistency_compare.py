"""image-and-report check, PR 2: the closed schema, the comparator and the three output texts (design note sections 2, 3.2, 3.3, 12)."""
import itertools
import random

import pytest

from para_triage.consistency import compare as cmp
from para_triage.consistency import schema as sc
from para_triage.consistency.compare import CONFERE, NAO_CONFERE, NAO_SEI, compare, compare_attribute
from para_triage.consistency.schema import ATTRIBUTES, UNKNOWN, Attrs, SchemaError
from para_triage.rules.schema import LowerLimbLevel, UpperLimbLevel


# ---- the schema --------------------------------------------------------------------------------


def test_the_level_domains_are_the_ones_of_the_profile():
    assert sc.LOWER_LEVELS == tuple(int(v) for v in LowerLimbLevel)
    assert sc.UPPER_LEVELS == tuple(int(v) for v in UpperLimbLevel)
    assert sc.DOMAINS["lower_left"] == sc.DOMAINS["lower_right"] == (0, 1, 2, 3, "?")
    assert sc.DOMAINS["upper_left"] == sc.DOMAINS["upper_right"] == (0, 1, 2, "?")
    assert sc.DOMAINS["wheelchair"] == sc.DOMAINS["prosthesis"] == ("yes", "no", "?")
    assert set(sc.DOMAINS) == set(ATTRIBUTES) and len(ATTRIBUTES) == 6


@pytest.mark.parametrize("name,value", [
    ("lower_left", 4), ("lower_left", -1), ("upper_right", 3), ("upper_left", "2"), ("wheelchair", "maybe"), ("wheelchair", 1),
    ("prosthesis", True), ("lower_right", 1.0), ("lower_right", None), ("lower_left", "yes"),
])
def test_a_value_outside_the_domain_is_refused(name, value):
    with pytest.raises(SchemaError):
        Attrs(**{name: value})


def test_unknown_attributes_and_extra_keys_are_refused_and_missing_keys_are_unknown():
    with pytest.raises(SchemaError):
        Attrs.from_mapping({"lower_left": 1, "class": "T42"})
    assert Attrs.from_mapping({"lower_left": 1}).lower_right == UNKNOWN
    assert Attrs().known() == {}


def test_there_are_144_distinct_level_1_combinations_and_each_value_appears():
    combos = sc.level1_combinations()
    assert len(combos) == len(set(combos)) == 4 * 4 * 3 * 3
    assert {c.lower_left for c in combos} == {0, 1, 2, 3} and {c.upper_right for c in combos} == {0, 1, 2}
    assert all(c.wheelchair == c.prosthesis == UNKNOWN for c in combos)


def test_swapping_sides_swaps_only_sides():
    a = Attrs(3, 0, 1, 2, "yes", "no")
    assert a.swapped_sides() == Attrs(0, 3, 2, 1, "yes", "no")
    assert a.swapped_sides().swapped_sides() == a


# ---- the comparator ----------------------------------------------------------------------------

VALUES = {"lower_left": (0, 2, UNKNOWN), "wheelchair": ("yes", "no", UNKNOWN)}


@pytest.mark.parametrize("i,l,expected", [
    (2, 2, cmp.OK), (0, 0, cmp.OK), (2, 3, cmp.DIVERGENCE), (0, 1, cmp.DIVERGENCE),
    (2, UNKNOWN, cmp.GAP), (UNKNOWN, 2, cmp.GAP), (UNKNOWN, UNKNOWN, cmp.IGNORED),
    ("yes", "yes", cmp.OK), ("yes", "no", cmp.DIVERGENCE), ("no", UNKNOWN, cmp.GAP), (UNKNOWN, "no", cmp.GAP),
])
def test_the_table_of_section_3_2_for_one_attribute(i, l, expected):
    assert compare_attribute(i, l) == expected


def test_zero_is_a_known_value_not_a_gap():
    assert compare_attribute(0, 0) == cmp.OK
    assert compare_attribute(0, UNKNOWN) == cmp.GAP
    assert compare_attribute(0, 1) == cmp.DIVERGENCE


def test_overall_verdict_order_is_divergence_then_gap_then_ok_then_all_unknown():
    assert compare(Attrs(1, 2), Attrs(1, 2)).verdict == CONFERE
    assert compare(Attrs(1, 2), Attrs(1, 3)).verdict == NAO_CONFERE
    assert compare(Attrs(1, 2), Attrs(1, UNKNOWN)).verdict == NAO_SEI
    assert compare(Attrs(1, 2), Attrs(UNKNOWN, 2)).verdict == NAO_SEI
    assert compare(Attrs(), Attrs()).verdict == NAO_SEI  # nothing known on either side
    assert compare(Attrs(1), Attrs(1)).verdict == CONFERE  # unknown on both sides does not spoil it


def test_the_result_lists_the_fields_in_the_schema_order():
    r = compare(Attrs(1, 2, 0, 1, "yes", "no"), Attrs(2, 2, UNKNOWN, 0, "yes", "yes"))
    assert r.verdict == NAO_CONFERE
    assert r.divergent == ("lower_left", "upper_right", "prosthesis")
    assert r.gaps == ("upper_left",)
    assert r.agreed == ("lower_right", "wheelchair")
    assert r.fields == r.divergent
    assert compare(Attrs(1), Attrs(UNKNOWN)).fields == ("lower_left",)
    assert compare(Attrs(1), Attrs(1)).fields == ()


def _random_attrs(rng):
    return Attrs(**{name: rng.choice(sc.DOMAINS[name]) for name in ATTRIBUTES})


def test_one_divergence_dominates_any_number_of_gaps_and_oks():
    rng = random.Random(1)
    for _ in range(300):
        image, report = _random_attrs(rng), _random_attrs(rng)
        names = [n for n in ATTRIBUTES if getattr(image, n) != UNKNOWN and getattr(report, n) != UNKNOWN]
        if not names:
            continue
        victim = rng.choice(names)
        domain = [v for v in sc.DOMAINS[victim] if v != UNKNOWN]
        forced = report.with_(**{victim: next(v for v in domain if v != getattr(image, victim))})
        assert compare(image, forced).verdict == NAO_CONFERE
        assert victim in compare(image, forced).divergent


def test_comparing_is_symmetric_deterministic_and_neutral_for_unknown_on_both_sides():
    rng = random.Random(2)
    for _ in range(500):
        a, b = _random_attrs(rng), _random_attrs(rng)
        forward, backward = compare(a, b), compare(b, a)
        assert forward.verdict == backward.verdict == compare(a, b).verdict
        assert forward.divergent == backward.divergent and forward.gaps == backward.gaps and forward.agreed == backward.agreed
        # an attribute that is `?` on both sides changes nothing: it is as if it were not compared
        name = rng.choice(ATTRIBUTES)
        a2, b2 = a.with_(**{name: UNKNOWN}), b.with_(**{name: UNKNOWN})
        rest = tuple(n for n in ATTRIBUTES if n != name)
        with_it, without_it = compare(a2, b2), compare(a2, b2, rest)
        assert with_it.verdict == without_it.verdict
        assert with_it.divergent == without_it.divergent and with_it.gaps == without_it.gaps


def test_every_pair_of_values_of_one_attribute_follows_the_table_exhaustively():
    for name in ATTRIBUTES:
        for i, l in itertools.product(sc.DOMAINS[name], repeat=2):
            got = compare(Attrs(**{name: i}), Attrs(**{name: l})).per_attribute[name]
            assert got == compare_attribute(i, l)


# ---- the output texts --------------------------------------------------------------------------

FORBIDDEN = ("elegível", "elegivel", "rejeitad", "inelegível", "classe", "aprovad", "reprovad", "decisão final")


def _texts():
    cases = [(Attrs(1, 2), Attrs(1, 2)), (Attrs(1, 2), Attrs(1, 3, 0, 1)), (Attrs(1, 2), Attrs(1)), (Attrs(), Attrs()),
             (Attrs(1, 2, 0, 1, "yes", "no"), Attrs(2, 0, UNKNOWN, 2, "no", "no"))]
    return [compare(a, b).text() for a, b in cases]


def test_the_three_texts_always_ask_for_human_review_and_never_decide():
    texts = _texts()
    assert any(t.startswith("A imagem e o laudo concordam") for t in texts)
    assert any(t.startswith("A imagem e o laudo divergem em:") for t in texts)
    assert any(t.startswith("Não foi possível conferir") for t in texts)
    for text in texts:
        assert "revisão humana" in text
        for word in FORBIDDEN:
            assert word not in text.lower()


def test_the_text_names_the_fields_that_matter():
    divergent = compare(Attrs(1, 2), Attrs(1, 3)).text()
    assert "membro inferior direito" in divergent and "membro inferior esquerdo" not in divergent
    gap = compare(Attrs(1, 2), Attrs(1)).text()
    assert "membro inferior direito" in gap
    assert compare(Attrs(), Attrs()).text().startswith("Não foi possível conferir nenhum campo")


def test_every_field_name_in_the_texts_avoids_the_forbidden_words():
    for name in cmp.FIELD_NAMES.values():
        for word in FORBIDDEN:
            assert word not in name.lower()
