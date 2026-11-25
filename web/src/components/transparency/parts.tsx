import type { ReactNode } from "react";
import { Badge } from "@/components/ui/badge";

/** Marks a block of numbers as level N1 (agreement with rule-made labels under simulated noise). */
export function EvidenceBadge() {
  return <Badge variant="secondary">Evidência N1</Badge>;
}

/**
 * A table that can scroll sideways on a narrow screen. The wrapper is focusable and named, so
 * keyboard users can scroll it (WCAG 2.2: 2.1.1, 1.4.10).
 */
export function DataTable({ label, caption, children }: { label: string; caption: ReactNode; children: ReactNode }) {
  return (
    <div
      role="region"
      aria-label={label}
      tabIndex={0}
      className="overflow-x-auto rounded-lg border focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
    >
      <table className="w-full min-w-[34rem] border-collapse text-left text-sm">
        <caption className="border-b bg-muted/40 px-3 py-2 text-left text-sm font-medium">{caption}</caption>
        {children}
      </table>
    </div>
  );
}

export function Th({ children, scope = "col", numeric = false }: { children: ReactNode; scope?: "col" | "row"; numeric?: boolean }) {
  return (
    <th scope={scope} className={"px-3 py-2 align-bottom font-medium " + (numeric ? "text-right" : "text-left")}>
      {children}
    </th>
  );
}

export function Td({ children, numeric = false }: { children: ReactNode; numeric?: boolean }) {
  return <td className={"px-3 py-2 align-top " + (numeric ? "text-right tabular-nums" : "text-left")}>{children}</td>;
}

export function Section({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section aria-labelledby={id} className="space-y-4">
      <h2 id={id} className="text-2xl font-semibold tracking-tight">
        {title}
      </h2>
      {children}
    </section>
  );
}

/** A notice box. role="note": it is static text, not a live alert. */
export function Note({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div role="note" className="space-y-1 rounded-lg border bg-card px-3 py-2 text-sm text-card-foreground">
      <p className="font-medium">{title}</p>
      <div className="space-y-2 text-foreground/85">{children}</div>
    </div>
  );
}

/** A long hash, shortened, with the full value one click away and readable by a screen reader. */
export function Hash({ value, length = 12 }: { value: string; length?: number }) {
  return (
    <details className="inline-block align-top">
      <summary className="cursor-pointer rounded-sm focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50">
        <code className="font-mono text-xs">{value.slice(0, length)}…</code>
        <span className="sr-only"> (mostrar o valor completo)</span>
      </summary>
      <code className="mt-1 block max-w-full break-all font-mono text-xs">{value}</code>
    </details>
  );
}
