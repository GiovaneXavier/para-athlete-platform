// Study mode (K2). Mirrors src/para_triage/api/education_schemas.py.
// The case types carry no answer: it only arrives with AnswerResult.
import { getJson, postJson } from "./api";

/** Fixed notice of every study-mode screen. Same text as NOTICE in education/scope.py (a test compares them). */
export const STUDY_NOTICE =
  "Material de estudo, com dados fictícios. Não ensina a classificar oficialmente. Regras do livreto do CPB (2024) em leitura nossa, ainda a validar com a especialista.";

export type GroupId = "visual" | "short_stature" | "limb_standing" | "limb_prosthesis";
export type Difficulty = "easy" | "medium" | "hard";
export type QuizDifficulty = Difficulty | "mixed";
export type ReviewStatus = "draft" | "reviewed";

export interface EduOption {
  id: string;
  label: string;
}

export interface EduFact {
  label: string;
  value: string;
}

export interface EduCase {
  case_id: string;
  group: GroupId;
  difficulty: Difficulty;
  review_status: ReviewStatus;
  notice: string;
  presentation: { summary: string; facts: EduFact[] };
  options: EduOption[];
}

export interface EduScopeGroup {
  id: GroupId;
  label: string;
  summary: string;
  classes: number[];
  warning: string | null;
  difficulties: Difficulty[];
  options: EduOption[];
}

export interface EduScope {
  notice: string;
  review_status_note: string;
  rules_version: string;
  case_version: string;
  quiz_sizes: number[];
  difficulties: { id: QuizDifficulty; label: string; hint: string }[];
  groups: EduScopeGroup[];
}

export interface EduQuiz {
  notice: string;
  seed: number;
  size: number;
  difficulty: QuizDifficulty;
  cases: EduCase[];
}

export interface TraceStep {
  criterion: string;
  reference: string;
  value: string;
  result: "met" | "not_met" | "not_assessed";
  result_label: string;
  explanation: string;
}

export interface AnswerResult {
  case_id: string;
  outcome: "correct" | "wrong" | "revealed";
  title: string;
  correct: boolean;
  answer_id: string;
  answer_label: string;
  class_name_pt: string | null;
  class_codes: string[];
  steps: TraceStep[];
  conclusion: string;
  references: string[];
  limits: string[];
  review_status: ReviewStatus;
  notice: string;
}

export const MAX_SEED = 999_999_999;

export const newSeed = () => Math.floor(Math.random() * (MAX_SEED + 1));

export const getEduScope = () => getJson<EduScope>("/api/education/scope");

export const getEduCase = (group: GroupId, difficulty: Difficulty, seed: number, index: number) =>
  getJson<EduCase>(`/api/education/case?group=${group}&difficulty=${difficulty}&seed=${seed}&index=${index}`);

export const getEduQuiz = (seed: number, size: number, groups: GroupId[], difficulty: QuizDifficulty) => {
  const params = new URLSearchParams({ seed: String(seed), size: String(size), difficulty });
  for (const group of groups) params.append("groups", group);
  return getJson<EduQuiz>(`/api/education/quiz?${params.toString()}`);
};

/** choice = null means "show me the answer". */
export const postEduAnswer = (caseId: string, choice: string | null) =>
  postJson<AnswerResult>("/api/education/answer", { case_id: caseId, choice });

export const DIFFICULTY_NAMES: Record<QuizDifficulty, string> = {
  easy: "Fácil",
  medium: "Médio",
  hard: "Difícil",
  mixed: "Misto",
};

export function parseSeed(value: string | null): number | null {
  if (value == null || !/^\d+$/.test(value)) return null;
  const seed = Number(value);
  return seed <= MAX_SEED ? seed : null;
}
