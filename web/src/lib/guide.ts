import content from "@/content/guide.json";
import type { GuideContent, GuidePage } from "./guide-types";

/** The generated guide (see src/para_triage/guide). Typed here because the JSON is written by Python. */
export const guide = content as unknown as GuideContent;

export function pageByPath(path: string): GuidePage | undefined {
  return guide.pages.find((page) => page.path === path);
}

export function pagesOfKind(kind: GuidePage["kind"]): GuidePage[] {
  return guide.pages.filter((page) => page.kind === kind);
}

/** "/guia/baixa-estatura/classe-40" -> { grupo: "baixa-estatura", classe: "classe-40" } */
export function classParams(): { grupo: string; classe: string }[] {
  return pagesOfKind("class").map((page) => {
    const [, , grupo, classe] = page.path.split("/");
    return { grupo, classe };
  });
}

export function groupParams(): { grupo: string }[] {
  return pagesOfKind("group").map((page) => ({ grupo: page.path.split("/")[2] }));
}

const NUMBER = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const INTEGER = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 });

export const formatDecimal = (value: number) => NUMBER.format(value);
export const formatInteger = (value: number) => INTEGER.format(value);
