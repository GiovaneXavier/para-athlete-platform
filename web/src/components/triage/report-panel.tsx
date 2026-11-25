"use client";

import dynamic from "next/dynamic";
import { useEffect, useRef, useState } from "react";
import useSWR from "swr";
import { Check, Copy, LoaderCircle, Printer, ShieldCheck, TriangleAlert } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { Job } from "@/lib/api-types";
import { getJson } from "@/lib/api";

// react-markdown is only needed once a report is shown.
const Markdown = dynamic(() => import("@/components/triage/markdown"), {
  ssr: false,
  loading: () => <Skeleton className="h-48 w-full" />,
});

const fetchJob = (url: string) => getJson<Job>(url);
const isFinished = (job: Job | undefined) => job !== undefined && (job.status === "done" || job.status === "error");

// Must keep the same identity across renders: SWR restarts its timer whenever this function changes,
// and this panel re-renders every second (the elapsed counter), so an inline function would never fire.
const pollWhileRunning = (latest: Job | undefined) => (isFinished(latest) ? 0 : 2000);

const ISSUE_LABEL: Record<string, string> = {
  llm_unavailable: "O servidor do LLM (Ollama) não respondeu",
  missing_section: "Seção ausente",
  duplicate_section: "Seção repetida",
  section_order: "Seções fora de ordem",
  empty_section: "Seção vazia",
  misplaced_text: "Texto na seção errada",
  contradiction: "Texto contraditório",
  untranslated_text: "Texto sem tradução",
  unknown_class: "Classe que não foi fornecida",
  unknown_percentage: "Porcentagem que não foi fornecida",
  missing_disclaimer: "Aviso de triagem ausente",
};

function formatElapsed(seconds: number) {
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

function useElapsedSeconds(active: boolean) {
  const [startedAt] = useState(() => Date.now());
  const [now, setNow] = useState(startedAt);
  useEffect(() => {
    if (!active) return;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [active]);
  return Math.floor((now - startedAt) / 1000);
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  useEffect(() => () => clearTimeout(timer.current), []);

  return (
    <Button
      type="button"
      variant="outline"
      size="sm"
      onClick={async () => {
        await navigator.clipboard.writeText(text);
        setCopied(true);
        clearTimeout(timer.current);
        timer.current = setTimeout(() => setCopied(false), 2000);
      }}
    >
      {copied ? <Check aria-hidden data-icon="inline-start" /> : <Copy aria-hidden data-icon="inline-start" />}
      {copied ? "Copiado" : "Copiar"}
    </Button>
  );
}

interface Props {
  /** The instant, deterministic report. */
  reference: string;
  /** The LLM job to follow, or null when the LLM was not requested. */
  jobId: string | null;
}

// Mount with key={jobId} so the timer and the "show reference" toggle reset for each analysis.
export function ReportPanel({ reference, jobId }: Props) {
  const { data: job, error } = useSWR<Job>(jobId ? `/api/report/${jobId}` : null, fetchJob, {
    refreshInterval: pollWhileRunning,
    // The wait is minutes long: keep polling when the user switches tabs, or the report would never appear.
    refreshWhenHidden: true,
    revalidateOnFocus: false,
  });
  const [showReference, setShowReference] = useState(false);
  const running = jobId !== null && !isFinished(job) && !error;
  const elapsed = useElapsedSeconds(running);

  const report = job?.status === "done" ? job.report : null;
  const usingLlm = report?.source === "llm" && !showReference;
  const text = usingLlm && report ? report.text : reference;

  return (
    <Card>
      <CardHeader className="flex-row flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <CardTitle>Relatório</CardTitle>
          {usingLlm && report ? (
            <Badge variant="secondary" className="gap-1">
              <ShieldCheck aria-hidden />
              {report.model} · verificado
            </Badge>
          ) : (
            <Badge variant="outline">Referência</Badge>
          )}
        </div>
        <div className="flex gap-2 print:hidden">
          {report?.source === "llm" ? (
            <Button type="button" variant="ghost" size="sm" onClick={() => setShowReference((v) => !v)}>
              {showReference ? "Ver texto do LLM" : "Ver relatório de referência"}
            </Button>
          ) : null}
          <CopyButton text={text} />
          <Button type="button" variant="outline" size="sm" onClick={() => window.print()}>
            <Printer aria-hidden data-icon="inline-start" />
            Imprimir
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {running ? (
          <Alert className="print:hidden">
            <LoaderCircle aria-hidden className="animate-spin" />
            <AlertTitle>Gerando o relatório com o LLM… {formatElapsed(elapsed)}</AlertTitle>
            <AlertDescription>
              Costuma levar de 1 a 6 minutos em CPU. O relatório de referência abaixo já está pronto e é fiel aos mesmos dados.
            </AlertDescription>
          </Alert>
        ) : null}

        {report?.source === "template" && report.issues.length > 0 ? (
          <Alert className="border-amber-300 bg-amber-50 print:hidden dark:bg-amber-950/30">
            <TriangleAlert aria-hidden />
            <AlertTitle>O texto do LLM não foi usado</AlertTitle>
            <AlertDescription>
              <ul className="list-disc pl-4">
                {report.issues.map((issue) => (
                  <li key={`${issue.kind}-${issue.detail}`}>
                    {ISSUE_LABEL[issue.kind] ?? issue.kind}: {issue.detail}
                  </li>
                ))}
              </ul>
              Mostrando o relatório de referência.
            </AlertDescription>
          </Alert>
        ) : null}

        {job?.status === "error" || error ? (
          <Alert variant="destructive" className="print:hidden">
            <TriangleAlert aria-hidden />
            <AlertTitle>Não foi possível gerar o relatório com o LLM</AlertTitle>
            <AlertDescription>{job?.error ?? error?.message}</AlertDescription>
          </Alert>
        ) : null}

        <div className="rounded-lg border bg-background px-4 py-2">
          <Markdown>{text}</Markdown>
        </div>
      </CardContent>
    </Card>
  );
}
