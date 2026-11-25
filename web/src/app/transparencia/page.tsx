import type { Metadata } from "next";
import Link from "next/link";
import { ArrowLeft, Info } from "lucide-react";
import { LiveCheck } from "@/components/transparency/live-check";
import { E1Section, E7Section, V1Section } from "@/components/transparency/experiment-sections";
import { EvidenceBadge, Note } from "@/components/transparency/parts";
import { ModelSection, RulesSection } from "@/components/transparency/rules-sections";
import type { TransparencyReport } from "@/lib/api-types";
import report from "../../../public/transparency.json";

export const metadata: Metadata = {
  title: "Transparência — triagem de classe esportiva",
  description:
    "Versão das regras, ficha do modelo e resultados dos experimentos, com o nível de evidência de cada número.",
};

// The JSON is written by para_triage.transparency.export; its shape is checked by the API tests.
const data = report as unknown as TransparencyReport;

export default function TransparenciaPage() {
  return (
    <>
      <main id="conteudo" className="mx-auto w-full max-w-5xl flex-1 space-y-10 px-4 py-8 sm:px-6 lg:py-10">
        <header className="space-y-4">
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 rounded-sm text-sm font-medium text-primary underline underline-offset-4 focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
          >
            <ArrowLeft aria-hidden className="size-4" />
            Voltar à triagem
          </Link>
          <div className="space-y-1.5">
            <p className="text-sm font-medium text-primary">Atletismo paralímpico</p>
            <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">Transparência</h1>
            <p className="max-w-3xl text-balance text-foreground/85">
              De onde vêm as regras, qual modelo está em uso e o que os experimentos medem, com o que eles não medem. Os números vêm de
              um arquivo versionado, gerado por script a partir dos resultados dos experimentos; nenhum foi digitado à mão.
            </p>
          </div>
          <Note title="Aviso de uso">
            <p>{data.usage_notice}</p>
          </Note>
        </header>

        <section aria-labelledby="como-ler" className="space-y-3">
          <h2 id="como-ler" className="flex flex-wrap items-center gap-2 text-2xl font-semibold tracking-tight">
            Como ler os números <EvidenceBadge />
          </h2>
          <div className="flex max-w-3xl gap-2 text-foreground/90">
            <Info aria-hidden className="mt-1 size-4 shrink-0" />
            <p>
              Todo número desta página é do nível de evidência <strong>N1</strong>: {data.evidence_notice}. Os rótulos são produzidos
              pelas mesmas regras que o sistema aplica, então os experimentos medem a robustez do sistema ao ruído e a campos
              faltantes, não se ele acerta a classe de um atleta real. Por isso não usamos aqui o termo “acurácia”: ele sugeriria uma
              verdade externa, que o nível N1 não tem. Usamos <strong>concordância com o rótulo sintético</strong>.
            </p>
          </div>
        </section>

        <RulesSection report={data} />
        <ModelSection report={data} />
        <LiveCheck />
        <E1Section report={data} />
        <E7Section report={data} />
        <V1Section report={data} />

        <section aria-labelledby="regerar" className="space-y-2">
          <h2 id="regerar" className="text-2xl font-semibold tracking-tight">
            Como esta página é gerada
          </h2>
          <p className="max-w-3xl">
            Um script lê as pastas de resultados dos experimentos (que ficam na máquina de quem os rodou, fora do git) e grava só os
            agregados em <code className="font-mono text-sm">web/public/transparency.json</code>, com o commit de origem. A página e
            a API leem esse arquivo; nenhuma delas lê as pastas de resultados. As instruções para regerar estão em{" "}
            <code className="font-mono text-sm">docs/transparencia.md</code> no repositório.
          </p>
        </section>
      </main>
    </>
  );
}
