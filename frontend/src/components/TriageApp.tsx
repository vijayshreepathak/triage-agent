"use client";

import { motion } from "framer-motion";
import { useCallback, useEffect, useRef, useState } from "react";
import { useAppAuth } from "./Providers";
import { CaseSidebar } from "./CaseSidebar";
import { ConnectionBanner, LoadingShell } from "./ConnectionBanner";
import { DashboardPanel } from "./DashboardPanel";
import { Header } from "./Header";
import { MobileBottomNav } from "./MobileBottomNav";
import { TriageResultCard } from "./TriageResultCard";
import { VisualGuideModal } from "./VisualGuideModal";
import { bootstrapApp, getHistory, getStats, runDebug, runTriage } from "@/lib/api";
import type {
  AppConfig,
  CaseItem,
  HealthResponse,
  HistoryRecord,
  StatsResponse,
  TriageRunResult,
  TriageResponse,
} from "@/lib/types";

const CHIPS = [
  { id: "case_001", label: "Chest pain" },
  { id: "case_002", label: "Headache" },
  { id: "case_025", label: "Swallowed bone" },
  { id: "case_088", label: "Hand tremor" },
];

export function TriageApp() {
  const { getToken, isSignedIn, isLoaded, clerkEnabled } = useAppAuth();
  const [booting, setBooting] = useState(true);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [cases, setCases] = useState<CaseItem[]>([]);
  const [history, setHistory] = useState<HistoryRecord[]>([]);
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [selectedId, setSelectedId] = useState("");
  const [message, setMessage] = useState("");
  const [results, setResults] = useState<TriageRunResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<"cases" | "history">("cases");
  const [trace, setTrace] = useState(false);
  const [guideOpen, setGuideOpen] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [mobileView, setMobileView] = useState<"cases" | "chat" | "stats">("chat");
  const manualCounter = useRef(0);

  const backendOnline = health?.status === "ok" || health?.status === "degraded";
  const clerkRequired = clerkEnabled && (config?.auth_mode === "clerk" || health?.auth_mode === "clerk");
  const canRun = isLoaded && isSignedIn && backendOnline;

  const showToast = (msg: string) => {
    setToast(msg);
    window.setTimeout(() => setToast(null), 2800);
  };

  const token = useCallback(async () => {
    if (!isSignedIn) return null;
    return getToken();
  }, [isSignedIn, getToken]);

  const refreshProtected = useCallback(async () => {
    if (!isSignedIn) {
      setHistory([]);
      setStats(null);
      return;
    }
    try {
      const t = await token();
      const [h, s] = await Promise.all([getHistory(t), getStats(t)]);
      setHistory(h.records ?? []);
      setStats(s);
    } catch (e) {
      if (clerkRequired) {
        setError(e instanceof Error ? e.message : "Could not load your history");
      }
    }
  }, [clerkRequired, isSignedIn, token]);

  const loadApp = useCallback(async () => {
    setBooting(true);
    setError(null);
    try {
      const data = await bootstrapApp();
      setHealth(data.health);
      setConfig(data.config);
      setCases(data.cases);
      if (data.backendError) {
        setError(data.backendError);
      } else {
        showToast(`${data.cases.length} cases ready`);
      }
      if (data.casesFromFallback && data.cases.length > 0) {
        showToast(`${data.cases.length} cases loaded (offline dataset)`);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not connect");
    } finally {
      setBooting(false);
    }
  }, []);

  useEffect(() => {
    loadApp();
  }, [loadApp]);

  useEffect(() => {
    if (isLoaded) refreshProtected();
  }, [isLoaded, isSignedIn, refreshProtected]);

  const selectCase = (item: CaseItem) => {
    setSelectedId(item.patient_id);
    setMessage(item.message);
    setMobileView("chat");
  };

  const handleSend = async () => {
    const text = message.trim();
    if (!text || !canRun) return;
    setLoading(true);
    setError(null);
    const patientId = selectedId || `manual_${String(++manualCounter.current).padStart(3, "0")}`;
    try {
      const t = await token();
      if (trace) {
        const data = await runDebug(patientId, text, t);
        setResults((prev) => [
          ...prev,
          {
            triage: data.triage,
            trace: data.execution_trace,
            searchReason: data.search_decision_reason,
          },
        ]);
      } else {
        const triage = await runTriage(patientId, text, t);
        setResults((prev) => [...prev, { triage }]);
      }
      await refreshProtected();
      showToast("Done — saved to your history");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Triage failed");
    } finally {
      setLoading(false);
    }
  };

  if (booting) {
    return (
      <div className="grid h-screen place-items-center bg-[#06080f]">
        <LoadingShell />
      </div>
    );
  }

  return (
    <div className="relative grid h-[100dvh] grid-cols-1 overflow-hidden bg-[#06080f] text-slate-100 lg:grid-cols-[minmax(400px,32vw)_1fr_minmax(280px,24vw)]">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top_left,rgba(99,102,241,0.12),transparent_50%),radial-gradient(ellipse_at_bottom_right,rgba(34,211,238,0.08),transparent_45%)]" />

      <CaseSidebar
        className={`${mobileView === "cases" ? "flex" : "hidden"} lg:flex`}
        cases={cases}
        selectedId={selectedId}
        onSelect={selectCase}
        tab={tab}
        onTabChange={setTab}
        onGuideTour={() => setGuideOpen(true)}
        trace={trace}
        onTraceChange={setTrace}
        historySlot={
          history.length ? (
            history.map((r) => (
              <button
                key={`${r.patient_id}-${r.created_at}`}
                type="button"
                onClick={() => {
                  setSelectedId(r.patient_id);
                  setMessage(r.message);
                  setTab("cases");
                  setMobileView("chat");
                }}
                className="mb-2 w-full rounded-xl border border-transparent px-3 py-2.5 text-left transition hover:border-white/10 hover:bg-white/5"
              >
                <div className="text-sm font-semibold text-cyan-300">{r.patient_id}</div>
                <div className="line-clamp-2 text-sm leading-relaxed text-slate-300">{r.triage_decision}</div>
              </button>
            ))
          ) : (
            <p className="px-2 text-sm leading-relaxed text-slate-500">No past runs yet. Run your first triage to see history here.</p>
          )
        }
      />

      <section className={`relative z-10 flex min-h-0 min-w-0 flex-col pb-[72px] lg:pb-0 ${mobileView === "chat" ? "flex" : "hidden lg:flex"}`}>
        <Header health={health} config={config} onClear={() => setResults([])} onGuideTour={() => setGuideOpen(true)} />

        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4 sm:px-6 sm:py-6">
          {error && !results.length && (
            <div className="mb-6">
              <ConnectionBanner message={error} onRetry={loadApp} />
            </div>
          )}

          {!results.length && (
            <motion.div
              className="mx-auto max-w-xl py-12 text-center"
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
            >
              <h2 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
                Understand symptoms{" "}
                <span className="bg-gradient-to-r from-cyan-300 to-violet-400 bg-clip-text text-transparent">
                  with clarity
                </span>
              </h2>
              <p className="mt-4 text-base leading-relaxed text-slate-400">
                Choose a case from the left, or describe how you feel in plain language.
                ViZ Triage agent evaluates urgency and saves every result securely.
              </p>
              <div className="mt-8 flex flex-wrap justify-center gap-2">
                {CHIPS.map((chip, i) => (
                  <motion.button
                    key={chip.id}
                    type="button"
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.06 }}
                    onClick={() => {
                      const c = cases.find((x) => x.patient_id === chip.id);
                      if (c) selectCase(c);
                    }}
                    className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-slate-200 transition hover:border-cyan-500/40 hover:bg-cyan-500/10"
                  >
                    {chip.label}
                  </motion.button>
                ))}
              </div>
            </motion.div>
          )}

          <div className="mx-auto max-w-2xl space-y-5">
            {results.map((r) => (
              <TriageResultCard
                key={r.triage.request_id}
                result={r.triage}
                trace={r.trace}
                searchReason={r.searchReason}
              />
            ))}
            {error && results.length > 0 && (
              <ConnectionBanner message={error} onRetry={loadApp} />
            )}
          </div>
        </div>

        <footer className="relative z-10 border-t border-white/10 bg-[#0a101c]/90 p-3 backdrop-blur-xl sm:p-5">
          <div className="mx-auto flex max-w-3xl flex-col gap-3 sm:flex-row sm:gap-4">
            <textarea
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              disabled={!canRun || !backendOnline}
              rows={3}
              placeholder={
                !backendOnline
                  ? "Connect the API backend to run triage…"
                  : !isSignedIn
                    ? "Sign in to continue…"
                    : "Tell us what you're experiencing — chest pain, fever, dizziness, anything…"
              }
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              className="min-h-[88px] flex-1 resize-none rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-3.5 text-[15px] leading-relaxed text-slate-100 outline-none ring-cyan-500/30 placeholder:text-slate-500 focus:border-cyan-500/30 focus:ring-2 disabled:opacity-50"
            />
            <div className="flex flex-row gap-2 sm:flex-col">
              <button
                type="button"
                disabled={loading || !canRun || !backendOnline}
                onClick={handleSend}
                className="flex-1 rounded-2xl bg-gradient-to-r from-cyan-500 to-indigo-600 px-5 py-3.5 text-sm font-semibold text-white shadow-lg shadow-indigo-500/30 transition hover:brightness-110 disabled:opacity-45 sm:flex-none sm:px-6"
              >
                {loading ? "Analyzing…" : "Run Triage"}
              </button>
              <button
                type="button"
                disabled={!results.length}
                onClick={() => {
                  const last = results[results.length - 1];
                  if (last) navigator.clipboard.writeText(JSON.stringify(last.triage, null, 2));
                  showToast("Copied to clipboard");
                }}
                className="rounded-2xl border border-white/10 px-4 py-2.5 text-xs text-slate-300 hover:bg-white/5 disabled:opacity-40 sm:flex-none"
              >
                Copy JSON
              </button>
            </div>
          </div>
          <p className="mx-auto mt-3 max-w-3xl text-center text-xs text-slate-500">
            Press Enter to send · Shift+Enter for a new line · Not a substitute for emergency care
          </p>
        </footer>
      </section>

      <DashboardPanel
        className={`${mobileView === "stats" ? "flex" : "hidden"} pb-[72px] lg:flex lg:pb-0`}
        stats={stats}
        casesLoaded={cases.length}
        health={health}
      />

      <MobileBottomNav active={mobileView} onChange={setMobileView} caseCount={cases.length} />

      <VisualGuideModal open={guideOpen} onClose={() => setGuideOpen(false)} />

      {toast && (
        <motion.div
          className="fixed bottom-20 left-1/2 z-50 -translate-x-1/2 rounded-full border border-cyan-500/30 bg-[#0f1628]/95 px-6 py-2.5 text-sm text-cyan-100 shadow-xl backdrop-blur-md lg:bottom-8"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
        >
          {toast}
        </motion.div>
      )}
    </div>
  );
}
