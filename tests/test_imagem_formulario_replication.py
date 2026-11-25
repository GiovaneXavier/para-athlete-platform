"""The replication (second training seed) and the post-test look at the visible slice. `analysis` is numpy only; the torch test is skipped without torch."""
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "spikes"))

from imagem_formulario import analysis as an  # noqa: E402
from imagem_formulario import labels  # noqa: E402
from para_triage.consistency.schema import UNKNOWN, Attrs  # noqa: E402

# Three pictures at level 2: the first shows every limb, the second hides lower_left, the third shows every limb.
SHOWN = [Attrs(0, 0, 0, 1, "no", "no"), Attrs(UNKNOWN, 0, 0, 0, "no", "no"), Attrs(0, 2, 0, 0, "no", "yes")]


def make_y():
    return np.array([labels.encode_attrs(a, 2) for a in SHOWN])


def test_the_classical_reader_on_the_visible_slice_skips_the_hidden_limb():
    y = make_y()
    reads = [{"lower_left": 0, "lower_right": 0, "upper_left": 0, "upper_right": 1},
             {"lower_left": 3, "lower_right": 0, "upper_left": 0, "upper_right": 0},   # hidden limb: a read of 3 must not be counted at all
             {"lower_left": 0, "lower_right": 1, "upper_left": 0, "upper_right": 0}]
    hits = an.classical_visible_hits(reads, y, np.ones(3, bool))
    assert hits["lower_left"] == (2, 2)      # picture 2 is left out: only 2 pictures show lower_left
    assert hits["lower_right"] == (2, 3)     # the third read says 1, the label is 2
    assert hits["upper_right"] == (3, 3)


def test_the_constant_guess_on_the_visible_slice_ignores_hidden_labels_in_training_and_test():
    y = make_y()
    train = np.concatenate([y, y, y])        # `?` appears in a third of the lower_left labels; the visible majority is level 0
    hits = an.majority_visible_hits(train, y, np.ones(3, bool))
    assert hits["lower_left"] == (2, 2)
    assert hits["upper_right"][1] == 3


def test_the_gap_between_seeds_is_second_minus_first_in_points():
    assert an.seed_gap((90, 100), (93, 100)) == pytest.approx(3.0)
    assert an.seed_gap((1, 4), (1, 5)) == pytest.approx(-5.0)


def test_the_replication_script_is_separate_and_final_still_refuses_a_second_run():
    spikes = Path(__file__).resolve().parents[1] / "spikes" / "imagem_formulario"
    final, rep = (spikes / "final.py").read_text(encoding="utf-8"), (spikes / "replicate.py").read_text(encoding="utf-8")
    assert "Refusing to run again" in final                    # the guard of the single test run is still there
    assert "FINAL_MARKER" not in rep                           # the replication does not touch it
    assert "TAU = 0.5" in rep and "choose_tau" not in rep      # the threshold is fixed, never chosen again
    assert "Replicação, semente 1, nenhum ajuste" in rep       # the label asked for


def test_the_same_training_seed_gives_the_same_network_and_another_seed_a_different_one():
    torch = pytest.importorskip("torch")
    from imagem_formulario.net import SmallNet

    def first_weights(seed):
        torch.manual_seed(seed)
        return next(SmallNet().parameters()).detach().clone()

    assert torch.equal(first_weights(1), first_weights(1))
    assert not torch.equal(first_weights(0), first_weights(1))
