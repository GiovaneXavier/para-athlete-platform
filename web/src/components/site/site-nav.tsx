"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const ITEMS = [
  { href: "/", label: "Triagem" },
  { href: "/educacao", label: "Educação" },
  { href: "/guia", label: "Guia" },
  { href: "/transparencia", label: "Transparência" },
] as const;

function isCurrent(pathname: string, href: string): boolean {
  return href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);
}

/**
 * Site-wide skip link and navigation. A plain list of links (no menu to open, no hover): at 320 px the
 * items wrap. The current section is marked with aria-current and a thicker underline, not only by colour.
 */
export function SiteNav() {
  const pathname = usePathname();
  return (
    <>
      <a
        href="#conteudo"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-background focus:px-3 focus:py-2 focus:ring-[3px] focus:ring-ring/50 print:hidden"
      >
        Pular para o conteúdo
      </a>
      <header className="border-b bg-background print:hidden">
        <nav aria-label="Principal" className="mx-auto w-full max-w-7xl px-4 sm:px-6">
          <ul className="flex flex-wrap gap-x-5 gap-y-1 py-1">
            {ITEMS.map((item) => {
              const current = isCurrent(pathname, item.href);
              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    aria-current={current ? "page" : undefined}
                    className={cn(
                      "inline-flex min-h-8 items-center rounded-sm text-sm underline-offset-[6px] focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50",
                      current ? "font-semibold underline decoration-2" : "font-medium hover:underline",
                    )}
                  >
                    {item.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
      </header>
    </>
  );
}
