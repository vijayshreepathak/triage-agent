import type {
  AppConfig,
  CaseItem,
  HealthResponse,
  HistoryRecord,
  StatsResponse,
  TraceStep,
  TriageResponse,
} from "./types";

/** Same-origin proxy via Next.js rewrites — avoids CORS / failed fetch. */
const API_BASE = "/api";

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
        "Production backend not configured. In Vercel → Project Settings → Environment Variables, " +
        "set API_BACKEND_URL to your public Render/Railway API URL (e.g. https://triage-api.onrender.com), then redeploy."
      );
    }
  }
  return "Start the API locally: uvicorn app.api.main:app --host 127.0.0.1 --port 8000";
}

async function request<T>(path: string, init?: RequestInit, token?: string | null): Promise<T> {
  const headers: Record<string, string> = {
    ...(init?.headers as Record<string, string> | undefined),
  };
  if (token) headers.Authorization = `Bearer ${token}`;
  if (init?.body && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, { ...init, headers, cache: "no-store" });
  } catch {
    throw new Error(`Cannot reach the triage engine. ${backendHint()}`);
  }

  if (!res.ok) {
    const text = await res.text();
    const snippet = text.slice(0, 160).replace(/\s+/g, " ").trim();
    if (res.status === 404 && snippet.includes("DNS_HOSTNAME_RESOLVED_PRIVATE")) {
      throw new Error(
        `Backend URL points to a private address (localhost). ${backendHint()}`,
      );
    }
    throw new Error(`Request failed (${res.status}). ${snippet || "No response body"}`);
  }
  return res.json() as Promise<T>;
}

export function getHealth() {
  return request<HealthResponse>("/health");
}

export function getConfig() {
  return request<AppConfig>("/config");
}

export async function getCases(): Promise<CaseItem[]> {
  const data = await request<{ cases: CaseItem[] }>("/cases");
  return data.cases ?? [];
}

/** Bundled dataset when the API proxy is misconfigured or offline. */
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
  );
}

export function getHistory(token?: string | null) {
  return request<{ records: HistoryRecord[] }>("/history?limit=50", undefined, token);
}

export function getStats(token?: string | null) {
  return request<StatsResponse>("/stats", undefined, token);
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
