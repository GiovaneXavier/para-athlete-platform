"use client";

import { Accessibility, Brain, Eye, Footprints, Puzzle, Ruler, type LucideIcon } from "lucide-react";
import { GROUPS, type GroupDef, type GroupId } from "@/lib/profile-schema";

const ICONS: Record<GroupDef["icon"], LucideIcon> = {
  eye: Eye,
  puzzle: Puzzle,
  ruler: Ruler,
  footprints: Footprints,
  accessibility: Accessibility,
  brain: Brain,
};

export function GroupPicker({ value, onChange }: { value: GroupId; onChange: (id: GroupId) => void }) {
  return (
    <div role="group" aria-label="Tipo de comprometimento" className="grid grid-cols-1 gap-2 sm:grid-cols-2">
      {GROUPS.map((group) => {
        const Icon = ICONS[group.icon];
        const selected = group.id === value;
        return (
          <button
            key={group.id}
            type="button"
            aria-pressed={selected}
            onClick={() => onChange(group.id)}
            className={
              "flex items-start gap-3 rounded-xl border p-3 text-left transition-colors outline-none focus-visible:ring-3 focus-visible:ring-ring/50 " +
              (selected
                ? "border-primary bg-primary/5 ring-1 ring-primary"
                : "border-border bg-card hover:bg-muted/60")
            }
          >
            <Icon aria-hidden className={"mt-0.5 size-5 shrink-0 " + (selected ? "text-primary" : "text-muted-foreground")} />
            <span className="min-w-0">
              <span className="block text-sm font-medium leading-tight">{group.title}</span>
              <span className="mt-0.5 block text-xs leading-snug text-foreground/80">{group.description}</span>
            </span>
          </button>
        );
      })}
    </div>
  );
}
