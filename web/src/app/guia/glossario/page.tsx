import type { Metadata } from "next";
import { GuideShell } from "@/components/guide/guide-shell";
import { Rich } from "@/components/guide/rich";
import { guide, pageByPath } from "@/lib/guide";

const page = pageByPath("/guia/glossario")!;

export const metadata: Metadata = {
  title: "Glossário — guia de classes",
  description: "Definições curtas dos termos usados no guia de classes.",
};

export default function GlossarioPage() {
  return (
    <GuideShell page={page}>
      <section aria-labelledby="s-termos-lista" className="space-y-4">
        <h2 id="s-termos-lista" className="text-2xl font-semibold tracking-tight">
          Termos, em ordem alfabética
        </h2>
        <dl className="max-w-3xl space-y-4">
          {guide.glossary.map((item) => (
            <div key={item.id} id={item.id} className="scroll-mt-6 rounded-lg border p-3 target:ring-[3px] target:ring-ring/50">
              <dt className="font-semibold">{item.term}</dt>
              <dd className="mt-1 leading-relaxed">
                <Rich segments={item.definition} />
              </dd>
            </div>
          ))}
        </dl>
      </section>
    </GuideShell>
  );
}
