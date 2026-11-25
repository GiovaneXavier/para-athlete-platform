import Link from "next/link";
import type { ReactNode } from "react";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { guide } from "@/lib/guide";
import type { Block, Cell } from "@/lib/guide-types";
import { FigureView } from "./figures";
import { LINK_CLASS, Rich } from "./rich";

function CellView({ cell }: { cell: Cell }): ReactNode {
  if (typeof cell === "string") return cell;
  if (Array.isArray(cell)) return <Rich segments={cell} />;
  return (
    <Link href={cell.href} className={cn(LINK_CLASS, "font-medium")}>
      {cell.t}
    </Link>
  );
}

function TableBlock({ block }: { block: Extract<Block, { kind: "table" }> }) {
  return (
    <div
      role="region"
      aria-label={`Tabela: ${block.caption}`}
      tabIndex={0}
      className="overflow-x-auto rounded-lg border focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
    >
      <table className="w-full min-w-[26rem] border-collapse text-left text-sm">
        <caption className="border-b bg-muted/40 px-3 py-2 text-left font-medium">{block.caption}</caption>
        <thead className="border-b bg-muted/40">
          <tr>
            {block.headers.map((header) => (
              <th key={header} scope="col" className="px-3 py-2 align-bottom font-medium">
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y">
          {block.rows.map((row, rowIndex) => (
            <tr key={rowIndex}>
              {row.map((cell, cellIndex) => (
                <td key={cellIndex} className="px-3 py-2 align-top">
                  <CellView cell={cell} />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function BlockView({ block }: { block: Block }): ReactNode {
  switch (block.kind) {
    case "p":
      return (
        <p className="max-w-3xl leading-relaxed">
          <Rich segments={block.text} />
        </p>
      );
    case "ul":
      return (
        <ul className="max-w-3xl list-disc space-y-2 pl-5 leading-relaxed">
          {block.items.map((item, index) => (
            <li key={index}>
              <Rich segments={item} />
            </li>
          ))}
        </ul>
      );
    case "table":
      return <TableBlock block={block} />;
    case "figure":
      return <FigureView figure={guide.figures[block.id]} />;
    case "example":
      return (
        <div className="max-w-3xl space-y-2 rounded-xl border bg-card p-4">
          <p className="font-medium">{block.summary}</p>
          <dl className="grid gap-x-4 gap-y-1 text-sm sm:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
            {block.facts.map((fact) => (
              <div key={fact.label} className="contents">
                <dt className="font-medium">{fact.label}</dt>
                <dd>{fact.value}</dd>
              </div>
            ))}
          </dl>
          <p className="text-sm">
            <strong>Conclusão:</strong> {block.conclusion}
          </p>
        </div>
      );
    case "link":
      return (
        <p>
          <Link href={block.href} className={cn(buttonVariants({ variant: "outline", size: "lg" }), "h-auto min-h-9 whitespace-normal py-2 text-left")}>
            {block.label}
          </Link>
        </p>
      );
    case "cards":
      return (
        <ul className="grid gap-4 sm:grid-cols-2">
          {block.items.map((item) => (
            <li key={item.href} className="flex flex-col gap-2 rounded-xl border bg-card p-4">
              <h3 className="text-lg font-semibold">
                <Link href={item.href} className={LINK_CLASS}>
                  {item.title}
                </Link>
              </h3>
              <p className="text-sm text-foreground/85">
                <Rich segments={item.text} />
              </p>
              <p className="text-sm">Classes: {item.classes.join(", ")}</p>
            </li>
          ))}
        </ul>
      );
    case "details":
      return (
        <details className="max-w-3xl rounded-lg border bg-card p-3 text-sm">
          <summary className="cursor-pointer rounded-sm font-medium focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50">
            {block.summary}
          </summary>
          <div className="mt-3 space-y-3">
            {block.blocks.map((inner, index) => (
              <BlockView key={index} block={inner} />
            ))}
          </div>
        </details>
      );
  }
}
