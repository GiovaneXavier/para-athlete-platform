import type { Metadata } from "next";
import { Suspense } from "react";
import { Practice } from "@/components/education/practice";
import { StudyPage } from "@/components/education/study-parts";

export const metadata: Metadata = {
  title: "Praticar — modo educação",
  description: "Um caso fictício por vez, com a resposta e o rastro dos critérios depois que você responde.",
};

export default function PraticarPage() {
  return (
    <StudyPage title="Praticar">
      <Suspense fallback={<p role="status">Carregando…</p>}>
        <Practice />
      </Suspense>
    </StudyPage>
  );
}
