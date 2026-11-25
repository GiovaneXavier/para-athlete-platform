import { CircleCheck, Info, TriangleAlert } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import type { ClassOption, RuleStatus, Triage } from "@/lib/api-types";

const pct = (p: number) => Math.round(p * 100);

const STATUS: Record<RuleStatus, { label: string; className: string }> = {
  meets: { label: "Atende aos critérios", className: "bg-emerald-100 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-200" },
  borderline: { label: "Caso limítrofe", className: "bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-200" },
  needs_review: { label: "Avaliação de especialista", className: "bg-rose-100 text-rose-900 dark:bg-rose-950 dark:text-rose-200" },
};

function StatusBadge({ status }: { status: RuleStatus }) {
  const { label, className } = STATUS[status];
  return <Badge className={className}>{label}</Badge>;
}

function ProbabilityBar({ label, value }: { label: string; value: number }) {
  return (
    <div className="space-y-1">
      <div className="flex items-baseline justify-between text-xs text-muted-foreground">
        <span>{label}</span>
        <span className="tabular-nums">{pct(value)}%</span>
      </div>
      <Progress value={pct(value)} aria-label={`${label}: ${pct(value)}%`} />
    </div>
  );
}

function ClassCard({ option, rank }: { option: ClassOption; rank: number }) {
  return (
    <Card size="sm" className={rank === 0 ? "ring-2 ring-primary/40" : undefined}>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle className="flex flex-wrap items-center gap-2">
            <span className="text-lg font-semibold tracking-tight">{option.codes.join(" / ")}</span>
            {rank === 0 ? <Badge variant="outline">Mais provável</Badge> : null}
          </CardTitle>
          {option.rule_status ? <StatusBadge status={option.rule_status} /> : null}
        </div>
        <p className="text-sm text-muted-foreground">{option.name_pt}</p>
      </CardHeader>
      <CardContent className="space-y-3">
        {option.probability !== null ? <ProbabilityBar label="Probabilidade estimada" value={option.probability} /> : null}
        <dl className="grid gap-3 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Provas</dt>
            <dd>
              <ul className="mt-1 space-y-0.5">
                {option.events.map((event) => (
                  <li key={event}>{event}</li>
                ))}
              </ul>
            </dd>
          </div>
          <div>
            <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Equipamentos</dt>
            <dd className="mt-1">{option.equipment.length > 0 ? option.equipment.join(", ") : "Nenhum específico"}</dd>
          </div>
        </dl>
      </CardContent>
    </Card>
  );
}

function Summary({ triage }: { triage: Triage }) {
  const top = triage.options[0];
  const ambiguousLed =
    top !== undefined && top.probability !== null && triage.p_ambiguous !== null && triage.p_ambiguous > top.probability;

  if (top === undefined && triage.review_notes.length > 0) {
    return (
      <Alert className="border-amber-300 bg-amber-50 dark:bg-amber-950/30">
        <TriangleAlert aria-hidden />
        <AlertTitle>Caso para avaliação de especialista</AlertTitle>
        <AlertDescription>
          As regras da cartilha não decidem este caso:
          <ul className="mt-1 list-disc pl-4">
            {triage.review_notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
          Leve o atleta a um classificador do CPB.
        </AlertDescription>
      </Alert>
    );
  }
  if (top === undefined) {
    return (
      <Alert>
        <Info aria-hidden />
        <AlertTitle>Nenhuma classe elegível identificada</AlertTitle>
        <AlertDescription>Com os dados informados, não foi possível indicar uma classe. Revise os campos preenchidos.</AlertDescription>
      </Alert>
    );
  }
  if (ambiguousLed) {
    return (
      <Alert className="border-amber-300 bg-amber-50 dark:bg-amber-950/30">
        <TriangleAlert aria-hidden />
        <AlertTitle>Perfil limítrofe</AlertTitle>
        <AlertDescription>
          O modelo estima {pct(triage.p_ambiguous as number)}% de chance de caso ambíguo. A decisão entre{" "}
          {triage.options.map((o) => o.codes.join("/")).join(" e ")} cabe ao classificador.
        </AlertDescription>
      </Alert>
    );
  }
  return (
    <Alert className="border-emerald-300 bg-emerald-50 dark:bg-emerald-950/30">
      <CircleCheck aria-hidden />
      <AlertTitle>
        Classe mais provável: {top.codes.join(" / ")}
        {top.probability !== null ? ` (${pct(top.probability)}%)` : ""}
      </AlertTitle>
      <AlertDescription>
        {triage.rules_model_agree === true
          ? "As regras da cartilha e o modelo apontam a mesma classe."
          : triage.rules_model_agree === false
            ? "As regras da cartilha e o modelo apontam classes diferentes."
            : top.name_pt}
      </AlertDescription>
    </Alert>
  );
}

export function ResultsPanel({ triage }: { triage: Triage }) {
  return (
    <div className="space-y-4" aria-live="polite">
      <Summary triage={triage} />

      {triage.flags.length > 0 || triage.missing.length > 0 ? (
        <Alert>
          <TriangleAlert aria-hidden />
          <AlertTitle>Pontos de atenção</AlertTitle>
          <AlertDescription>
            <ul className="list-disc space-y-0.5 pl-4">
              {triage.flags.map((flag) => (
                <li key={flag}>{flag}</li>
              ))}
              {triage.missing.map((field) => (
                <li key={field}>Falta informar: {field}</li>
              ))}
            </ul>
          </AlertDescription>
        </Alert>
      ) : null}

      <div className="space-y-3">
        {triage.options.map((option, index) => (
          <ClassCard key={option.class_id} option={option} rank={index} />
        ))}
      </div>

      {triage.p_none !== null || triage.p_ambiguous !== null ? (
        <Card size="sm">
          <CardHeader>
            <CardTitle className="text-sm">Outras possibilidades do modelo</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {triage.p_none !== null ? <ProbabilityBar label="Nenhuma classe elegível" value={triage.p_none} /> : null}
            {triage.p_ambiguous !== null ? <ProbabilityBar label="Caso ambíguo" value={triage.p_ambiguous} /> : null}
          </CardContent>
        </Card>
      ) : null}

      {!triage.model_available ? (
        <p className="text-xs text-muted-foreground">
          O modelo de aprendizado não está carregado no servidor: o resultado vem só das regras da cartilha, sem probabilidades.
        </p>
      ) : null}

      <details className="rounded-lg border bg-card p-3 text-sm">
        <summary className="cursor-pointer font-medium">Dados considerados na análise</summary>
        <ul className="mt-2 list-disc space-y-0.5 pl-5 text-muted-foreground">
          {triage.facts.map((fact) => (
            <li key={fact}>{fact}</li>
          ))}
        </ul>
      </details>
    </div>
  );
}
