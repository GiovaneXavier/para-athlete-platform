"""image-and-report check, PR 2: synthetic reports, the rule-based reader and the planted errors (design note sections 5 and 12)."""
import itertools
import random
from collections import Counter

import pytest

from para_triage.consistency import errors as er
from para_triage.consistency import reports as rp
from para_triage.consistency.compare import CONFERE, NAO_CONFERE, NAO_SEI, compare
from para_triage.consistency.schema import LIMB_FIELDS, UNKNOWN, Attrs, level1_combinations

COMBOS = level1_combinations()
FLAGS = list(itertools.product(("yes", "no", UNKNOWN), repeat=2))
KEYWORDS = {"membro", "perna", "braço", "inferior", "superior", "esquerda", "esquerdo", "direita", "direito", "amputação", "joelho",
            "cotovelo", "punho", "pé", "cadeira", "prótese", "completo", "íntegro", "ausência", "sem", "não", "lado"}


def images(n=None):
    chosen = COMBOS if n is None else COMBOS[:: max(1, len(COMBOS) // n)]
    return [(f"img-{i:03d}", a) for i, a in enumerate(chosen)]


# ---- the reports -------------------------------------------------------------------------------


def test_the_rule_reader_recovers_the_label_from_every_clean_report_of_the_144_combinations():
    for i, attrs in enumerate(COMBOS):
        for seed in range(3):
            text = rp.render_report(rp.ReportContent(attrs), f"{i}:{seed}")
            assert rp.read_report(text) == attrs, (attrs, text)


def test_the_reader_also_recovers_chair_prosthesis_and_unknown_limbs():
    rng = random.Random(3)
    for i in range(400):
        values = {n: rng.choice((0, 1, 2) + (UNKNOWN,) * 2) for n in LIMB_FIELDS}
        values["lower_left"] = rng.choice((0, 1, 2, 3, UNKNOWN))
        values["wheelchair"], values["prosthesis"] = rng.choice(FLAGS)
        attrs = Attrs(**values)
        text = rp.render_report(rp.ReportContent(attrs), i)
        assert rp.read_report(text) == attrs, (attrs, text)


def test_a_report_with_nothing_to_say_reads_as_unknown():
    text = rp.render_report(rp.ReportContent(Attrs()), 0)
    assert text == rp.EMPTY_REPORT and rp.read_report(text) == Attrs()


def test_the_report_is_deterministic_and_varies_with_the_seed_and_the_vocabulary_is_used():
    attrs = Attrs(2, 3, 1, 0)
    assert rp.render_report(rp.ReportContent(attrs), 7) == rp.render_report(rp.ReportContent(attrs), 7)
    texts = {rp.render_report(rp.ReportContent(attrs), s) for s in range(40)}
    assert len(texts) > 20
    joined = " ".join(texts)
    for variant in ("transtibial", "abaixo do joelho", "transfemoral", "esquerdo", "esquerda", "direita", "direito", "braço", "perna"):
        assert variant in joined, variant


def test_the_noisy_report_changes_the_text_but_no_fact():
    for i, attrs in enumerate(COMBOS[::5]):
        clean = rp.render_report(rp.ReportContent(attrs), i)
        noisy = rp.render_report(rp.ReportContent(attrs), i, noisy=True)
        assert noisy != clean and len(noisy) > len(clean)
        assert rp.read_report(noisy) == attrs, (attrs, noisy)
        assert rp.render_report(rp.ReportContent(attrs), i, noisy=True) == noisy
    sample = " ".join(rp.render_report(rp.ReportContent(Attrs(2, 1, 0, 1)), s, noisy=True) for s in range(30))
    assert "MI" in sample or "MS" in sample or "esq." in sample or "dir." in sample  # abbreviations are used
    assert any(f.split()[0] in sample for f in rp.FILLER)  # irrelevant sentences are used


def test_the_irrelevant_sentences_say_nothing_about_limbs_sides_levels_chairs_or_prostheses():
    for sentence in rp.FILLER:
        assert rp.read_report(sentence) == Attrs()
        words = {w.strip(".,").lower() for w in sentence.split()}
        assert not words & KEYWORDS, words & KEYWORDS


def test_typos_never_touch_a_keyword():
    rng = random.Random(0)
    for word in sorted(rp.PROTECTED) + ["Registra-se", "Nenhuma", "intercorrência"]:
        assert rp._typo(word, rng) == word or word not in rp.PROTECTED
    assert any(rp._typo("atendimento", random.Random(s)) != "atendimento" for s in range(5))


def test_an_unsided_clause_has_unknown_labels_for_both_sides_of_its_region():
    content = rp.ReportContent(Attrs(UNKNOWN, UNKNOWN, 0, 1), {"lower": 2})
    text = rp.render_report(content, 1)
    assert rp.UNSIDED_MARKER in text
    assert rp.read_report(text) == content.attrs
    with pytest.raises(ValueError):
        rp.ReportContent(Attrs(1, UNKNOWN), {"lower": 2})  # a side is still known: it would contradict the label


def test_the_reader_splits_sentences_without_breaking_on_an_abbreviation():
    assert rp.split_sentences("Perna esq.: amputação abaixo do joelho. MS dir. completo.") == ["Perna esq.: amputação abaixo do joelho.", "MS dir. completo."]


# ---- the planted errors ------------------------------------------------------------------------


def pairs_of(attrs_list, seed=34):
    return er.build_pairs(attrs_list, seed)


def by_image(pairs):
    out = {}
    for p in pairs:
        out.setdefault(p.image_id, {})[p.kind] = p
    return out


def test_every_image_has_the_seven_pairs_in_a_fixed_order():
    items = images(36)
    pairs = pairs_of(items)
    assert len(items) == 36 and len(pairs) == 7 * 36
    assert [p.kind for p in pairs[:7]] == list(er.KINDS) and len(er.KINDS) == 7
    assert pairs_of(items) == pairs
    assert pairs_of(items, seed=35) != pairs


def test_the_expected_verdict_is_the_comparator_on_the_true_labels_and_never_written_by_hand():
    items = images()
    truth = dict(items)
    for p in pairs_of(items):
        if p.content is None:
            assert p.status == er.NOT_APPLICABLE and p.expected is None and p.text is None
        else:
            assert p.expected == compare(truth[p.image_id], p.content.attrs).verdict


def test_the_consistent_and_the_noisy_pairs_say_the_same_facts_and_expect_confere():
    items = images()
    truth = dict(items)
    for kinds in by_image(pairs_of(items)).values():
        for kind in (er.CONSISTENT, er.NOISE):
            p = kinds[kind]
            assert p.content.attrs == truth[p.image_id] and p.expected == CONFERE and p.status == er.OK
            assert rp.read_report(p.text) == truth[p.image_id]
        assert kinds[er.CONSISTENT].text != kinds[er.NOISE].text


def test_a_swapped_report_changes_exactly_the_sides():
    items = images()
    truth = dict(items)
    indistinguishable = 0
    for image_id, kinds in by_image(pairs_of(items)).items():
        p, attrs = kinds[er.SIDE_SWAP], truth[image_id]
        assert p.content.attrs == attrs.swapped_sides()
        assert rp.read_report(p.text) == attrs.swapped_sides()
        if attrs.swapped_sides() == attrs:
            assert p.status == er.INDISTINGUISHABLE and p.expected == CONFERE
            indistinguishable += 1
        else:
            assert p.status == er.OK and p.expected == NAO_CONFERE
    assert indistinguishable == 4 * 3  # both pairs of sides equal: 4 lower values x 3 upper values


def test_a_level_error_moves_exactly_one_limb_by_exactly_one_step_inside_the_domain():
    items = images()
    truth = dict(items)
    redirected = 0
    for image_id, kinds in by_image(pairs_of(items)).items():
        p, attrs = kinds[er.WRONG_LEVEL], truth[image_id]
        changed = [n for n in LIMB_FIELDS if getattr(attrs, n) != getattr(p.content.attrs, n)]
        assert len(changed) == 1 and p.expected == NAO_CONFERE and p.status == er.OK
        name = changed[0]
        assert abs(getattr(p.content.attrs, name) - getattr(attrs, name)) == 1
        assert getattr(p.content.attrs, name) in (range(4) if name.startswith("lower") else range(3))
        assert rp.read_report(p.text) == p.content.attrs
        redirected += p.note == "redirected"
    assert redirected > 0  # at the edges of the domain the rule sends the error to the neighbour, and says so


def test_a_level_error_is_not_applicable_when_no_limb_is_known():
    pairs = pairs_of([("blank", Attrs(wheelchair="yes"))])
    kinds = by_image(pairs)["blank"]
    assert kinds[er.WRONG_LEVEL].status == er.NOT_APPLICABLE and kinds[er.WRONG_LEVEL].content is None
    assert kinds[er.WRONG_REGION].status == er.NOT_APPLICABLE
    assert kinds[er.OMISSION].status == er.OK  # the chair can still be omitted


def test_a_region_error_moves_the_level_of_one_limb_to_the_other_region_of_the_same_side():
    items = images()
    truth = dict(items)
    not_applicable = []
    for image_id, kinds in by_image(pairs_of(items)).items():
        p, attrs = kinds[er.WRONG_REGION], truth[image_id]
        if p.status == er.NOT_APPLICABLE:
            not_applicable.append(attrs)
            continue
        changed = {n for n in LIMB_FIELDS if getattr(attrs, n) != getattr(p.content.attrs, n)}
        assert 1 <= len(changed) <= 2 and p.expected == NAO_CONFERE
        sides = {n.split("_")[1] for n in changed}
        regions = {n.split("_")[0] for n in changed}
        assert len(sides) == 1  # same side: the report put the level on the wrong region
        source = [n for n in changed if getattr(attrs, n) != 0 and getattr(p.content.attrs, n) == 0]
        assert source, "the limb that had a level now says none"
        assert rp.read_report(p.text) == p.content.attrs
        assert regions <= {"lower", "upper"}
    assert not_applicable == [Attrs(0, 0, 0, 0)]  # only the all-zero image has no level to move


def test_an_omission_turns_known_into_unknown_and_always_expects_nao_sei():
    items = images()
    truth = dict(items)
    notes = Counter()
    for image_id, kinds in by_image(pairs_of(items)).items():
        p, attrs = kinds[er.OMISSION], truth[image_id]
        assert p.status == er.OK and p.expected == NAO_SEI
        lost = [n for n in attrs.known() if getattr(p.content.attrs, n) == UNKNOWN]
        assert lost and all(getattr(p.content.attrs, n) == getattr(attrs, n) for n in attrs.known() if n not in lost)
        notes[p.note] += 1
        if p.note == "level_omitted":
            assert len(lost) == 1
        else:
            assert p.note == "side_omitted" and len(lost) == 2 and rp.UNSIDED_MARKER in p.text
        assert rp.read_report(p.text) == p.content.attrs
    assert set(notes) == {"level_omitted", "side_omitted"}


def test_another_persons_report_is_the_label_of_another_image_and_identical_labels_are_flagged():
    items = images()
    truth = dict(items)
    labels = set(truth.values())
    identical = 0
    for image_id, kinds in by_image(pairs_of(items)).items():
        p, attrs = kinds[er.OTHER_PERSON], truth[image_id]
        assert p.content.attrs in labels
        if p.content.attrs == attrs:
            assert p.status == er.INDISTINGUISHABLE and p.expected == CONFERE
            identical += 1
        else:
            assert p.status == er.OK and p.expected == NAO_CONFERE
    assert identical == 0  # the 144 combinations are all different from each other


def test_images_with_the_same_label_make_the_other_person_error_indistinguishable_and_it_is_counted():
    twins = [(f"t{i}", Attrs(1, 2, 0, 1)) for i in range(4)]
    kinds = by_image(pairs_of(twins))
    assert all(k[er.OTHER_PERSON].status == er.INDISTINGUISHABLE for k in kinds.values())
    assert all(k[er.SIDE_SWAP].status == er.OK for k in kinds.values())  # the sides differ in this label


def test_a_single_image_has_no_other_person_to_borrow_a_report_from():
    [kinds] = by_image(pairs_of([("only", Attrs(1, 2, 0, 1))])).values()
    assert kinds[er.OTHER_PERSON].status == er.NOT_APPLICABLE


def test_nothing_is_dropped_every_pair_is_either_usable_or_counted_apart():
    pairs = pairs_of(images())
    counts = Counter(p.status for p in pairs)
    assert sum(counts.values()) == 7 * 144
    assert counts[er.OK] + counts[er.INDISTINGUISHABLE] + counts[er.NOT_APPLICABLE] == len(pairs)
    assert counts[er.INDISTINGUISHABLE] == 12 and counts[er.NOT_APPLICABLE] == 1
    assert all(p.usable == (p.status == er.OK) for p in pairs)
