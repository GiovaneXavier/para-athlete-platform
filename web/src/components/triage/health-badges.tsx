"use client";

import useSWR from "swr";
import { Badge } from "@/components/ui/badge";
import type { Health } from "@/lib/api-types";
import { getJson } from "@/lib/api";

const fetchHealth = (url: string) => getJson<Health>(url);

function Dot({ ok }: { ok: boolean }) {
  return <span aria-hidden className={"size-1.5 rounded-full " + (ok ? "bg-emerald-500" : "bg-rose-500")} />;
}

export function HealthBadges() {
  const { data, error, isLoading } = useSWR<Health>("/api/health", fetchHealth, {
    refreshInterval: 30_000,
    errorRetryInterval: 4_000,
    revalidateOnFocus: false,
  });

  if (isLoading) return <span className="text-xs text-muted-foreground">Verificando o servidor…</span>;
  if (error || !data) {
    return (
      <Badge variant="outline" className="gap-1.5">
        <Dot ok={false} />
        Servidor da API fora do ar
      </Badge>
    );
  }
  return (
    <div className="flex flex-wrap gap-1.5">
      <Badge variant="outline" className="gap-1.5">
        <Dot ok />
        API conectada
      </Badge>
      <Badge variant="outline" className="gap-1.5">
        <Dot ok={data.model_loaded} />
        {data.model_loaded ? "Modelo carregado" : "Só regras (sem modelo)"}
      </Badge>
      <Badge variant="outline" className="gap-1.5">
        <Dot ok={data.ollama_available} />
        {data.ollama_available ? `LLM: ${data.ollama_model}` : "LLM indisponível"}
      </Badge>
    </div>
  );
}
