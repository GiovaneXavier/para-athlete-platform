"""E2: the mask ablation model and the thresholded hybrid."""

import numpy as np

from para_triage.experiments import e2
from para_triage.models.mlp import MaskedMLP

import torch


# --- E2 pieces ------------------------------------------------------------------------------------------------


def test_the_no_mask_model_ignores_the_mask():
    model = MaskedMLP(6, 3, (8,), 0.0, use_mask=False).eval()
    x = torch.randn(4, 6)
    same = model(x, torch.ones(4, 6)), model(x, torch.zeros(4, 6))
    assert torch.allclose(*same)
    masked = MaskedMLP(6, 3, (8,), 0.0, use_mask=True).eval()
    assert not torch.allclose(masked(x, torch.ones(4, 6)), masked(x, torch.zeros(4, 6)))


def test_thresholded_hybrid_trusts_the_rules_only_when_the_mlp_is_unsure():
    classes = np.array([11, 12])
    p = np.array([[0.95, 0.05], [0.55, 0.45], [0.2, 0.8]])
    rules = np.array([12, 12, -2])
    assert list(e2.hybrid_predictions(p, rules, classes, 0.0)) == [11, 11, 12]  # always the model
    assert list(e2.hybrid_predictions(p, rules, classes, 1.01)) == [12, 12, 12]  # rules whenever they decide
    assert list(e2.hybrid_predictions(p, rules, classes, 0.9)) == [11, 12, 12]
    y = np.array([11, 12, 12])
    # every tau from 0.6 to 0.9 gets all three right; ties go to the first (smaller) tau
    assert e2.choose_tau(p, rules, y, classes) == 0.6
