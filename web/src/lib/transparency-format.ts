import type { Stat } from "./api-types";

const MISSING = "—";

function fixed(value: number, digits: number): string {
  return value.toLocaleString("pt-BR", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

/** 0.8921 -> "89,2%". */
export function pct(value: number | null | undefined, digits = 1): string {
  return value == null ? MISSING : `${fixed(value * 100, digits)}%`;
}

/** A plain number, e.g. a set size or a loss. */
export function num(value: number | null | undefined, digits = 2): string {
  return value == null ? MISSING : fixed(value, digits);
}

/** Mean of a share across seeds, with the spread in percentage points: "89,2% ± 0,2 p.p.". */
export function statPct(stat: Stat | undefined, digits = 1): string {
  if (!stat || stat.mean == null) return MISSING;
  const spread = stat.sd == null ? "" : ` ± ${fixed(stat.sd * 100, digits)} p.p.`;
  return `${pct(stat.mean, digits)}${spread}`;
}

/** Mean of a non-share number across seeds: "1,01 ± 0,01". */
export function statNum(stat: Stat | undefined, digits = 2): string {
  if (!stat || stat.mean == null) return MISSING;
  const spread = stat.sd == null ? "" : ` ± ${fixed(stat.sd, digits)}`;
  return `${fixed(stat.mean, digits)}${spread}`;
}

export function shortHash(hash: string, length = 12): string {
  return hash.slice(0, length);
}

/** "2026-10-24T15:37:11-03:00" -> "24/10/2026". */
export function dateBr(iso: string | null | undefined): string {
  if (!iso) return MISSING;
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  return match ? `${match[3]}/${match[2]}/${match[1]}` : iso;
}

export const SYSTEM_LABELS: Record<string, string> = {
  rules: "Regras",
  rules_imp: "Regras com imputação",
  gb: "Gradient boosting",
  mlp: "MLP",
  hybrid: "Híbrido (regras e MLP)",
};

export const SPLIT_LABELS: Record<string, string> = {
  row: "Divisão por linha",
  profile_by_label: "Divisão por perfil (perfis novos no teste)",
  profile: "Divisão por perfil, sem garantir os rótulos no treino",
};

export const CATEGORY_LABELS: Record<string, string> = {
  implemented: "Implementado",
  partial: "Parcial",
  provisional: "Provisório",
};
