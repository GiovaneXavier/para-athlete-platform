"""Tabular MLP that takes (values, observed-mask) and handles missing fields."""
from __future__ import annotations

import copy
from dataclasses import dataclass

import numpy as np
import torch
import torch.nn.functional as F
from torch import nn

from ..data.features import FEATURE_NAMES


class Standardizer:
    """Per-feature mean/std over observed entries only; missing entries stay at 0."""

    def fit(self, x: np.ndarray, m: np.ndarray) -> "Standardizer":
        count = np.maximum(m.sum(0), 1.0)
        self.mean = (x * m).sum(0) / count
        var = (((x - self.mean) ** 2) * m).sum(0) / count
        self.std = np.where(var > 1e-8, np.sqrt(var), 1.0)
        return self

    def transform(self, x: np.ndarray, m: np.ndarray) -> np.ndarray:
        return (((x - self.mean) / self.std) * m).astype(np.float32)


class MaskedMLP(nn.Module):
    def __init__(
        self, n_features: int, n_classes: int, hidden: tuple[int, ...] = (128, 64), dropout: float = 0.2, use_mask: bool = True
    ):
        super().__init__()
        self.use_mask = use_mask  # False hides which fields were recorded (ablation); the width stays the same
        layers: list[nn.Module] = []
        width = 2 * n_features  # values and mask side by side
        for h in hidden:
            layers += [nn.Linear(width, h), nn.BatchNorm1d(h), nn.GELU(), nn.Dropout(dropout)]
            width = h
        layers.append(nn.Linear(width, n_classes))
        self.net = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor, m: torch.Tensor) -> torch.Tensor:
        return self.net(torch.cat([x, m if self.use_mask else torch.zeros_like(m)], dim=1))


@dataclass(frozen=True)
class TrainConfig:
    hidden: tuple[int, ...] = (128, 64)
    dropout: float = 0.2
    lr: float = 2e-3
    weight_decay: float = 1e-4
    epochs: int = 80
    batch_size: int = 128
    feature_dropout: float = 0.1  # extra random masking of observed fields during training
    patience: int = 12
    seed: int = 0
    use_mask: bool = True  # ablation: False feeds the model no record of which fields are missing


# Which declared impairments are present defines the group, so they are never masked out.
_DROPPABLE = torch.tensor([not name.startswith("impairment_") for name in FEATURE_NAMES])


def fit_model(
    train: tuple[np.ndarray, np.ndarray, np.ndarray],
    val: tuple[np.ndarray, np.ndarray, np.ndarray],
    n_classes: int,
    cfg: TrainConfig,
) -> tuple[MaskedMLP, list[dict]]:
    """`train` and `val` are (x, m, y) with x already standardized."""
    torch.manual_seed(cfg.seed)
    g = torch.Generator().manual_seed(cfg.seed)
    xt, mt, yt = (torch.as_tensor(a) for a in train)
    xv, mv, yv = (torch.as_tensor(a) for a in val)

    model = MaskedMLP(xt.shape[1], n_classes, cfg.hidden, cfg.dropout, cfg.use_mask)
    opt = torch.optim.AdamW(model.parameters(), lr=cfg.lr, weight_decay=cfg.weight_decay)
    best_state, best_loss, stale, history = None, float("inf"), 0, []

    for epoch in range(cfg.epochs):
        model.train()
        order = torch.randperm(len(xt), generator=g)
        total = 0.0
        for start in range(0, len(order), cfg.batch_size):
            idx = order[start : start + cfg.batch_size]
            if len(idx) < 2:
                continue  # BatchNorm needs more than one sample
            xb, mb, yb = xt[idx], mt[idx], yt[idx]
            if cfg.feature_dropout > 0:
                drop = (torch.rand(mb.shape, generator=g) < cfg.feature_dropout) & (mb > 0) & _DROPPABLE
                mb = mb * (~drop)
                xb = xb * mb
            loss = F.cross_entropy(model(xb, mb), yb)
            opt.zero_grad()
            loss.backward()
            opt.step()
            total += loss.item() * len(idx)

        model.eval()
        with torch.no_grad():
            val_loss = F.cross_entropy(model(xv, mv), yv).item()
        history.append({"epoch": epoch, "train_loss": total / len(xt), "val_loss": val_loss})
        if val_loss < best_loss - 1e-4:
            best_loss, best_state, stale = val_loss, copy.deepcopy(model.state_dict()), 0
        else:
            stale += 1
            if stale >= cfg.patience:
                break

    model.load_state_dict(best_state)
    model.eval()
    return model, history


@torch.no_grad()
def predict_logits(model: MaskedMLP, x: np.ndarray, m: np.ndarray) -> np.ndarray:
    model.eval()
    return model(torch.as_tensor(x), torch.as_tensor(m)).numpy()


def softmax(logits: np.ndarray, temperature: float = 1.0) -> np.ndarray:
    z = logits / temperature
    z = z - z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


def fit_temperature(logits: np.ndarray, y: np.ndarray) -> float:
    """Single temperature that minimizes NLL on held-out logits."""
    lg, target = torch.as_tensor(logits), torch.as_tensor(y)
    log_t = torch.zeros(1, requires_grad=True)
    opt = torch.optim.LBFGS([log_t], lr=0.1, max_iter=100)

    def closure():
        opt.zero_grad()
        loss = F.cross_entropy(lg / log_t.exp(), target)
        loss.backward()
        return loss

    opt.step(closure)
    return float(log_t.exp().item())
