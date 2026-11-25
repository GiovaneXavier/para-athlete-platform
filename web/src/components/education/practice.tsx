"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import useSWR from "swr";
import { ArrowRight } from "lucide-react";
import { Button, buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { getEduCase, parseSeed, type Difficulty, type EduCase, type GroupId } from "@/lib/education-api";
import { CaseQuestion } from "./case-question";
import { LoadError } from "./study-parts";

const GROUPS: GroupId[] = ["visual", "short_stature", "limb_standing", "limb_prosthesis"];
const LEVELS: Difficulty[] = ["easy", "medium", "hard"];

function readParams(params: URLSearchParams) {
  const group = GROUPS.find((g) => g === params.get("grupo"));
  const level = LEVELS.find((d) => d === params.get("nivel"));
  const seed = parseSeed(params.get("semente"));
  const index = parseSeed(params.get("caso")) ?? 0;
  return group && level && seed !== null ? { group, level, seed, index } : null;
}

export function Practice() {
  const router = useRouter();
  const params = readParams(useSearchParams());
  const { data, error, isLoading, mutate } = useSWR<EduCase>(
    params ? ["edu-case", params.group, params.level, params.seed, params.index] : null,
    () => getEduCase(params!.group, params!.level, params!.seed, params!.index),
    { revalidateOnFocus: false, shouldRetryOnError: false },
  );

  if (!params) {
    return (
      <LoadError message="O endereço não tem um grupo, um nível e uma semente válidos. Volte e escolha um grupo." />
    );
  }
  if (isLoading) return <p role="status">Montando o caso…</p>;
  if (error || !data) {
    return <LoadError message="Não foi possível montar o caso." onRetry={() => void mutate()} />;
  }

  const next = new URLSearchParams({
    grupo: params.group,
    nivel: params.level,
    semente: String(params.seed),
    caso: String(params.index + 1),
  });

  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-semibold tracking-tight">Caso {params.index + 1}</h2>
      <CaseQuestion
        key={data.case_id}
        eduCase={data}
        afterResult={
          <div className="flex flex-wrap gap-2">
            <Button size="lg" onClick={() => router.push(`/educacao/praticar?${next.toString()}`)}>
              Próximo caso
              <ArrowRight aria-hidden />
            </Button>
            <Link href="/educacao" className={cn(buttonVariants({ variant: "outline", size: "lg" }))}>
              Escolher outro grupo ou nível
            </Link>
          </div>
        }
      />
    </div>
  );
}
