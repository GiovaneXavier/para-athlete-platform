"use client";

import { LoaderCircle, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { FieldControl } from "@/components/triage/field-controls";
import { visibleFields, type GroupDef, type Values } from "@/lib/profile-schema";

interface Props {
  group: GroupDef;
  values: Values;
  onChange: (name: string, value: string | boolean | string[] | undefined) => void;
  useLlm: boolean;
  onUseLlmChange: (next: boolean) => void;
  onSubmit: () => void;
  pending: boolean;
  problem: string | null;
}

export function ProfileForm({ group, values, onChange, useLlm, onUseLlmChange, onSubmit, pending, problem }: Props) {
  return (
    <form
      className="space-y-5"
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit();
      }}
    >
      {group.sections.map((section, index) => {
        const fields = visibleFields(section, values);
        if (fields.length === 0) return null;
        return (
          <section key={section.title ?? index} className="space-y-4">
            {index > 0 ? <Separator /> : null}
            {section.title ? (
              <div className="space-y-1">
                <h2 className="text-sm font-semibold">{section.title}</h2>
                {section.description ? <p className="text-xs text-muted-foreground">{section.description}</p> : null}
              </div>
            ) : section.description ? (
              <p className="text-xs text-muted-foreground">{section.description}</p>
            ) : null}
            <div className="grid gap-4 sm:grid-cols-2">
              {fields.map((field) => (
                <div key={field.name} className={field.kind === "multi" ? "sm:col-span-2" : undefined}>
                  <FieldControl field={field} values={values} onChange={onChange} />
                </div>
              ))}
            </div>
          </section>
        );
      })}

      <Separator />
      <div className="flex items-center justify-between gap-3">
        <div className="space-y-0.5">
          <Label htmlFor="use-llm">Relatório com LLM</Label>
          <p className="text-xs text-muted-foreground">Leva alguns minutos. Sem ele, o relatório de referência sai na hora.</p>
        </div>
        <Switch id="use-llm" checked={useLlm} onCheckedChange={onUseLlmChange} />
      </div>

      <div className="space-y-2">
        <Button type="submit" size="lg" className="w-full" disabled={pending || problem !== null}>
          {pending ? (
            <LoaderCircle aria-hidden className="animate-spin" data-icon="inline-start" />
          ) : (
            <Search aria-hidden data-icon="inline-start" />
          )}
          {pending ? "Analisando…" : "Analisar perfil"}
        </Button>
        {problem ? <p className="text-center text-xs text-muted-foreground">{problem}</p> : null}
      </div>
    </form>
  );
}
