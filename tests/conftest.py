"""Fixtures shared by the experiment smoke tests."""
import pytest

from para_triage.experiments import protocol as P
from para_triage.experiments.baselines import GbConfig
from para_triage.models import TrainConfig


@pytest.fixture()
def tiny_e1(tmp_path, monkeypatch):
    from para_triage.experiments import e1

    monkeypatch.setattr(e1, "MLP_GRID", (TrainConfig(hidden=(16,), epochs=2),))
    monkeypatch.setattr(e1, "GB_GRID", (GbConfig(max_iter=3),))
    for module in ("seed_context",):
        monkeypatch.setattr(f"para_triage.experiments.{module}.MLP_GRID", e1.MLP_GRID)
        monkeypatch.setattr(f"para_triage.experiments.{module}.GB_GRID", e1.GB_GRID)
    cells = [P.CLEAN_CELL, P.DEFAULT_CELL, (1.0, 2.0)]
    e1.run_seed(0, tmp_path / "e1", cells, n_per_label=40)
    e1.aggregate(tmp_path / "e1", [0])
    return tmp_path
