"""Synthetic profile generation driven by the rule engine."""
from .features import FEATURE_NAMES, encode_profiles
from .generator import ABSTAIN, AMBIGUOUS, NONE_ELIGIBLE, generate_dataset
from .noise import NoiseConfig, observe
from .records import profile_to_record, record_to_profile

__all__ = [
    "ABSTAIN",
    "AMBIGUOUS",
    "FEATURE_NAMES",
    "NONE_ELIGIBLE",
    "NoiseConfig",
    "encode_profiles",
    "generate_dataset",
    "observe",
    "profile_to_record",
    "record_to_profile",
]
