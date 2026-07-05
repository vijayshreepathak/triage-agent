export interface CaseItem {
  patient_id: string;
  message: string;
}

export interface HealthResponse {
  status: string;
  llm_provider: string;
  search_provider: string;
  database: string;
  database_connected: boolean;
  auth_mode: string;
  mcp_agent?: string;
  mcp_configured?: boolean;
  mcp_connected?: boolean;
}

export interface AppConfig {
  auth_mode: string;
  clerk_publishable_key: string;
  clerk_configured: boolean;
  search_provider: string;
  llm_provider: string;
  debug_enabled: boolean;
}

export interface TriageResponse {
  patient_message_id: string;
  urgency_level: "emergency" | "high" | "moderate" | "low";
  red_flags: string[];
  triage_decision: string;
  confidence: number;
  reasoning: string;
  disclaimers: string[];
  recommended_action: string;
  sources: string[];
  request_id: string;
}

export interface HistoryRecord {
  patient_id: string;
  message: string;
  urgency_level: string;
  confidence: number;
  triage_decision: string;
  created_at: string;
}

export interface TraceStep {
  node_name: string;
  status: string;
  latency_ms: number;
  retry_count: number;
  result_summary: string;
}

export interface TriageRunResult {
  triage: TriageResponse;
  trace?: TraceStep[];
  searchReason?: string;
}

export interface StatsResponse {
  total: number;
  by_urgency: Record<string, number>;
}
