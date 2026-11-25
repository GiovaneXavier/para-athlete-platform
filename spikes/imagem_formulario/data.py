"""Loads the generated sets from `paths.DATA` (numpy only)."""
from __future__ import annotations

import pickle
from dataclasses import dataclass

import numpy as np

from . import paths


@dataclass
class Split:
    level: int
    name: str
    x: np.ndarray      # (N, 200, 140, 3) uint8
    y: np.ndarray      # (N, 6) head indices of the IMAGE label (`?` where the picture does not show it; IGNORE for the flags at level 1)
    t: np.ndarray      # (N, 6) head indices of the TRUE attributes (the real level of every limb, even if hidden)
    band: np.ndarray   # (N,) 0..3 at level 2, -1 at level 1
    combo: np.ndarray  # (N,) index of the 144 combinations
    held: np.ndarray   # (N,) True if the combination was held out of training

    def __len__(self) -> int:
        return len(self.x)

    def pngs(self) -> list[bytes]:
        """The original PNG bytes (test sets only), for the classical baseline."""
        with open(paths.DATA / f"L{self.level}_{self.name}_png.pkl", "rb") as f:
            return pickle.load(f)


def load(level: int, name: str) -> Split:
    z = np.load(paths.DATA / f"L{level}_{name}.npz")
    return Split(level, name, z["x"], z["y"].astype(np.int64), z["t"].astype(np.int64), z["band"].astype(np.int64), z["combo"].astype(np.int64), z["held"])
