"""image-against-form experiment: the class table, the form simulator, the labels and the split. None of these tests needs torch.

Evidence level N1 (synthetic pictures, labels by construction)."""
import itertools
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "spikes"))

from imagem_formulario import classes, forms, labels, splits  # noqa: E402
from para_triage.consistency.schema import DOMAINS, LIMB_FIELDS, UNKNOWN, Attrs, level1_combinations  # noqa: E402


# ---- the class table equals the engine ----------------------------------------------------------


def test_the_class_table_is_the_rule_engine_on_every_decided_combination():
    pytest.importorskip("yaml")
    from imagem_formulario.make_class_table import POSTURES, engine_classes
    from para_triage.rules import RuleEngine

    engine = RuleEngine()
    for posture in POSTURES:
        for ll, lr, ul, ur in itertools.product(range(4), range(4), range(3), range(3)):
            meets, borderline = engine_classes(engine, posture, ll, lr, ul, ur)
            assert classes.TABLE.get((posture, ll, lr, ul, ur), ((), ())) == (meets, borderline), (posture, ll, lr, ul, ur)


def test_the_engine_gives_an_empty_list_when_a_limb_is_not_informed():
    """Why `undecided` is kept apart from the empty set: with a `?` the engine has no data and says nothing."""
    pytest.importorskip("yaml")
    from imagem_formulario.make_class_table import POSTURES, engine_classes
    from para_triage.rules import RuleEngine

    engine = RuleEngine()
    for posture in POSTURES:
        for ll, lr, ul, ur in itertools.product((0, 1, 2, 3, "?"), (0, 1, 2, 3, "?"), (0, 1, 2, "?"), (0, 1, 2, "?")):
            if "?" in (ll, lr, ul, ur):
                assert engine_classes(engine, posture, ll, lr, ul, ur) == ((), ())


def test_only_a_few_combinations_give_a_class_and_a_seated_person_gives_none():
    assert classes.table_size() == (27, 432)
    assert not any(key[0] == "seated" for key in classes.TABLE)
    assert classes.candidates((0, 0, 0, 1)) == frozenset({47})
    assert classes.candidates((0, 0, 0, 0)) == frozenset()  # decided, and no class: the EMPTY set
    assert classes.candidates((3, 0, 0, 0), "no", "yes") == frozenset({63})


def test_undecided_is_not_the_empty_set():
    assert classes.candidates((0, 0, "?", 1)) is None
    assert classes.candidates((0, 0, 0, 1), UNKNOWN, "no") is None  # the chair flag decides the posture
    assert classes.candidates((0, 0, 0, 1), "no", UNKNOWN) is None
    assert classes.candidates((0, 0, 0, 1), "yes", UNKNOWN) == frozenset()  # a chair settles the posture whatever the prosthesis flag says
    assert classes.posture("no", "no") == "standing" and classes.posture("no", "yes") == "prosthesis" and classes.posture("yes", "no") == "seated"


# ---- labels and the mirror -----------------------------------------------------------------------


def test_swapping_labels_swaps_the_two_sides_of_each_region_and_leaves_the_flags():
    y = labels.encode_attrs(Attrs(lower_left=3, lower_right=0, upper_left=1, upper_right=2, wheelchair="yes", prosthesis="no"), 2)
    swapped = labels.swap_labels(y)
    assert swapped == [y[1], y[0], y[3], y[2], y[4], y[5]]
    assert labels.swap_labels(swapped) == y  # an involution


def test_swapped_labels_equal_the_encoding_of_the_swapped_attributes_for_every_combination():
    for attrs in level1_combinations():
        for level in (1, 2):
            full = attrs.with_(wheelchair="no", prosthesis="yes")
            assert labels.swap_labels(labels.encode_attrs(full, level)) == labels.encode_attrs(full.swapped_sides(), level)


def test_a_hidden_limb_stays_hidden_after_the_swap_and_an_ignored_flag_stays_ignored():
    y = labels.encode_attrs(Attrs(lower_left=UNKNOWN, lower_right=2, upper_left=0, upper_right=UNKNOWN), 1)
    assert y[4] == y[5] == labels.IGNORE
    swapped = labels.swap_labels(y)
    assert labels.decode("lower_right", swapped[1]) == UNKNOWN and labels.decode("upper_left", swapped[2]) == UNKNOWN
    assert swapped[4] == swapped[5] == labels.IGNORE


# ---- the simulated form ---------------------------------------------------------------------------

TRUTH = {"lower_left": 2, "lower_right": 0, "upper_left": 1, "upper_right": 1, "wheelchair": "no", "prosthesis": "yes"}


def test_a_form_without_blanks_or_mistakes_is_the_truth_and_is_always_the_same():
    assert forms.make_form(TRUTH, 0.0, 0.0, "a") == TRUTH
    assert forms.make_form(TRUTH, 0.3, 0.1, "a") == forms.make_form(TRUTH, 0.3, 0.1, "a")
    assert forms.make_form(TRUTH, 0.3, 0.1, "a") != forms.make_form(TRUTH, 0.3, 0.1, "b") or forms.make_form(TRUTH, 0.3, 0.1, "c") != forms.make_form(TRUTH, 0.3, 0.1, "a")


def test_the_rates_of_blank_and_wrong_fields_are_the_ones_asked_for():
    n, blank, wrong, fields = 4000, 0, 0, 0
    for i in range(n):
        f = forms.make_form(TRUTH, 0.30, 0.10, f"k{i}")
        blank += sum(f[name] == UNKNOWN for name in labels.HEADS)
        wrong += sum(f[name] not in (UNKNOWN, TRUTH[name]) for name in labels.LIMBS)
        fields += 1
    assert abs(blank / (fields * 6) - 0.30) < 0.02
    # a limb is wrong with probability 0.10 and then it may also be blanked (0.30): wrong and shown = 0.10 * 0.70
    assert abs(wrong / (fields * 4) - 0.10 * 0.70) < 0.01


def test_a_mistake_always_changes_the_value_and_stays_in_the_domain():
    for i in range(500):
        f = forms.make_form(TRUTH, 0.0, 1.0, f"m{i}")
        for name in labels.LIMBS:
            assert f[name] != TRUTH[name] and f[name] in DOMAINS[name] and f[name] != UNKNOWN
        assert forms.has_error(f, TRUTH)
    assert not forms.has_error(forms.make_form(TRUTH, 1.0, 0.0, "x"), TRUTH)  # a blank is not a mistake


def test_there_are_twelve_cells():
    assert len(forms.CELLS) == 12 and {m for m, _ in forms.CELLS} == {0.0, 0.1, 0.3, 0.5} and {e for _, e in forms.CELLS} == {0.0, 0.05, 0.1}


# ---- the split ---------------------------------------------------------------------------------------


def test_twelve_combinations_are_held_out_and_every_limb_value_stays_in_the_seen_ones():
    held, seen = set(splits.held_out_indices()), set(splits.seen_indices())
    assert len(held) == 12 and not held & seen and len(held | seen) == 144
    combos = splits.combos()
    for field in LIMB_FIELDS:
        assert {getattr(combos[i], field) for i in seen} == {getattr(c, field) for c in combos}


def test_held_out_combinations_appear_only_in_the_test_set_and_the_sizes_are_the_planned_ones():
    held = set(splits.held_out_indices())
    for level in (1, 2):
        for name in ("train", "dev", "test"):
            its = splits.items(level, name)
            assert len(its) == {"train": 6000, "dev": 1000, "test": 2000}[name]
            in_held = {c for c, _, _, h in its if c in held}
            assert all(h == (c in held) for c, _, _, h in its)
            assert (len(in_held) > 0) == (name == "test")
            if name == "test":
                assert sum(h for *_, h in its) == 500


def test_the_seeds_are_disjoint_and_differ_from_imagem_laudo():
    assert len(set(splits.SEEDS.values())) == 3 and 34 not in splits.SEEDS.values()


def test_every_combination_meets_every_pose_and_every_band():
    poses, bands = {}, {}
    for c, band, index, _ in splits.items(1, "train"):
        poses.setdefault(c, set()).add(index % 3)
    for c, band, index, _ in splits.items(2, "train"):
        bands.setdefault(c, set()).add(band)
    assert all(p == {0, 1, 2} for p in poses.values()) and all(b == {0, 1, 2, 3} for b in bands.values())


def test_no_picture_is_shared_between_the_sets():
    """Renders a few pictures of each set (same combination, same index) and checks that no pixel array repeats."""
    from imagem_formulario.make_data import render_item

    seen = splits.seen_indices()
    keys = set()
    for level in (1, 2):
        for name in ("train", "dev", "test"):
            for item in [(seen[0], -1 if level == 1 else 0, 0, False), (seen[1], -1 if level == 1 else 1, 1, False)]:
                x = render_item((level, name, item))[0]
                key = (level, x.tobytes())
                assert key not in keys, "the same picture appears in two sets"
                keys.add(key)


def test_the_spike_folder_holds_code_and_text_only():
    out = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "spikes/imagem_formulario"], capture_output=True, text=True, cwd=ROOT)
    if out.returncode != 0:
        pytest.skip("not a git checkout")
    files = [ROOT / line for line in out.stdout.splitlines() if line]
    assert files and {p.suffix for p in files} <= {".py", ".md", ".txt"}
    assert all(p.stat().st_size < 100_000 for p in files)
    src = ROOT / "src" / "para_triage"
    assert not any("imagem_formulario" in p.read_text(encoding="utf-8") for p in src.rglob("*.py")), "the package must not know the spike"
