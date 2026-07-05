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
    throw new Error(
      "Cannot reach the triage engine. Start the API with: uvicorn app.api.main:app --port 8000",
    );
  }

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Request failed (${res.status}). ${text.slice(0, 120)}`);
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

export async function bootstrapApp() {
  const [health, config, cases] = await Promise.all([getHealth(), getConfig(), getCases()]);
  return { health, config, cases };
}
