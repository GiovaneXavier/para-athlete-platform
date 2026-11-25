"""Read-only provenance of what the platform serves: the rule book id and the checkpoint hash.

Nothing here writes to, or changes the behaviour of, `rules/` or `models/`.
"""
from .checkpoint import KNOWN_CHECKPOINTS, CheckpointInfo, checkpoint_info, file_sha256
from .evidence import EVIDENCE_LEVEL, EVIDENCE_NOTICE
from .rules_version import RulesVersion, rules_version, rules_version_from_contents

__all__ = [
    "EVIDENCE_LEVEL",
    "EVIDENCE_NOTICE",
    "KNOWN_CHECKPOINTS",
    "CheckpointInfo",
    "RulesVersion",
    "checkpoint_info",
    "file_sha256",
    "rules_version",
    "rules_version_from_contents",
]
