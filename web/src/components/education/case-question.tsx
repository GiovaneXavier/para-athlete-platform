"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { CircleCheck, CircleX, Eye } from "lucide-react";
import { Button } from "@/components/ui/button";
import { postEduAnswer, DIFFICULTY_NAMES, type AnswerResult, type EduCase } from "@/lib/education-api";
import { DraftBadge } from "./study-parts";

const RESULT_ICON = {
  correct: CircleCheck,
  wrong: CircleX,
  revealed: Eye,
} as const;

function TraceTable({ result }: { result: AnswerResult }) {
  return (
    <div
      role="region"
      aria-label="Rastro dos critérios"
      tabIndex={0}
      className="overflow-x-auto rounded-lg border focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
    >
      <table className="w-full min-w-[40rem] border-collapse text-left text-sm">
        <caption className="border-b bg-muted/40 px-3 py-2 text-left font-medium">
          Rastro dos critérios: o que se verificou, com o valor do caso
        </caption>
        <thead className="border-b bg-muted/40">
          <tr>
            <th scope="col" className="px-3 py-2 font-medium">Critério</th>
            <th scope="col" className="px-3 py-2 font-medium">Referência</th>
            <th scope="col" className="px-3 py-2 font-medium">Valor do caso</th>
            <th scope="col" className="px-3 py-2 font-medium">Resultado</th>
          </tr>
        </thead>
        <tbody className="divide-y">
          {result.steps.map((step, index) => (
            <tr key={index}>
              <td className="px-3 py-2 align-top">
                {step.criterion}
                <span className="mt-1 block text-foreground/80">{step.explanation}</span>
              </td>
              <td className="px-3 py-2 align-top">{step.reference}</td>
              <td className="px-3 py-2 align-top">{step.value}</td>
              <td className="px-3 py-2 align-top font-medium">{step.result_label}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ResultPanel({ result, headingRef }: { result: AnswerResult; headingRef: React.RefObject<HTMLHeadingElement | null> }) {
  const Icon = RESULT_ICON[result.outcome];
  return (
    <section aria-labelledby={`resultado-${result.case_id}`} className="space-y-4 rounded-xl border bg-card p-4">
      <div className="flex flex-wrap items-center gap-2">
        <h3
          id={`resultado-${result.case_id}`}
          ref={headingRef}
          tabIndex={-1}
          className="flex items-center gap-2 text-xl font-semibold focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
        >
          <Icon aria-hidden className="size-5" />
          {result.title}
        </h3>
        <DraftBadge status={result.review_status} />
      </div>
      <p>
        Resposta: <strong>{result.answer_label}</strong>
        {result.class_name_pt ? <> — {result.class_name_pt}</> : null}.
      </p>
      <TraceTable result={result} />
      <p>
        <strong>Conclusão:</strong> {result.conclusion}
      </p>
      {result.references.length > 0 ? (
        <p className="text-sm text-foreground/85">Referência: {result.references.join("; ")}.</p>
      ) : null}
      <div role="note" className="space-y-1 rounded-lg border bg-background px-3 py-2 text-sm">
        <p className="font-medium">O que este rastro não cobre</p>
        <ul className="list-disc space-y-1 pl-5 text-foreground/90">
          {result.limits.map((limit) => (
            <li key={limit}>{limit}</li>
          ))}
        </ul>
      </div>
    </section>
  );
}

interface Props {
  eduCase: EduCase;
  /** Called once the learner answered (or asked to see the answer). */
  onAnswered?: (result: AnswerResult, choice: string | null) => void;
  /** Rendered after the result (for example, the "next" button). */
  afterResult?: ReactNode;
}

/** One case: facts, options, the answer check on the server, and the trace. Remount per case (key). */
export function CaseQuestion({ eduCase, onAnswered, afterResult }: Props) {
  const [selected, setSelected] = useState<string | null>(null);
  const [chosen, setChosen] = useState<string | null>(null);
  const [result, setResult] = useState<AnswerResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const headingRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    if (result) headingRef.current?.focus();
  }, [result]);

  async function send(choice: string | null) {
    setError(null);
    setPending(true);
    try {
      const answer = await postEduAnswer(eduCase.case_id, choice);
      setChosen(choice);
      if (choice === null) setSelected(null);
      setResult(answer);
      onAnswered?.(answer, choice);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Erro inesperado");
    } finally {
      setPending(false);
    }
  }

  const errorId = `erro-${eduCase.case_id}`;
  const done = result !== null;
  return (
    <div className="space-y-5">
      <section aria-label="Caso" className="space-y-3 rounded-xl border bg-card p-4">
        <div className="flex flex-wrap items-center gap-2">
          <DraftBadge status={eduCase.review_status} />
          <span className="text-sm text-foreground/80">Nível: {DIFFICULTY_NAMES[eduCase.difficulty]}</span>
        </div>
        <p>{eduCase.presentation.summary}</p>
        <dl className="grid gap-x-4 gap-y-1 sm:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
          {eduCase.presentation.facts.map((fact) => (
            <div key={fact.label} className="contents">
              <dt className="font-medium">{fact.label}</dt>
              <dd>{fact.value}</dd>
            </div>
          ))}
        </dl>
      </section>

      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (selected === null) {
            setError("Escolha uma opção antes de responder, ou use “Ver a resposta”.");
            return;
          }
          void send(selected);
        }}
        className="space-y-3"
      >
        <fieldset disabled={done || pending} aria-describedby={error ? errorId : undefined} className="space-y-2">
          <legend className="mb-2 text-base font-medium">Qual é a resposta para este caso?</legend>
          {eduCase.options.map((option) => {
            const isRight = result?.answer_id === option.id;
            const isYours = done && chosen === option.id;
            return (
              <label
                key={option.id}
                className="flex min-h-11 cursor-pointer items-center gap-3 rounded-lg border bg-background px-3 py-2 has-[:checked]:border-primary has-[:checked]:bg-primary/5 has-[:focus-visible]:ring-[3px] has-[:focus-visible]:ring-ring/50 has-[:disabled]:cursor-default"
              >
                <input
                  type="radio"
                  name={`opcao-${eduCase.case_id}`}
                  value={option.id}
                  checked={selected === option.id}
                  onChange={() => {
                    setSelected(option.id);
                    setError(null);
                  }}
                  className="size-4 accent-primary"
                />
                <span>{option.label}</span>
                {isRight ? <span className="ml-auto text-sm font-medium">Resposta certa</span> : null}
                {isYours && !isRight ? <span className="ml-auto text-sm font-medium">Sua resposta</span> : null}
              </label>
            );
          })}
        </fieldset>

        <p id={errorId} role="alert" className={error ? "text-sm font-medium text-destructive" : "sr-only"}>
          {error ?? ""}
        </p>

        {!done ? (
          <div className="flex flex-wrap gap-2">
            <Button type="submit" size="lg" disabled={pending}>
              {pending ? "Verificando…" : "Responder"}
            </Button>
            <Button type="button" size="lg" variant="outline" disabled={pending} onClick={() => void send(null)}>
              Ver a resposta
            </Button>
          </div>
        ) : null}
      </form>

      <div role="status" aria-live="polite" className="sr-only">
        {result ? `${result.title}. Resposta: ${result.answer_label}.` : ""}
      </div>

      {result ? (
        <>
          <ResultPanel result={result} headingRef={headingRef} />
          {afterResult}
        </>
      ) : null}
    </div>
  );
}
