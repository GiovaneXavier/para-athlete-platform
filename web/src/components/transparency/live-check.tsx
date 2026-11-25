"use client";

import useSWR from "swr";
import { Badge } from "@/components/ui/badge";
import type { Transparency } from "@/lib/api-types";
import { getTransparency } from "@/lib/api";
import { shortHash } from "@/lib/transparency-format";

function Verdict({ ok, yes, no }: { ok: boolean; yes: string; no: string }) {
  // The words carry the meaning; the dot is decoration (nothing is conveyed by colour alone).
  return (
    <Badge variant={ok ? "secondary" : "destructive"} className="gap-1.5">
      <span aria-hidden className={"size-1.5 rounded-full " + (ok ? "bg-emerald-600" : "bg-rose-600")} />
      {ok ? yes : no}
    </Badge>
  );
}

function modelLine(data: Transparency) {
  const served = data.live.served_model;
  if (!served) return <>Nenhum modelo carregado: a triagem usa só as regras.</>;
  const matches = data.live.served_model_matches_card;
  return (
    <>
      Modelo servido: <code className="font-mono text-xs">{shortHash(served.sha256)}…</code>{" "}
      {matches == null ? (
        <Badge variant="outline">Sem ficha para comparar</Badge>
      ) : (
        <Verdict ok={matches} yes="É o modelo da ficha" no="Não é o modelo da ficha" />
      )}
    </>
  );
}

/** Compares the committed report with what the API is running now. Optional: the page works without it. */
export function LiveCheck() {
  const { data, error, isLoading } = useSWR<Transparency>("/api/transparency", () => getTransparency(), {
    revalidateOnFocus: false,
    shouldRetryOnError: false,
  });

  return (
    <div role="status" aria-live="polite" className="space-y-2 rounded-lg border bg-card p-3 text-sm">
      <p className="font-medium">Verificação ao vivo</p>
      {isLoading ? (
        <p className="text-foreground/85">Consultando a API…</p>
      ) : error || !data ? (
        <p className="text-foreground/85">
          A API não respondeu, então não foi possível conferir o que está em uso agora. Os números desta página vêm do arquivo
          versionado e continuam valendo.
        </p>
      ) : (
        <ul className="space-y-1.5">
          <li>
            Regras servidas: <code className="font-mono text-xs">{data.live.rules_id}</code>{" "}
            <Verdict ok={data.live.rules_match_report} yes="Igual ao relatório" no="Diferente do relatório" />
          </li>
          <li>{modelLine(data)}</li>
        </ul>
      )}
    </div>
  );
}
