"use client";

import { useId } from "react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import type { FieldDef, Values } from "@/lib/profile-schema";

type Change = (name: string, value: string | boolean | string[] | undefined) => void;

interface Props {
  field: FieldDef;
  values: Values;
  onChange: Change;
}

function Help({ id, children }: { id: string; children?: string }) {
  return children ? (
    <p id={id} className="text-xs leading-snug text-muted-foreground">
      {children}
    </p>
  ) : null;
}

function ClearButton({ onClick, show }: { onClick: () => void; show: boolean }) {
  return show ? (
    <Button type="button" variant="link" size="xs" className="h-auto p-0 text-xs" onClick={onClick}>
      Limpar
    </Button>
  ) : null;
}

export function FieldControl({ field, values, onChange }: Props) {
  const id = useId();
  const helpId = `${id}-help`;
  const value = values[field.name];

  if (field.kind === "multi") {
    const selected = Array.isArray(value) ? value : [];
    return (
      <fieldset className="space-y-2" aria-describedby={field.help ? helpId : undefined}>
        <legend className="text-sm font-medium">{field.label}</legend>
        <Help id={helpId}>{field.help}</Help>
        <div className="space-y-2">
          {field.options.map((option) => (
            <div key={option.value} className="flex items-center gap-2">
              <Checkbox
                id={`${id}-${option.value}`}
                checked={selected.includes(option.value)}
                onCheckedChange={(checked) =>
                  onChange(
                    field.name,
                    checked ? [...selected, option.value] : selected.filter((v) => v !== option.value),
                  )
                }
              />
              <Label htmlFor={`${id}-${option.value}`} className="font-normal">
                {option.label}
              </Label>
            </div>
          ))}
        </div>
      </fieldset>
    );
  }

  if (field.kind === "tri") {
    const choices = [
      { label: "Sim", value: true },
      { label: "Não", value: false },
      { label: "Não sei", value: undefined },
    ] as const;
    return (
      <div className="space-y-2" role="group" aria-labelledby={`${id}-label`} aria-describedby={field.help ? helpId : undefined}>
        <p id={`${id}-label`} className="text-sm font-medium">
          {field.label}
        </p>
        <div className="flex gap-1.5">
          {choices.map((choice) => (
            <Button
              key={choice.label}
              type="button"
              size="sm"
              variant={value === choice.value ? "default" : "outline"}
              aria-pressed={value === choice.value}
              onClick={() => onChange(field.name, choice.value)}
            >
              {choice.label}
            </Button>
          ))}
        </div>
        <Help id={helpId}>{field.help}</Help>
      </div>
    );
  }

  if (field.kind === "select") {
    const current = typeof value === "string" ? value : null;
    return (
      <div className="space-y-1.5">
        <div className="flex items-baseline justify-between gap-2">
          <Label htmlFor={id}>{field.label}</Label>
          <ClearButton show={current !== null && !field.required} onClick={() => onChange(field.name, undefined)} />
        </div>
        <Select
          value={current}
          items={field.options}
          onValueChange={(next) => onChange(field.name, next ?? undefined)}
        >
          <SelectTrigger id={id} className="w-full" aria-describedby={field.help ? helpId : undefined}>
            <SelectValue placeholder="Não informado" />
          </SelectTrigger>
          <SelectContent className="w-auto min-w-(--anchor-width) max-w-[min(32rem,90vw)]">
            {field.options.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Help id={helpId}>{field.help}</Help>
      </div>
    );
  }

  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{field.label}</Label>
      <div className="flex items-center gap-2">
        <Input
          id={id}
          type="number"
          inputMode="decimal"
          min={field.min}
          max={field.max}
          step={field.step}
          value={typeof value === "string" ? value : ""}
          aria-describedby={field.help ? helpId : undefined}
          className="max-w-40"
          onChange={(event) => onChange(field.name, event.target.value === "" ? undefined : event.target.value)}
        />
        {field.unit ? <span className="text-sm text-muted-foreground">{field.unit}</span> : null}
      </div>
      <Help id={helpId}>{field.help}</Help>
    </div>
  );
}
