import Link from "next/link";
import { Info } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { HealthBadges } from "@/components/triage/health-badges";
import { TriageApp } from "@/components/triage/triage-app";

export default function Home() {
  return (
    <main id="conteudo" className="mx-auto w-full max-w-7xl flex-1 px-4 py-8 sm:px-6 lg:py-10">
      <header className="mb-8 space-y-4 print:hidden">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-1.5">
            <p className="text-sm font-medium text-primary">Atletismo paralímpico</p>
            <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">Triagem de classe esportiva</h1>
            <p className="max-w-2xl text-balance text-muted-foreground">
              Informe o perfil do atleta e veja as classes mais prováveis, as provas elegíveis e os equipamentos, com um relatório
              explicativo. Baseado na cartilha de classificação do CPB (2024).
            </p>
          </div>
          <div className="flex flex-col items-start gap-2 sm:items-end">
            <HealthBadges />
            <Link
              href="/transparencia"
              className="rounded-sm text-sm font-medium text-primary underline underline-offset-4 focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
            >
              Transparência: regras, modelo e experimentos
            </Link>
            <Link
              href="/educacao"
              className="rounded-sm text-sm font-medium text-primary underline underline-offset-4 focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
            >
              Modo educação: casos fictícios para estudar
            </Link>
          </div>
        </div>
        <Alert>
          <Info aria-hidden />
          <AlertDescription>
            Esta é uma ferramenta de apoio à triagem. Ela <strong>não substitui</strong> a classificação esportiva oficial, feita
            presencialmente por classificadores do CPB e da World Para Athletics.
          </AlertDescription>
        </Alert>
      </header>
      <TriageApp />
    </main>
  );
}
