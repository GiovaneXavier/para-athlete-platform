"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import useSWR from "swr";
import { Button, buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  getEduScope,
  newSeed,
  type EduScope,
  type GroupId,
  type QuizDifficulty,
} from "@/lib/education-api";
import { LoadError } from "./study-parts";

/** Practice links use the fixed seed 0: the same cases the specialist reviews. */
const PRACTICE_SEED = 0;

export function EducationHub() {
  const router = useRouter();
  const { data, error, isLoading, mutate } = useSWR<EduScope>("/api/education/scope", () => getEduScope(), {
    revalidateOnFocus: false,
    shouldRetryOnError: false,
  });
  const [difficulty, setDifficulty] = useState<QuizDifficulty>("mixed");
  const [size, setSize] = useState(10);
  const [groups, setGroups] = useState<GroupId[]>([]);
  const [problem, setProblem] = useState<string | null>(null);

  if (isLoading) return <p role="status">Carregando os grupos…</p>;
  if (error || !data) {
    return (
      <LoadError
        message="A API não respondeu. O modo educação precisa dela para montar os casos."
        onRetry={() => void mutate()}
      />
    );
  }

  const picked = groups.length > 0 ? groups : data.groups.map((g) => g.id);
  const practiceLevels = data.difficulties.filter((d) => d.id !== "mixed");

  function startQuiz() {
    if (picked.length === 0) {
      setProblem("Escolha pelo menos um grupo.");
      return;
    }
    const params = new URLSearchParams({
      semente: String(newSeed()),
      tamanho: String(size),
      nivel: difficulty,
    });
    for (const group of picked) params.append("grupo", group);
    router.push(`/educacao/quiz?${params.toString()}`);
  }

  function toggle(group: GroupId, checked: boolean) {
    setProblem(null);
    const base = groups.length > 0 ? groups : data!.groups.map((g) => g.id);
    setGroups(checked ? [...new Set([...base, group])] : base.filter((g) => g !== group));
  }

  return (
    <div className="space-y-10">
      <section aria-labelledby="praticar" className="space-y-4">
        <h2 id="praticar" className="text-2xl font-semibold tracking-tight">
          Praticar um caso por vez
        </h2>
        <p className="max-w-3xl text-foreground/85">
          Escolha o grupo e o nível. Cada caso é fictício e sempre o mesmo para a mesma semente. Você responde, e só então vê a
          resposta e o rastro dos critérios.
        </p>
        <ul className="grid gap-4 sm:grid-cols-2">
          {data.groups.map((group) => (
            <li key={group.id} className="flex flex-col gap-3 rounded-xl border bg-card p-4">
              <h3 className="text-lg font-semibold">{group.label}</h3>
              <p className="text-sm text-foreground/85">{group.summary}</p>
              {group.warning ? (
                <p role="note" className="rounded-md border bg-background px-2 py-1.5 text-sm">
                  <strong>Atenção:</strong> {group.warning}
                </p>
              ) : null}
              <div className="mt-auto flex flex-wrap gap-2">
                {practiceLevels.map((level) => (
                  <Link
                    key={level.id}
                    href={`/educacao/praticar?grupo=${group.id}&nivel=${level.id}&semente=${PRACTICE_SEED}&caso=0`}
                    className={cn(buttonVariants({ variant: "outline", size: "lg" }))}
                    title={level.hint}
                  >
                    {level.label}
                    <span className="sr-only">: praticar {group.label}</span>
                  </Link>
                ))}
              </div>
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="quiz" className="space-y-4">
        <h2 id="quiz" className="text-2xl font-semibold tracking-tight">
          Fazer um quiz
        </h2>
        <p className="max-w-3xl text-foreground/85">
          Uma série de casos. Nada é guardado: o resultado fica só nesta página, e a semente no endereço permite refazer o mesmo quiz.
        </p>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            startQuiz();
          }}
          className="max-w-2xl space-y-5 rounded-xl border bg-card p-4"
        >
          <fieldset className="space-y-2">
            <legend className="font-medium">Grupos</legend>
            {data.groups.map((group) => (
              <label key={group.id} className="flex min-h-9 items-center gap-3">
                <input
                  type="checkbox"
                  checked={picked.includes(group.id)}
                  onChange={(event) => toggle(group.id, event.target.checked)}
                  className="size-4 accent-primary"
                />
                {group.label}
              </label>
            ))}
          </fieldset>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <label htmlFor="quiz-tamanho" className="font-medium">
                Número de questões
              </label>
              <select
                id="quiz-tamanho"
                value={size}
                onChange={(event) => setSize(Number(event.target.value))}
                className="h-10 w-full rounded-lg border bg-background px-2 focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
              >
                {data.quiz_sizes.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-1.5">
              <label htmlFor="quiz-nivel" className="font-medium">
                Nível
              </label>
              <select
                id="quiz-nivel"
                value={difficulty}
                onChange={(event) => setDifficulty(event.target.value as QuizDifficulty)}
                className="h-10 w-full rounded-lg border bg-background px-2 focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
              >
                {data.difficulties.map((option) => (
                  <option key={option.id} value={option.id}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <p role="alert" className={problem ? "text-sm font-medium text-destructive" : "sr-only"}>
            {problem ?? ""}
          </p>
          <Button type="submit" size="lg">
            Começar o quiz
          </Button>
        </form>
      </section>
    </div>
  );
}
