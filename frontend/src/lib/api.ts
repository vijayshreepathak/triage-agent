import type {
  AppConfig,
  CaseItem,
  HealthResponse,
  HistoryRecord,
  StatsResponse,
  TraceStep,
  TriageResponse,
} from "./types";
import { resolveApiPath } from "./api-base";

export type BootstrapResult = {
  health: HealthResponse | null;
  config: AppConfig | null;
  cases: CaseItem[];
  backendError: string | null;
  casesFromFallback: boolean;
};

function backendHint(): string {
  if (typeof window !== "undefined") {
    const host = window.location.hostname;
    if (host.endsWith(".vercel.app") || (host !== "localhost" && host !== "127.0.0.1")) {
      return (
        "Set NEXT_PUBLIC_API_URL=https://triage-agent-7xts.onrender.com on Vercel (direct calls avoid proxy timeouts). " +
        "Also set CORS_ORIGINS=https://vizagent-dun.vercel.app on Render."
      );
    }
  }
  return "Start the API locally: uvicorn app.api.main:app --host 127.0.0.1 --port 8000";
}

function friendlyHttpError(status: number, raw: string): string {
  const html = raw.trim().startsWith("<!DOCTYPE") || raw.trim().startsWith("<html");
  if (status === 401) {
    return "Authentication required. Sign in again — and ensure Render has AUTH_MODE=clerk with CLERK_ISSUER set.";
  }
  if (status === 502 || status === 504 || (html && status >= 500)) {
    return (
      "Backend timed out or is waking up (common on Render free tier during triage). " +
      "Wait ~30 seconds and try again. " +
      backendHint()
    );
  }
  if (status === 404 && raw.includes("DNS_HOSTNAME_RESOLVED_PRIVATE")) {
    return `Backend URL points to localhost. ${backendHint()}`;
  }
  const snippet = raw.slice(0, 120).replace(/\s+/g, " ").trim();
  return html
    ? `Request failed (${status}). Backend unavailable — try again in a moment.`
    : `Request failed (${status}). ${snippet || "No response body"}`;
}

async function request<T>(
  path: string,
  init?: RequestInit,
  token?: string | null,
  timeoutMs = 120_000,
): Promise<T> {
  const headers: Record<string, string> = {
    ...(init?.headers as Record<string, string> | undefined),
  };
  if (token) headers.Authorization = `Bearer ${token}`;
  if (init?.body && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);

  let res: Response;
  try {
    res = await fetch(resolveApiPath(path), {
      ...init,
      headers,
      cache: "no-store",
      signal: controller.signal,
    });
  } catch (e) {
    if (e instanceof Error && e.name === "AbortError") {
      throw new Error(`Triage timed out after ${timeoutMs / 1000}s. ${backendHint()}`);
    }
    throw new Error(`Cannot reach the triage engine. ${backendHint()}`);
  } finally {
    window.clearTimeout(timer);
  }

  if (!res.ok) {
    const text = await res.text();
    throw new Error(friendlyHttpError(res.status, text));
  }
  return res.json() as Promise<T>;
}

export function getHealth() {
  return request<HealthResponse>("/health", undefined, null, 30_000);
}

export function getConfig() {
  return request<AppConfig>("/config", undefined, null, 30_000);
}

export async function getCases(): Promise<CaseItem[]> {
  const data = await request<{ cases: CaseItem[] }>("/cases", undefined, null, 30_000);
  return data.cases ?? [];
}

export async function getCasesFallback(): Promise<CaseItem[]> {
  const res = await fetch("/data/cases.json", { cache: "force-cache" });
  if (!res.ok) throw new Error("Local case dataset unavailable");
  const data = (await res.json()) as { cases: CaseItem[] };
  return data.cases ?? [];
}

export async function getCasesWithFallback(): Promise<{ cases: CaseItem[]; fromFallback: boolean }> {
  try {
    const cases = await getCases();
    return { cases, fromFallback: false };
  } catch {
    const cases = await getCasesFallback();
    return { cases, fromFallback: true };
  }
}

export function runTriage(patientId: string, message: string, token?: string | null) {
  return request<TriageResponse>(
    "/triage",
    {
      method: "POST",
      body: JSON.stringify({ patient_id: patientId, message }),
    },
    token,
    180_000,
  );
}

export function runDebug(patientId: string, message: string, token?: string | null) {
  return request<{ triage: TriageResponse; execution_trace: TraceStep[]; search_decision_reason?: string }>(
    "/debug",
    {
      method: "POST",
      body: JSON.stringify({ patient_id: patientId, message }),
    },
    token,
    180_000,
  );
}

export function getHistory(token?: string | null) {
  return request<{ records: HistoryRecord[] }>("/history?limit=50", undefined, token, 30_000);
}

export function getStats(token?: string | null) {
  return request<StatsResponse>("/stats", undefined, token, 30_000);
}

export async function bootstrapApp(): Promise<BootstrapResult> {
  const { cases, fromFallback } = await getCasesWithFallback();
  let health: HealthResponse | null = null;
  let config: AppConfig | null = null;
  let backendError: string | null = null;

  try {
    [health, config] = await Promise.all([getHealth(), getConfig()]);
  } catch (e) {
    backendError = e instanceof Error ? e.message : "Backend unavailable";
  }

  return { health, config, cases, backendError, casesFromFallback: fromFallback };
}
