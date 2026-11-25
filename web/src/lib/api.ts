import type { Job, ProfileIn, Transparency, Triage } from "./api-types";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

async function readError(res: Response): Promise<ApiError> {
  let detail = `${res.status} ${res.statusText}`;
  try {
    const body = await res.json();
    if (typeof body.detail === "string") detail = body.detail;
    else if (Array.isArray(body.detail)) {
      detail = body.detail
        .map((d: { loc?: unknown[]; msg?: string }) => `${d.loc?.slice(-1)[0] ?? "campo"}: ${d.msg}`)
        .join("; ");
    }
  } catch {
    // keep the status line
  }
  return new ApiError(detail, res.status);
}

export async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw await readError(res);
  return res.json();
}

export async function postJson<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw await readError(res);
  return res.json();
}

export const postTriage = (profile: ProfileIn, topK = 3) =>
  postJson<Triage>("/api/triage", { profile, top_k: topK });

export const startReport = (profile: ProfileIn, topK = 3) =>
  postJson<Job>("/api/report", { profile, top_k: topK });

export const getTransparency = () => getJson<Transparency>("/api/transparency");
