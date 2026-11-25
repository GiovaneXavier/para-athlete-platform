"""The small convolutional network (about 1 M parameters) and the mirror augmentation. Needs torch."""
from __future__ import annotations

import ctypes
import os
from ctypes import wintypes

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from .labels import HEADS, IGNORE, N_CLASSES, SWAP_INDEX

INPUT_HW = (200, 140)


class SmallNet(nn.Module):
    """Five blocks of conv3x3 + batch norm + ReLU + 2x2 max pool, then the last map (6 x 4 x 128) is FLATTENED (not averaged), so the
    position in the picture survives and the left of the picture can be told from the right. One shared layer, six heads."""

    def __init__(self, width=(16, 32, 64, 96, 128), hidden: int = 256, dropout: float = 0.3):
        super().__init__()
        layers, c = [], 3
        for w in width:
            layers += [nn.Conv2d(c, w, 3, padding=1, bias=False), nn.BatchNorm2d(w), nn.ReLU(inplace=True), nn.MaxPool2d(2)]
            c = w
        self.features = nn.Sequential(*layers)
        h, wd = INPUT_HW
        for _ in width:
            h, wd = h // 2, wd // 2
        self.neck = nn.Sequential(nn.Flatten(), nn.Dropout(dropout), nn.Linear(c * h * wd, hidden), nn.ReLU(inplace=True), nn.Dropout(dropout))
        self.heads = nn.ModuleList([nn.Linear(hidden, N_CLASSES[name]) for name in HEADS])

    def forward(self, x):
        z = self.neck(self.features(x))
        return [head(z) for head in self.heads]


def parameter_count(model: nn.Module) -> int:
    return sum(p.numel() for p in model.parameters())


def to_tensor(x_uint8: np.ndarray) -> torch.Tensor:
    """(N, H, W, 3) uint8 -> (N, 3, H, W) float in [-0.5, 0.5]."""
    return torch.from_numpy(x_uint8).permute(0, 3, 1, 2).float().div_(255.0).sub_(0.5)


def mirror_batch(x: torch.Tensor, y: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    """The picture reflected left to right AND the label with the person's two sides swapped (flags unchanged).
    x: (N, 3, H, W); y: (N, 6) head indices."""
    return x.flip(-1), y[:, list(SWAP_INDEX)]


def loss_fn(logits: list[torch.Tensor], y: torch.Tensor) -> torch.Tensor:
    """Cross entropy summed over the six heads and divided by the number of labels that count (IGNORE takes no loss)."""
    total, count = logits[0].new_zeros(()), 0
    for i, out in enumerate(logits):
        total = total + F.cross_entropy(out, y[:, i], ignore_index=IGNORE, reduction="sum")
        count += int((y[:, i] != IGNORE).sum())
    return total / max(count, 1)


@torch.no_grad()
def predict(model: nn.Module, x: np.ndarray, batch: int = 256, flip: bool = False) -> list[np.ndarray]:
    """Softmax probabilities of the six heads, as numpy arrays (N, classes). With `flip` the picture is reflected first and the
    heads of the two sides are put back in the person's own order (so the result is the reading of the reflected picture, swapped back)."""
    model.eval()
    outs: list[list[np.ndarray]] = [[] for _ in HEADS]
    for start in range(0, len(x), batch):
        xb = to_tensor(x[start:start + batch])
        if flip:
            xb = xb.flip(-1)
        logits = model(xb)
        for i, o in enumerate(logits):
            outs[i].append(F.softmax(o, dim=1).numpy())
    probs = [np.concatenate(o) for o in outs]
    return [probs[j] for j in SWAP_INDEX] if flip else probs  # SWAP_INDEX is its own inverse


class _Counters(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t), ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]


def peak_memory_mb() -> float:
    """Peak working set of this process in MB (Windows); 0.0 elsewhere."""
    if os.name != "nt":
        return 0.0
    counters = _Counters()
    counters.cb = ctypes.sizeof(counters)
    kernel32, psapi = ctypes.WinDLL("kernel32"), ctypes.WinDLL("psapi")
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(_Counters), wintypes.DWORD]
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
    if not psapi.GetProcessMemoryInfo(kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
        return 0.0
    return counters.PeakWorkingSetSize / 1e6
