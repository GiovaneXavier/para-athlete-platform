import Link from "next/link";
import type { ReactNode } from "react";
import { ArrowLeft, Info } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { STUDY_NOTICE, type ReviewStatus } from "@/lib/education-api";

/** The fixed notice, on every study-mode screen. Static text: it shows even when the API is down. */
export function StudyNotice() {
  return (
    <div role="note" className="flex gap-2 rounded-lg border bg-card px-3 py-2 text-sm text-card-foreground">
      <Info aria-hidden className="mt-0.5 size-4 shrink-0" />
      <div className="space-y-1">
        <p>{STUDY_NOTICE}</p>
        <p className="text-foreground/85">Todo caso e toda explicação são rascunho até a especialista rever.</p>
      </div>
    </div>
  );
}

export function DraftBadge({ status }: { status: ReviewStatus }) {
  return <Badge variant="outline">{status === "reviewed" ? "Revisado" : "Rascunho"}</Badge>;
}

export function StudyPage({ title, intro, children }: { title: string; intro?: ReactNode; children: ReactNode }) {
  return (
    <main id="conteudo" className="mx-auto w-full max-w-4xl flex-1 space-y-6 px-4 py-8 sm:px-6 lg:py-10">
      <header className="space-y-4">
        <Link
          href="/"
          className="inline-flex min-h-8 items-center gap-1.5 rounded-sm text-sm font-medium text-primary underline underline-offset-4 focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
        >
          <ArrowLeft aria-hidden className="size-4" />
          Voltar à triagem
        </Link>
        <div className="space-y-1.5">
          <p className="text-sm font-medium text-primary">Modo educação</p>
          <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">{title}</h1>
          {intro ? <p className="max-w-3xl text-balance text-foreground/85">{intro}</p> : null}
        </div>
        <StudyNotice />
      </header>
      {children}
    </main>
  );
}

export function LoadError({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="space-y-2 rounded-lg border border-destructive/40 bg-card p-3 text-sm">
      <p className="font-medium text-destructive">Não foi possível carregar</p>
      <p className="text-foreground/85">{message}</p>
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="inline-flex h-9 items-center rounded-lg border px-3 font-medium hover:bg-muted focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
        >
          Tentar de novo
        </button>
      ) : null}
    </div>
  );
}
