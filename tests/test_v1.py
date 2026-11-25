"""V1: duplicates and the split by true profile."""

import numpy as np

from para_triage.data.generator import sample_true_profiles
from para_triage.rules import Impairment, Profile



# --- V1: duplicates and the split by true profile -----------------------------------------------------------


def test_profile_split_never_puts_a_profile_in_two_parts_and_keeps_the_shares():
    from para_triage.experiments import v1

    true = sample_true_profiles(n_per_label=40, seed=5)
    split = v1.profile_split(true.profiles, true.groups, seed=0)
    n = len(true)
    assert sum(len(v) for v in split.values()) == n and len(set().union(*map(set, split.values()))) == n
    parts = {k: {true.profiles[i] for i in v} for k, v in split.items()}
    names = list(parts)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            assert not parts[a] & parts[b], f"{a} and {b} share a profile"
    assert 0.5 < len(split["train"]) / n < 0.7


def test_duplicate_flags_find_exact_repeats():
    from para_triage.experiments import v1

    a = Profile(impairments=frozenset({Impairment.VISUAL}), logmar_best_eye=1.0)
    b = Profile(impairments=frozenset({Impairment.VISUAL}), logmar_best_eye=1.1)
    flags = v1.duplicate_flags([a, a, b, b], np.array([0, 2]), np.array([1, 3]))
    assert list(flags) == [True, True]
    assert list(v1.duplicate_flags([a, b], np.array([0]), np.array([1]))) == [False]


def test_profile_split_by_label_keeps_labels_in_training_that_the_plain_split_loses():
    from para_triage.experiments import v1

    true = sample_true_profiles(n_per_label=40, seed=5)
    plain = v1.profile_split(true.profiles, true.groups, seed=1)
    by_label = v1.profile_split(true.profiles, true.groups, seed=1, labels=true.labels)

    def unseen_share(split):
        seen = set(true.labels[split["train"]].tolist())
        return np.mean([l not in seen for l in true.labels[split["test"]]])

    assert unseen_share(by_label) <= unseen_share(plain)
    parts = {k: {true.profiles[i] for i in v} for k, v in by_label.items()}
    assert not parts["train"] & parts["test"]
