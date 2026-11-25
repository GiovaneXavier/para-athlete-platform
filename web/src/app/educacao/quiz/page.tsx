import type { Metadata } from "next";
import { Suspense } from "react";
import { Quiz } from "@/components/education/quiz";
import { StudyPage } from "@/components/education/study-parts";

export const metadata: Metadata = {
  title: "Quiz — modo educação",
  description: "Uma série de casos fictícios, com a contagem de acertos no fim. Nada é guardado.",
};

export default function QuizPage() {
  return (
    <StudyPage title="Quiz">
      <Suspense fallback={<p role="status">Carregando…</p>}>
        <Quiz />
      </Suspense>
    </StudyPage>
  );
}
