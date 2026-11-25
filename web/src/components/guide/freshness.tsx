"use client";

import useSWR from "swr";
import { getTransparency } from "@/lib/api";
import { guide } from "@/lib/guide";

/**
 * Progressive check: if the API answers and runs another rule book version than the one this guide was
 * generated from, say so. It never blocks the page and shows nothing when the API is down.
 */
export function Freshness() {
  const { data } = useSWR("/api/transparency", () => getTransparency(), {
    revalidateOnFocus: false,
    shouldRetryOnError: false,
  });
  const live = data?.live.rules_id;
  const outdated = live !== undefined && live !== guide.rules_id;
  return (
    <div role="status" aria-live="polite">
      {outdated ? (
        <p className="rounded-lg border border-destructive/40 bg-card px-3 py-2 text-sm">
          <strong>Atenção:</strong>{" "}
          {guide.freshness_warning.replace("${page_rules_id}", guide.rules_id).replace("${live_rules_id}", live)}
        </p>
      ) : null}
    </div>
  );
}
