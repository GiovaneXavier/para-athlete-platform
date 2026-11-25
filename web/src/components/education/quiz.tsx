"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import useSWR from "swr";
import { ArrowRight, CircleCheck, CircleX } from "lucide-react";
import { Button, buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  DIFFICULTY_NAMES,
  getEduQuiz,
  newSeed,
  parseSeed,
  type AnswerResult,
  type EduQuiz,
  type GroupId,
  type QuizDifficulty,
} from "@/lib/education-api";
import { CaseQuestion } from "./case-question";
import { LoadError } from "./study-parts";

const GROUPS: GroupId[] = ["visual", "short_stature", "limb_standing", "limb_prosthesis"];
const SIZES = [5, 10, 15];
const LEVELS: QuizDifficulty[] = ["easy", "medium", "hard", "mixed"];
const GROUP_NAMES: Record<GroupId, string> = {
  visual: "Deficiência visual",
  short_stature: "Baixa estatura",
  limb_standing: "Amputação, em pé e sem prótese",
  limb_prosthesis: "Amputação, com prótese",
};

interface Entry {
  caseId: string;
  group: GroupId;
  difficulty: string;
  result: AnswerResult;
}

function readParams(params: URLSearchParams) {
  const seed = parseSeed(params.get("semente"));
  const size = SIZES.find((s) => String(s) === params.get("tamanho")) ?? 10;
  const level = LEVELS.find((d) => d === params.get("nivel")) ?? "mixed";
  const groups = GROUPS.filter((g) => params.getAll("grupo").includes(g));
  return { seed, size, level, groups: groups.length > 0 ? groups : GROUPS };
}

function Summary({ quiz, entries, onRestart }: { quiz: EduQuiz; entries: Entry[]; onRestart: () => void }) {
  const headingRef = useRef<HTMLHeadingElement>(null);
  useEffect(() => headingRef.current?.focus(), []);
  const hits = entries.filter((entry) => entry.result.correct).length;
  const byGroup = GROUPS.map((group) => {
    const own = entries.filter((entry) => entry.group === group);
    return { group, total: own.length, hits: own.filter((entry) => entry.result.correct).length };
  }).filter((row) => row.total > 0);

  return (
    <section aria-labelledby="quiz-resultado" className="space-y-5">
      <h2 id="quiz-resultado" ref={headingRef} tabIndex={-1} className="text-2xl font-semibold tracking-tight focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50">
        Resultado do quiz
      </h2>
      <p className="text-xl" role="status">
        Você teve <strong>{hits}</strong> {hits === 1 ? "acerto" : "acertos"} em {entries.length} questões.
      </p>
      <div role="region" aria-label="Acertos por grupo" tabIndex={0} className="overflow-x-auto rounded-lg border focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50">
        <table className="w-full min-w-[24rem] border-collapse text-left text-sm">
          <caption className="border-b bg-muted/40 px-3 py-2 text-left font-medium">Acertos por grupo</caption>
          <thead className="border-b bg-muted/40">
            <tr>
              <th scope="col" className="px-3 py-2 font-medium">Grupo</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">Acertos</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {byGroup.map((row) => (
              <tr key={row.group}>
                <td className="px-3 py-2">{GROUP_NAMES[row.group]}</td>
                <td className="px-3 py-2 text-right tabular-nums">
                  {row.hits} de {row.total}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <h3 className="text-lg font-semibold">Questão por questão</h3>
      <ol className="space-y-2">
        {entries.map((entry, index) => (
          <li key={entry.caseId} className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg border bg-card px-3 py-2 text-sm">
            {entry.result.correct ? <CircleCheck aria-hidden className="size-4" /> : <CircleX aria-hidden className="size-4" />}
            <span className="font-medium">
              Questão {index + 1}: {entry.result.correct ? "acerto" : entry.result.outcome === "revealed" ? "resposta vista" : "erro"}
            </span>
            <span>
              {GROUP_NAMES[entry.group]}, nível {DIFFICULTY_NAMES[entry.difficulty as QuizDifficulty]}. Resposta: {entry.result.answer_label}.
            </span>
          </li>
        ))}
      </ol>
      <div className="flex flex-wrap gap-2">
        <Button size="lg" onClick={onRestart}>
          Refazer com a mesma semente
        </Button>
        <Link href="/educacao" className={cn(buttonVariants({ variant: "outline", size: "lg" }))}>
          Voltar ao início do modo educação
        </Link>
      </div>
      <p className="text-sm text-foreground/85">
        Nada foi guardado. Para refazer este quiz depois, guarde o endereço desta página: a semente é {quiz.seed}.
      </p>
    </section>
  );
}

export function Quiz() {
  const router = useRouter();
  const search = useSearchParams();
  const { seed, size, level, groups } = readParams(search);
  const groupKey = groups.join(",");

  // Without a seed in the address, draw one and put it there (client only, so the page prerenders).
  useEffect(() => {
    if (seed === null) {
      const next = new URLSearchParams(search.toString());
      next.set("semente", String(newSeed()));
      router.replace(`/educacao/quiz?${next.toString()}`);
    }
  }, [seed, search, router]);

  const [position, setPosition] = useState(0);
  const [entries, setEntries] = useState<Entry[]>([]);
  const [finished, setFinished] = useState(false);
  const { data, error, isLoading, mutate } = useSWR<EduQuiz>(
    seed === null ? null : ["edu-quiz", seed, size, level, groupKey],
    () => getEduQuiz(seed!, size, groups, level),
    { revalidateOnFocus: false, shouldRetryOnError: false },
  );

  if (seed === null || isLoading) return <p role="status">Montando o quiz…</p>;
  if (error || !data) {
    return <LoadError message="Não foi possível montar o quiz." onRetry={() => void mutate()} />;
  }

  const current = data.cases[position];
  const last = position === data.cases.length - 1;

  function restart() {
    setPosition(0);
    setEntries([]);
    setFinished(false);
  }

  if (finished) return <Summary quiz={data} entries={entries} onRestart={restart} />;

  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-semibold tracking-tight">
        Questão {position + 1} de {data.cases.length}
      </h2>
      <p className="text-sm text-foreground/85" role="status">
        Acertos até agora: {entries.filter((entry) => entry.result.correct).length}.
      </p>
      <CaseQuestion
        key={current.case_id}
        eduCase={current}
        onAnswered={(result) =>
          setEntries((previous) =>
            previous.some((entry) => entry.caseId === current.case_id)
              ? previous
              : [...previous, { caseId: current.case_id, group: current.group, difficulty: current.difficulty, result }],
          )
        }
        afterResult={
          <Button
            size="lg"
            onClick={() => {
              if (last) setFinished(true);
              else setPosition(position + 1);
            }}
          >
            {last ? "Ver o resultado" : "Próxima questão"}
            <ArrowRight aria-hidden />
          </Button>
        }
      />
    </div>
  );
}
