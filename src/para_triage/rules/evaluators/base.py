"""Helpers shared by the group evaluators."""
from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

from ..catalog import ClassSpec
from ..schema import Posture, Profile, Status, Verdict

_PRIORITY = (
    Status.MEETS,
    Status.BORDERLINE,
    Status.NEEDS_REVIEW,
    Status.INSUFFICIENT_DATA,
    Status.NOT_MET,
    Status.NOT_IMPLEMENTED,
    Status.NOT_APPLICABLE,
)


def uniform(
    specs: Iterable[ClassSpec], status: Status, reason: str, missing: Sequence[str] = ()
) -> dict[int, Verdict]:
    return {s.class_id: Verdict(s.class_id, status, (reason,), tuple(missing)) for s in specs}


def resolve(
    specs: Iterable[ClassSpec],
    meets: Mapping[int, str] | None = None,
    borderline: Mapping[int, str] | None = None,
    default_reason: str = "criteria not met",
    missing: Sequence[str] = (),
) -> dict[int, Verdict]:
    meets, borderline = meets or {}, borderline or {}
    out = {}
    for s in specs:
        cid = s.class_id
        if cid in meets:
            out[cid] = Verdict(cid, Status.MEETS, (meets[cid],), tuple(missing))
        elif cid in borderline:
            out[cid] = Verdict(cid, Status.BORDERLINE, (borderline[cid],), tuple(missing))
        else:
            out[cid] = Verdict(cid, Status.NOT_MET, (default_reason,), tuple(missing))
    return out


def merge(results: Sequence[Mapping[int, Verdict]]) -> dict[int, Verdict]:
    """Per class, keep the best verdict across alternative pathways."""
    out: dict[int, Verdict] = {}
    for result in results:
        for cid, verdict in result.items():
            current = out.get(cid)
            if current is None or _PRIORITY.index(verdict.status) < _PRIORITY.index(current.status):
                out[cid] = verdict
            elif verdict.status == current.status:
                out[cid] = Verdict(
                    cid,
                    current.status,
                    current.reasons + tuple(r for r in verdict.reasons if r not in current.reasons),
                    current.missing,
                )
    return out


def posture_gate(
    profile: Profile, specs: Sequence[ClassSpec], required: Posture, reason: str
) -> dict[int, Verdict] | None:
    """Returns verdicts when the posture rules the group out or is unknown, else None."""
    if profile.posture is None:
        return uniform(specs, Status.INSUFFICIENT_DATA, "competition posture not provided", ("posture",))
    if profile.posture is not required:
        return uniform(specs, Status.NOT_MET, reason)
    return None
