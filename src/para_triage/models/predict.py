"""Load a trained checkpoint and predict class probabilities for profiles."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch

from ..data.features import FEATURE_NAMES, encode_profiles
from ..rules import Profile
from .mlp import MaskedMLP, Standardizer, predict_logits, softmax


@dataclass
class Predictor:
    model: MaskedMLP
    scaler: Standardizer
    classes: np.ndarray  # label values: class ids, 0 = none eligible, -1 = ambiguous
    temperature: float

    @classmethod
    def load(cls, path: str | Path) -> "Predictor":
        # The checkpoint is written by models.train and holds numpy arrays, so the
        # weights-only loader cannot read it. Only load checkpoints you trained.
        ckpt = torch.load(path, map_location="cpu", weights_only=False)
        cfg = ckpt["config"]
        model = MaskedMLP(len(FEATURE_NAMES), len(ckpt["classes"]), tuple(cfg["hidden"]), cfg["dropout"], cfg.get("use_mask", True))
        model.load_state_dict(ckpt["state_dict"])
        model.eval()
        scaler = Standardizer()
        scaler.mean, scaler.std = ckpt["mean"], ckpt["std"]
        return cls(model, scaler, np.asarray(ckpt["classes"]), float(ckpt["temperature"]))

    def predict_proba(self, profiles: Sequence[Profile]) -> np.ndarray:
        x, m = encode_profiles(profiles)
        logits = predict_logits(self.model, self.scaler.transform(x, m), m)
        return softmax(logits, self.temperature)
