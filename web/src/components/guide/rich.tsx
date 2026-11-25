import Link from "next/link";
import { guide } from "@/lib/guide";
import type { Segment } from "@/lib/guide-types";

export const LINK_CLASS =
  "rounded-sm underline underline-offset-4 hover:decoration-2 focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50";

/** Text with glossary terms as links (no hover, no pop-up): they go to the glossary page. */
export function Rich({ segments }: { segments: Segment[] }) {
  return (
    <>
      {segments.map((segment, index) =>
        segment.term ? (
          <Link key={index} href={`${guide.glossary_path}#${segment.term}`} className={LINK_CLASS}>
            {segment.t}
          </Link>
        ) : (
          <span key={index}>{segment.t}</span>
        ),
      )}
    </>
  );
}
