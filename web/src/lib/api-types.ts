// Mirrors src/para_triage/api/schemas.py.

export interface ProfileIn {
  impairments?: string[];
  sex?: "M" | "F";
  age?: number;
  posture?: "standing" | "seated" | "prosthesis" | "frame_runner";

  logmar_best_eye?: number;
  visual_field_deg?: number;

  iq?: number;
  adaptive_limitation?: boolean;
  onset_before_22?: boolean;

  height_cm?: number;
  longest_arm_cm?: number;

  brain_impairment_report?: boolean;
  neuro_severity?: number;
  cp_distribution?: "quadriplegia" | "triplegia" | "hemiplegia" | "diplegia";
  chair_propulsion?: number;
  transfers_independently?: boolean;
  walks_short_distances?: boolean;
  trunk_straps_needed?: boolean;

  arm_function?: number;
  trunk_function?: number;
  leg_function?: number;

  lower_left?: number;
  lower_right?: number;
  upper_left?: number;
  upper_right?: number;

  ankle_pf_mrc?: number;
  ankle_rom_deg?: number;
  leg_length_diff_cm?: number;
  hip_knee_deficit?: boolean;
  lower_limb_sides_affected?: number;
}

export type RuleStatus = "meets" | "borderline" | "needs_review";

export interface ClassOption {
  class_id: number;
  codes: string[];
  name_pt: string;
  probability: number | null;
  rule_status: RuleStatus | null;
  rule_reasons: string[];
  events: string[];
  equipment: string[];
}

export interface Triage {
  options: ClassOption[];
  p_none: number | null;
  p_ambiguous: number | null;
  rules_primary: number | null;
  rules_model_agree: boolean | null;
  flags: string[];
  /** Why the rules hand the case to a specialist (Portuguese). */
  review_notes: string[];
  missing: string[];
  facts: string[];
  model_available: boolean;
  reference_report: string;
}

export interface ReportIssue {
  kind: string;
  detail: string;
}

export interface Report {
  text: string;
  source: "llm" | "template";
  attempts: number;
  issues: ReportIssue[];
  elapsed_s: number;
  model: string | null;
}

export interface Job {
  job_id: string;
  status: "queued" | "running" | "done" | "error";
  report: Report | null;
  error: string | null;
}

export interface Health {
  status: string;
  model_loaded: boolean;
  ollama_available: boolean;
  ollama_model: string;
}

// --- Transparency panel (K11). Mirrors the transparency models of src/para_triage/api/schemas.py
// and web/public/transparency.json. Every metric is level N1 (agreement with labels produced by the
// same rules, under simulated noise): it is never called "accuracy".

export interface Stat {
  mean: number | null;
  sd: number | null;
  min: number | null;
  max: number | null;
  n: number;
}

export type Metrics = Record<string, Stat>;

export interface Source {
  commit: string | null;
  code_tree_dirty: boolean | null;
  written_at: string | null;
  n_seeds: number;
  seeds: number[];
  split_mode: string | null;
  command: string;
  python: string | null;
  torch: string | null;
  scikit_learn: string | null;
  n_per_label?: number | null;
  split?: Record<string, number> | null;
}

export interface RulesInfo {
  id: string;
  sha256: string;
  files: { path: string; sha256: string }[];
  n_classes: number;
  n_groups: number;
  id_at_source_commit: Record<string, string | null>;
  unchanged_since_runs: Record<string, boolean | null>;
}

export interface RuleGroup {
  group: string;
  classes: string;
  state: string;
  category: "implemented" | "partial" | "provisional";
  origin: string;
}

export interface Divergence {
  id: string;
  classes: number[];
  text: string;
}

export interface ChangelogEntry {
  rules_id: string;
  date: string;
  summary: string;
}

export interface ModelCard {
  file_name: string;
  sha256: string;
  size_bytes: number;
  known: boolean;
  name: string | null;
  status: string;
  protocol: string | null;
  limits: string[];
  metrics: {
    n_runs: number;
    mlp_agreement_with_rule_labels: { mean: number; std: number };
    mlp_macro_f1: { mean: number; std: number };
    evidence_level: string;
    notice: string;
  } | null;
  evidence_level: string;
  notice: string;
}

export interface E1Split {
  source: Source;
  cell: Record<string, number | string>;
  systems: Record<string, Metrics>;
  mlp_calibration: Metrics;
}

export interface Conformal {
  metrics: Metrics;
  coverage_min_over_splits: number | null;
  n_splits_total: number;
}

export interface Conditional {
  coverage: Stat;
  size: Stat;
  n_per_split: number | null;
}

export interface E7Split {
  source: Source;
  declared_before_running: Record<string, unknown> | null;
  main_alpha: number;
  calibration_cell: Record<string, number>;
  conformal: Record<string, Record<string, Conformal>>;
  coverage_by_missing_fields: Record<string, Conditional>;
  coverage_by_group: Record<string, Conditional>;
  selective: Record<string, Metrics>;
}

export interface V1Result {
  evidence_level: string;
  source: Source;
  duplicates_in_test: Metrics;
  agreement_by_duplicate_subset: Record<string, { n_test_rows: number | null; systems: Record<string, Metrics> }>;
  new_profile_splits: Record<string, { systems: Record<string, Metrics>; split: Metrics }>;
}

export interface TransparencyReport {
  schema_version: number;
  evidence_level: string;
  evidence_notice: string;
  usage_notice: string;
  rules: RulesInfo;
  rule_groups: RuleGroup[];
  known_divergences: Divergence[];
  changelog: ChangelogEntry[];
  model_card: ModelCard | null;
  experiments: {
    E1: { evidence_level: string; splits: Record<string, E1Split> };
    E7: { evidence_level: string; splits: Record<string, E7Split> };
    V1: V1Result;
  };
}

export interface ServedModel {
  file_name: string;
  sha256: string;
  size_bytes: number;
  known: boolean;
  name: string | null;
  status: string;
}

export interface TransparencyLive {
  rules_id: string;
  rules_match_report: boolean;
  served_model: ServedModel | null;
  served_model_matches_card: boolean | null;
}

export interface Transparency {
  report: TransparencyReport;
  live: TransparencyLive;
}
