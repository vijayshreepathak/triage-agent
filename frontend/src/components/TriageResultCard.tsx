"use client";

import { motion } from "framer-motion";
import type { TriageResponse, TraceStep } from "@/lib/types";

const URGENCY_STYLES: Record<string, string> = {
  emergency: "bg-red-500/20 text-red-300 border-red-500/40",
  high: "bg-orange-500/20 text-orange-300 border-orange-500/40",
  moderate: "bg-yellow-500/20 text-yellow-300 border-yellow-500/40",
  low: "bg-emerald-500/20 text-emerald-300 border-emerald-500/40",
};

export function TriageResultCard({
  result,
  trace,
  searchReason,
}: {
  result: TriageResponse;
  trace?: TraceStep[];
  searchReason?: string;
}) {
  return (
    <motion.div
      className="rounded-2xl border border-white/10 bg-[#121a2e]/90 p-5 shadow-xl"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
    >
      <div className="mb-3 flex flex-wrap items-center gap-3">
        <span
          className={`rounded-full border px-3 py-0.5 text-xs font-semibold uppercase ${URGENCY_STYLES[result.urgency_level]}`}
        >
          {result.urgency_level}
        </span>
        <span className="text-xs text-slate-400">confidence {result.confidence}/100</span>
        <div className="h-1.5 flex-1 min-w-[100px] overflow-hidden rounded-full bg-white/10">
          <motion.div
            className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-violet-500"
            initial={{ width: 0 }}
            animate={{ width: `${result.confidence}%` }}
            transition={{ duration: 0.8 }}
          />
        </div>
      </div>
      <p className="mb-2 text-sm font-medium text-white">{result.triage_decision}</p>
      <p className="mb-3 text-sm leading-relaxed text-slate-300">{result.reasoning}</p>
      {result.red_flags.length > 0 && (
        <div className="mb-3 flex flex-wrap gap-2">
          {result.red_flags.map((f) => (
            <span key={f} className="rounded-lg border border-red-500/30 bg-red-500/10 px-2 py-0.5 text-[11px] text-red-200">
              {f}
            </span>
          ))}
        </div>
      )}
      <p className="mb-3 text-sm text-indigo-200">{result.recommended_action}</p>
      <div className="mb-3 space-y-1">
        {result.sources.length ? (
          result.sources.map((url) => (
            <a key={url} href={url} target="_blank" rel="noreferrer" className="block truncate text-xs text-indigo-400 hover:underline">
              {url}
            </a>
          ))
        ) : (
          <p className="text-xs text-slate-500">No verified external source found.</p>
        )}
      </div>
      <p className="text-[11px] text-slate-500">{result.disclaimers.join(" ")}</p>
      <p className="mt-2 text-[10px] text-slate-600">request {result.request_id} · recorded</p>
      {trace && trace.length > 0 && (
        <details className="mt-4 rounded-xl border border-white/10 bg-black/20 p-3">
          <summary className="cursor-pointer text-xs font-medium text-cyan-300">
            Execution trace · {trace.length} nodes{searchReason ? ` · ${searchReason}` : ""}
          </summary>
          <div className="mt-3 max-h-48 overflow-auto">
            <table className="w-full text-left text-[11px] text-slate-400">
              <thead>
                <tr className="text-slate-500">
                  <th className="pb-2 pr-2">Node</th>
                  <th className="pb-2 pr-2">Status</th>
                  <th className="pb-2 pr-2">ms</th>
                </tr>
              </thead>
              <tbody>
                {trace.map((t) => (
                  <tr key={t.node_name} className="border-t border-white/5">
                    <td className="py-1.5 pr-2 font-mono text-slate-300">{t.node_name}</td>
                    <td className="py-1.5 pr-2">{t.status}</td>
                    <td className="py-1.5">{t.latency_ms.toFixed(0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}
    </motion.div>
  );
}
