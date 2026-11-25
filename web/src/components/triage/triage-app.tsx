"use client";

import { useState, useTransition } from "react";
import { TriangleAlert } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { GroupPicker } from "@/components/triage/group-picker";
import { ProfileForm } from "@/components/triage/profile-form";
import { ReportPanel } from "@/components/triage/report-panel";
import { ResultsPanel } from "@/components/triage/results-panel";
import type { Triage } from "@/lib/api-types";
import { postTriage, startReport } from "@/lib/api";
import { GROUPS_BY_ID, buildProfile, validate, type GroupId, type Values } from "@/lib/profile-schema";

interface Analysis {
  triage: Triage;
  jobId: string | null;
  /** Distinguishes analyses so the report panel remounts. */
  key: number;
}

const INITIAL_GROUP: GroupId = "limb";

export function TriageApp() {
  const [groupId, setGroupId] = useState<GroupId>(INITIAL_GROUP);
  const [values, setValues] = useState<Values>(() => ({ ...GROUPS_BY_ID[INITIAL_GROUP].defaults }));
  const [useLlm, setUseLlm] = useState(true);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  const group = GROUPS_BY_ID[groupId];
  const problem = validate(group, values);

  function selectGroup(next: GroupId) {
    if (next === groupId) return;
    setGroupId(next);
    setValues({ ...GROUPS_BY_ID[next].defaults });
    setAnalysis(null);
    setError(null);
  }

  function changeValue(name: string, value: string | boolean | string[] | undefined) {
    setValues((current) => ({ ...current, [name]: value }));
  }

  function submit() {
    const profile = buildProfile(group, values);
    setError(null);
    startTransition(async () => {
      try {
        // The two requests are independent: the instant analysis and the slow LLM job.
        const [triage, job] = await Promise.all([
          postTriage(profile),
          useLlm ? startReport(profile).catch(() => null) : Promise.resolve(null),
        ]);
        startTransition(() => setAnalysis((previous) => ({ triage, jobId: job?.job_id ?? null, key: (previous?.key ?? 0) + 1 })));
      } catch (reason) {
        startTransition(() => setError(reason instanceof Error ? reason.message : "Erro inesperado"));
      }
    });
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
      <div className="space-y-4 print:hidden">
        <Card>
          <CardHeader>
            <CardTitle>1. Tipo de comprometimento</CardTitle>
          </CardHeader>
          <CardContent>
            <GroupPicker value={groupId} onChange={selectGroup} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>2. Dados do atleta</CardTitle>
          </CardHeader>
          <CardContent>
            <ProfileForm
              group={group}
              values={values}
              onChange={changeValue}
              useLlm={useLlm}
              onUseLlmChange={setUseLlm}
              onSubmit={submit}
              pending={pending}
              problem={problem}
            />
          </CardContent>
        </Card>
      </div>

      <div className="space-y-4">
        {error ? (
          <Alert variant="destructive">
            <TriangleAlert aria-hidden />
            <AlertTitle>Não foi possível analisar o perfil</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        ) : null}

        {analysis ? (
          <>
            <ResultsPanel triage={analysis.triage} />
            <ReportPanel key={analysis.key} reference={analysis.triage.reference_report} jobId={analysis.jobId} />
          </>
        ) : (
          <Card className="border-dashed print:hidden">
            <CardContent className="py-12 text-center text-sm text-muted-foreground">
              Escolha o tipo de comprometimento, preencha o que souber e clique em <strong>Analisar perfil</strong>. Campos em branco
              são tratados como “não medido”: o sistema continua e avisa o que falta.
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
