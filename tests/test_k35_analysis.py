"""K35: the arithmetic of the comparison on a small table that can be checked by hand (no torch)."""
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "spikes"))

from k35 import analysis as an  # noqa: E402
from k35 import labels  # noqa: E402
from para_triage.consistency.schema import UNKNOWN, Attrs  # noqa: E402

# Four pictures at level 2. The true attributes and what the picture shows (`?` where hidden):
#   0: one arm short (class 47), picture shows it            -> class {47}
#   1: same person, but the short arm is HIDDEN in the picture -> the picture cannot give the class
#   2: nobody short, standing                                  -> decided, empty class
#   3: one leg short with a prosthesis (class 64: lower_right=2 with prosthesis)
TRUE = [Attrs(0, 0, 0, 1, "no", "no"), Attrs(0, 0, 0, 1, "no", "no"), Attrs(0, 0, 0, 0, "no", "no"), Attrs(0, 2, 0, 0, "no", "yes")]
SHOWN = [Attrs(0, 0, 0, 1, "no", "no"), Attrs(0, 0, 0, UNKNOWN, "no", "no"), Attrs(0, 0, 0, 0, "no", "no"), Attrs(0, 2, 0, 0, "no", "yes")]


class SmallSplit(SimpleNamespace):
    def __len__(self):
        return len(self.t)


def make_split():
    return SimpleNamespace(name="small", t=np.array([labels.encode_attrs(a, 2) for a in TRUE]), y=np.array([labels.encode_attrs(a, 2) for a in SHOWN]),
                           band=np.array([0, 1, 2, 3]), held=np.zeros(4, bool))


def test_the_image_arm_never_gets_the_class_of_a_hidden_limb_and_counts_it_as_undecided():
    split = make_split()
    idx = split.y.copy()  # a perfect network: it says exactly what the picture shows
    arm = an.class_arms(split, idx, 2, np.ones(4, bool))
    assert (arm["n"], arm["ok"], arm["undecided"]) == (4, 3, 1)  # picture 1 is undecided: the true class {47} is out of reach by construction
    assert (arm["n_nonempty"], arm["ok_nonempty"]) == (3, 2)     # three true classes are not empty; two are reached
    hits = an.attribute_hits(idx, split.y, np.ones(4, bool))
    assert hits["upper_right"] == (4, 4) and all(k == n for k, n in hits.values())


def test_the_form_without_blanks_or_mistakes_is_the_ceiling():
    split = make_split()
    idx = split.y.copy()
    conf = np.ones(idx.shape)
    grid = an.form_grid(split, idx, conf, 2, np.ones(4, bool), 0.5, cells=[(0.0, 0.0)])[(0.0, 0.0)]
    assert grid["form_ok"] == 4 and grid["form_undecided"] == 0
    assert grid["fusion_ok"] == 4 and grid["fusion_review"] == 0


def test_the_fusion_fills_a_blank_with_a_sure_network_and_asks_for_review_on_a_disagreement():
    truth = {"lower_left": 0, "lower_right": 2, "upper_left": 0, "upper_right": 0, "wheelchair": "no", "prosthesis": "no"}
    net_row = [labels.encode(n, truth[n]) for n in labels.HEADS]
    sure, unsure = np.ones(6), np.full(6, 0.4)
    blank = dict(truth, lower_right=UNKNOWN)
    merged, review = an.fuse(blank, net_row, sure, 2, 0.9)
    assert merged == truth and not review                      # the network fills the blank
    merged, review = an.fuse(blank, net_row, unsure, 2, 0.9)
    assert merged["lower_right"] == UNKNOWN and not review      # not sure enough: stays blank
    wrong = dict(truth, lower_right=3)
    merged, review = an.fuse(wrong, net_row, sure, 2, 0.9)
    assert merged["lower_right"] == 3 and review                # both have a value and they differ: REVIEW
    merged, review = an.fuse(wrong, net_row, unsure, 2, 0.9)
    assert not review                                           # an unsure network does not contradict the form


def test_the_fusion_never_trusts_a_network_that_says_not_visible():
    truth = {"lower_left": 0, "lower_right": 2, "upper_left": 0, "upper_right": 0, "wheelchair": "no", "prosthesis": "no"}
    net_row = [labels.encode(n, UNKNOWN if n == "lower_right" else truth[n]) for n in labels.HEADS]
    merged, review = an.fuse(dict(truth), net_row, np.ones(6), 2, 0.5)
    assert merged == truth and not review


def test_wilson_and_the_interval_text():
    assert an.interval(0, 0).startswith("n/a")
    assert an.interval(50, 100).startswith("50.0% (50/100; 40.4 a 59.6")


def test_calibration_of_a_network_that_is_always_right_and_always_sure_is_zero():
    idx = np.zeros((10, 6), int)
    err = an.calibration(idx, np.ones((10, 6)), idx, np.ones(10, bool))
    assert err["ece"] == 0.0 and err["accuracy"] == 1.0
    overconfident = an.calibration(idx, np.ones((10, 6)), np.ones((10, 6), int), np.ones(10, bool))
    assert abs(overconfident["ece"] - 1.0) < 1e-9


def test_the_constant_guess_is_the_most_common_training_label():
    train_y = np.array([[0, 0, 0, 0, 1, 1]] * 3 + [[1, 0, 0, 0, 1, 1]])
    y = np.array([[0, 0, 0, 0, 1, 1], [1, 0, 0, 0, 1, 1]])
    assert an.majority_hits(train_y, y, np.ones(2, bool))["lower_left"] == (1, 2)


def test_choose_tau_runs_on_a_small_split_and_returns_one_of_the_candidates():
    # regression: `choose_tau` reads keys that `form_grid` must return (one was missing in the first dev report)
    split = make_split()
    split = SmallSplit(**vars(split))
    idx = split.y.copy()
    tau, scores = an.choose_tau({2: (split, idx, np.ones(idx.shape))}, candidates=(0.5, 0.9))
    assert tau in (0.5, 0.9) and set(scores) == {0.5, 0.9} and all(0.0 <= v <= 1.0 for v in scores.values())
