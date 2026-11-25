"""Split modes of E1 and E7 (by row and by profile)."""
import json

import numpy as np
import pytest

from para_triage.data.generator import sample_true_profiles
from para_triage.experiments import protocol as P
from para_triage.experiments.baselines import GbConfig
from para_triage.models import TrainConfig



# --- split modes in E1 and E7 -------------------------------------------------------------------------------


def test_split_modes_cover_every_row_once_and_profile_mode_shares_no_profile():
    from para_triage.experiments import splits

    true = sample_true_profiles(n_per_label=40, seed=5)
    for mode in splits.MODES:
        split = splits.split_for(mode, true, seed=2)
        assert sum(len(v) for v in split.values()) == len(true)
        assert len(set().union(*map(set, split.values()))) == len(true)
    parts = {k: {true.profiles[i] for i in v} for k, v in splits.split_for("profile_by_label", true, 2).items()}
    assert not parts["train"] & parts["test"] and not parts["cal"] & parts["test"]
    with pytest.raises(ValueError):
        splits.split_for("random", true, 0)


def test_halves_by_profile_share_no_profile_and_by_row_are_balanced():
    from para_triage.experiments import splits

    true = sample_true_profiles(n_per_label=40, seed=5)
    pool = np.sort(np.random.default_rng(0).choice(len(true), 1200, replace=False))
    a, b = splits.halves("profile_by_label", true, pool, seed=3)
    assert len(a) + len(b) == len(pool) and not set(a) & set(b)
    assert not {true.profiles[pool[i]] for i in a} & {true.profiles[pool[i]] for i in b}
    ar, br = splits.halves("row", true, pool, seed=3)
    assert len(ar) == len(br) == len(pool) // 2 and not set(ar) & set(br)


def test_e1_and_e7_in_profile_mode_record_the_mode_and_keep_halves_apart(tmp_path, monkeypatch):
    from para_triage.experiments import e1, e7

    monkeypatch.setattr(e1, "MLP_GRID", (TrainConfig(hidden=(16,), epochs=2),))
    monkeypatch.setattr(e1, "GB_GRID", (GbConfig(max_iter=3),))
    monkeypatch.setattr(e7, "GB_GRID", e1.GB_GRID)
    cells = [P.CLEAN_CELL, P.DEFAULT_CELL, (1.0, 2.0)]
    e1.run_seed(0, tmp_path / "e1", cells, n_per_label=40, split_mode="profile_by_label")
    e1.aggregate(tmp_path / "e1", [0])
    sp = np.load(tmp_path / "e1" / "seed_0" / "split.npz")
    assert str(sp["mode"]) == "profile_by_label"
    true = sample_true_profiles(n_per_label=40, seed=0)
    assert not {true.profiles[i] for i in sp["train"]} & {true.profiles[i] for i in sp["test"]}
    e7.run_seed(0, tmp_path / "e1", tmp_path / "e7", n_splits=2, n_per_label=40, cells=cells)
    sanity = json.loads((tmp_path / "e7" / "seed_0" / "sanity.json").read_text())
    assert all(v["match"] for v in sanity.values())
