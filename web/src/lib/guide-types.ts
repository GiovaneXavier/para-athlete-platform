// Content of the class guide (K18). Mirrors what src/para_triage/guide/build.py writes to
// web/src/content/guide.json. The web only renders it: no rule logic lives here.

export interface Segment {
  t: string;
  /** Glossary term id: the text links to /guia/glossario#<id>. */
  term?: string;
}

export interface LinkCell {
  t: string;
  href: string;
}

export type Cell = string | Segment[] | LinkCell;

export interface Fact {
  label: string;
  value: string;
}

export type Block =
  | { kind: "p"; text: Segment[] }
  | { kind: "ul"; items: Segment[][] }
  | { kind: "table"; caption: string; headers: string[]; rows: Cell[][] }
  | { kind: "figure"; id: string }
  | { kind: "example"; case_id: string; summary: string; facts: Fact[]; conclusion: string }
  | { kind: "link"; href: string; label: string }
  | { kind: "cards"; items: { title: string; href: string; text: Segment[]; classes: number[] }[] }
  | { kind: "details"; summary: string; blocks: Block[] };

export interface Section {
  id: string;
  heading: string;
  blocks: Block[];
}

export interface GlossaryItem {
  id: string;
  term: string;
  definition: Segment[];
}

export interface Crumb {
  label: string;
  href: string | null;
}

export type ReviewStatus = "draft" | "reviewed";

export interface GuidePage {
  path: string;
  kind: "hub" | "group" | "class" | "glossary";
  title: string;
  intro: Segment[];
  breadcrumbs: Crumb[];
  sections: Section[];
  terms: string[];
  term_definitions: GlossaryItem[];
  review_status: ReviewStatus;
  group?: string;
  class_id?: number;
  source_page?: number;
  classes?: { class_id: number; href: string }[];
  neighbors?: { class_id: number; href: string }[];
}

export type Figure = {
  id: string;
  title: string;
  caption: Segment[];
  long: string;
  numbers: string[];
} & (
  | {
      kind: "logmar_scale";
      data: {
        axis: { min: number; max: number; ticks: number[] };
        bands: { label: string; from: number; to: number; pattern: "dots" | "cross" | "diagonal" | "vertical" }[];
      };
    }
  | { kind: "field_circles"; data: { limits: [number, number]; labels: [string, string] } }
  | { kind: "stature_measures"; data: { labels: { height: string; arm: string } } }
  | { kind: "levels_lower"; data: { marks: { level: number; label: string }[] } }
  | { kind: "levels_upper"; data: { marks: { level: number; label: string }[] } }
  | {
      kind: "pattern";
      data: {
        levels: Record<"lower_left" | "lower_right" | "upper_left" | "upper_right", number>;
        labels: Record<string, string | null>;
        prosthesis: boolean;
        show_upper: boolean;
      };
    }
);

export interface GuideContent {
  content_version: number;
  notice: string;
  rules_id: string;
  generated_on: string;
  rules_path: string;
  glossary_path: string;
  footer: string;
  freshness_warning: string;
  groups: { id: string; slug: string; title: string; href: string; classes: number[] }[];
  pages: GuidePage[];
  figures: Record<string, Figure>;
  glossary: GlossaryItem[];
}
