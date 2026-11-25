"""Request and response models of the HTTP API."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..rules import (
    ArmFunction,
    CpDistribution,
    Impairment,
    LegFunction,
    LowerLimbLevel,
    Posture,
    Profile,
    Propulsion,
    Severity,
    Sex,
    TrunkFunction,
    UpperLimbLevel,
)


class ProfileIn(BaseModel):
    """What a professional fills in. Every field is optional: missing means "not measured"."""

    model_config = ConfigDict(extra="forbid")

    impairments: list[Impairment] = Field(default_factory=list)
    sex: Sex | None = None
    age: int | None = Field(None, ge=0, le=120)
    posture: Posture | None = None

    logmar_best_eye: float | None = Field(None, ge=-0.5, le=3.5)
    visual_field_deg: float | None = Field(None, ge=0, le=180)

    iq: int | None = Field(None, ge=20, le=160)
    adaptive_limitation: bool | None = None
    onset_before_22: bool | None = None

    height_cm: float | None = Field(None, ge=40, le=250)
    longest_arm_cm: float | None = Field(None, ge=10, le=120)

    brain_impairment_report: bool | None = None
    neuro_severity: Severity | None = None
    cp_distribution: CpDistribution | None = None
    chair_propulsion: Propulsion | None = None
    transfers_independently: bool | None = None
    walks_short_distances: bool | None = None
    trunk_straps_needed: bool | None = None

    arm_function: ArmFunction | None = None
    trunk_function: TrunkFunction | None = None
    leg_function: LegFunction | None = None

    lower_left: LowerLimbLevel | None = None
    lower_right: LowerLimbLevel | None = None
    upper_left: UpperLimbLevel | None = None
    upper_right: UpperLimbLevel | None = None

    ankle_pf_mrc: int | None = Field(None, ge=0, le=5)
    ankle_rom_deg: float | None = Field(None, ge=0, le=180)
    leg_length_diff_cm: float | None = Field(None, ge=0, le=60)
    hip_knee_deficit: bool | None = None
    lower_limb_sides_affected: int | None = Field(None, ge=1, le=2)

    def to_profile(self) -> Profile:
        data = self.model_dump()
        data["impairments"] = frozenset(self.impairments)
        return Profile(**data)


class TriageIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile: ProfileIn
    top_k: int = Field(3, ge=1, le=5)


class ReportIn(TriageIn):
    model: str | None = Field(None, description="Ollama model; defaults to the server setting")


class OptionOut(BaseModel):
    class_id: int
    codes: list[str]
    name_pt: str
    probability: float | None
    rule_status: str | None
    rule_reasons: list[str]
    events: list[str]
    equipment: list[str]


class TriageOut(BaseModel):
    options: list[OptionOut]
    p_none: float | None
    p_ambiguous: float | None
    rules_primary: int | None
    rules_model_agree: bool | None
    flags: list[str]
    review_notes: list[str]
    missing: list[str]
    facts: list[str]
    model_available: bool
    reference_report: str


class IssueOut(BaseModel):
    kind: str
    detail: str


class ReportOut(BaseModel):
    text: str
    source: str  # "llm" or "template"
    attempts: int
    issues: list[IssueOut]
    elapsed_s: float
    model: str | None


class JobOut(BaseModel):
    job_id: str
    status: Literal["queued", "running", "done", "error"]
    report: ReportOut | None = None
    error: str | None = None


class HealthOut(BaseModel):
    status: str
    model_loaded: bool
    ollama_available: bool
    ollama_model: str


# --- transparency panel (K11) -----------------------------------------------------------------------------
# Mirrors the committed web/public/transparency.json written by para_triage.transparency.export.
# Every metric is level N1: agreement with labels from the same rules, never "accuracy".


class StatOut(BaseModel):
    """One number per seed, summarised across seeds."""

    mean: float | None
    sd: float | None
    min: float | None
    max: float | None
    n: int


Metrics = dict[str, StatOut]


class SourceOut(BaseModel):
    commit: str | None
    code_tree_dirty: bool | None
    written_at: str | None
    n_seeds: int
    seeds: list[int]
    split_mode: str | None
    command: str
    python: str | None
    torch: str | None
    scikit_learn: str | None
    n_per_label: int | None = None
    split: dict[str, float] | None = None


class RuleFileOut(BaseModel):
    path: str
    sha256: str


class RulesOut(BaseModel):
    id: str
    sha256: str
    files: list[RuleFileOut]
    n_classes: int
    n_groups: int
    id_at_source_commit: dict[str, str | None]
    unchanged_since_runs: dict[str, bool | None]


class RuleGroupOut(BaseModel):
    group: str
    classes: str
    state: str
    category: Literal["implemented", "partial", "provisional"]
    origin: str


class DivergenceOut(BaseModel):
    id: str
    classes: list[int]
    text: str


class ChangelogEntryOut(BaseModel):
    rules_id: str
    date: str
    summary: str


class ModelCardOut(BaseModel):
    file_name: str
    sha256: str
    size_bytes: int
    known: bool
    name: str | None
    status: str
    protocol: str | None
    limits: list[str]
    metrics: dict | None
    evidence_level: str
    notice: str


class E1SplitOut(BaseModel):
    source: SourceOut
    cell: dict[str, float | str]
    systems: dict[str, Metrics]
    mlp_calibration: Metrics


class ConformalOut(BaseModel):
    metrics: Metrics
    coverage_min_over_splits: float | None
    n_splits_total: int


class ConditionalOut(BaseModel):
    coverage: StatOut
    size: StatOut
    n_per_split: float | None


class E7SplitOut(BaseModel):
    source: SourceOut
    declared_before_running: dict | None
    main_alpha: float
    calibration_cell: dict[str, float]
    conformal: dict[str, dict[str, ConformalOut]]
    coverage_by_missing_fields: dict[str, ConditionalOut]
    coverage_by_group: dict[str, ConditionalOut]
    selective: dict[str, Metrics]


class E1Out(BaseModel):
    evidence_level: str
    splits: dict[str, E1SplitOut]


class E7Out(BaseModel):
    evidence_level: str
    splits: dict[str, E7SplitOut]


class DuplicateSubsetOut(BaseModel):
    n_test_rows: float | None
    systems: dict[str, Metrics]


class NewProfileSplitOut(BaseModel):
    systems: dict[str, Metrics]
    split: Metrics


class V1Out(BaseModel):
    evidence_level: str
    source: SourceOut
    duplicates_in_test: Metrics
    agreement_by_duplicate_subset: dict[str, DuplicateSubsetOut]
    new_profile_splits: dict[str, NewProfileSplitOut]


class ExperimentsOut(BaseModel):
    E1: E1Out
    E7: E7Out
    V1: V1Out


class TransparencyReport(BaseModel):
    schema_version: int
    evidence_level: str
    evidence_notice: str
    usage_notice: str
    rules: RulesOut
    rule_groups: list[RuleGroupOut]
    known_divergences: list[DivergenceOut]
    changelog: list[ChangelogEntryOut]
    model_card: ModelCardOut | None
    experiments: ExperimentsOut


class ServedModelOut(BaseModel):
    file_name: str
    sha256: str
    size_bytes: int
    known: bool
    name: str | None
    status: str


class LiveOut(BaseModel):
    """What this server is running right now, to compare with the committed report."""

    rules_id: str
    rules_match_report: bool
    served_model: ServedModelOut | None
    served_model_matches_card: bool | None


class TransparencyOut(BaseModel):
    report: TransparencyReport
    live: LiveOut
