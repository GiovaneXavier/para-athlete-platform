import Link from "next/link";
import type { ReactNode } from "react";
import { Info } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { guide } from "@/lib/guide";
import type { GuidePage } from "@/lib/guide-types";
import { BlockView } from "./blocks";
import { Freshness } from "./freshness";
import { LINK_CLASS, Rich } from "./rich";

export function dateBr(iso: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  return match ? `${match[3]}/${match[2]}/${match[1]}` : iso;
}

function Breadcrumbs({ page }: { page: GuidePage }) {
  return (
    <nav aria-label="Trilha">
      <ol className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm">
        {page.breadcrumbs.map((crumb, index) => (
          <li key={crumb.label} className="flex items-center gap-2">
            {index > 0 ? <span aria-hidden>›</span> : null}
            {crumb.href ? (
              <Link href={crumb.href} className={`${LINK_CLASS} inline-flex min-h-8 items-center`}>
                {crumb.label}
              </Link>
            ) : (
              <span aria-current="page" className="font-medium">
                {crumb.label}
              </span>
            )}
          </li>
        ))}
      </ol>
    </nav>
  );
}

export function GuideNotice() {
  return (
    <div role="note" className="flex gap-2 rounded-lg border bg-card px-3 py-2 text-sm text-card-foreground">
      <Info aria-hidden className="mt-0.5 size-4 shrink-0" />
      <div className="space-y-1">
        <p>{guide.notice}</p>
        <p className="text-foreground/85">Toda página do guia é rascunho até a especialista rever.</p>
      </div>
    </div>
  );
}

export function DraftBadge({ status }: { status: GuidePage["review_status"] }) {
  return <Badge variant="outline">{status === "reviewed" ? "Revisado" : "Rascunho"}</Badge>;
}

/** Frame of every guide page: trail, fixed notice, draft mark, sections, terms and the version footer. */
export function GuideShell({ page, children }: { page: GuidePage; children?: ReactNode }) {
  const footer = guide.footer.replace("${rules_id}", guide.rules_id).replace("${generated_on}", dateBr(guide.generated_on));
  return (
    <main id="conteudo" className="mx-auto w-full max-w-4xl flex-1 space-y-8 px-4 py-8 sm:px-6 lg:py-10">
      <header className="space-y-4">
        <Breadcrumbs page={page} />
        <div className="space-y-2">
          <p className="text-sm font-medium text-primary">Guia de classes</p>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">{page.title}</h1>
            <DraftBadge status={page.review_status} />
          </div>
          {page.intro.length > 0 ? (
            <p className="max-w-3xl text-balance text-lg text-foreground/90">
              <Rich segments={page.intro} />
            </p>
          ) : null}
        </div>
        <GuideNotice />
        <Freshness />
      </header>

      {page.sections.map((section) => (
        <section key={section.id} aria-labelledby={`s-${section.id}`} className="space-y-4">
          <h2 id={`s-${section.id}`} className="text-2xl font-semibold tracking-tight">
            {section.heading}
          </h2>
          {section.blocks.map((block, index) => (
            <BlockView key={index} block={block} />
          ))}
        </section>
      ))}

      {children}

      {page.term_definitions.length > 0 ? (
        <section aria-labelledby="s-termos" className="space-y-3">
          <h2 id="s-termos" className="text-2xl font-semibold tracking-tight">
            Termos desta página
          </h2>
          <dl className="max-w-3xl space-y-2">
            {page.term_definitions.map((item) => (
              <div key={item.id}>
                <dt className="font-medium">
                  <Link href={`${guide.glossary_path}#${item.id}`} className={LINK_CLASS}>
                    {item.term}
                  </Link>
                </dt>
                <dd className="text-foreground/90">
                  <Rich segments={item.definition} />
                </dd>
              </div>
            ))}
          </dl>
        </section>
      ) : null}

      <footer className="space-y-1 border-t pt-4 text-sm text-foreground/85">
        <p>{footer}</p>
        <p>
          <Link href={guide.rules_path} className={LINK_CLASS}>
            Ver a versão das regras e o estado de cada grupo
          </Link>
        </p>
      </footer>
    </main>
  );
}
