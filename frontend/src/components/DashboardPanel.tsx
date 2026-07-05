"use client";

import { motion } from "framer-motion";
import { AnimatedArrow } from "./AnimatedArrow";
import { resolveApiPath } from "@/lib/api-base";
import type { HealthResponse, StatsResponse } from "@/lib/types";

const ARCH = [
  "11-node LangGraph pipeline",
  "MCP medical-search agent",
  "Structured clinical extraction",
  "Deterministic red-flag engine",
  "Persisted audit trail",
];

const LEVELS = ["emergency", "high", "moderate", "low"] as const;
const COLORS: Record<string, string> = {
  emergency: "#ef4444",
  high: "#f97316",
  moderate: "#eab308",
  low: "#22c55e",
};

interface DashboardPanelProps {
  stats: StatsResponse | null;
  casesLoaded: number;
  health: HealthResponse | null;
  className?: string;
}

export function DashboardPanel({ stats, casesLoaded, health, className = "" }: DashboardPanelProps) {
  const total = stats?.total ?? 0;
  const by = stats?.by_urgency ?? {};

  return (
    <aside className={`flex h-full min-h-0 flex-col overflow-y-auto border-l border-white/10 bg-[#0c1220]/70 p-4 backdrop-blur-xl ${className}`}>
      <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-400">Dashboard</h3>

      {health?.mcp_agent && (
        <div
          className={`mb-4 rounded-xl border px-3 py-2.5 text-xs ${
            health.mcp_connected
              ? "border-cyan-500/40 bg-cyan-500/10 text-cyan-200"
              : "border-amber-500/40 bg-amber-500/10 text-amber-200"
          }`}
        >
          <div className="font-semibold">MCP Agent · {health.mcp_agent}</div>
          <div className="mt-1 opacity-80">
            {health.mcp_connected ? "Connected — evidence search ready" : "Start: python -m mcp_server.server"}
          </div>
        </div>
      )}
      <div className="mb-4 grid grid-cols-2 gap-2">
        <div className="rounded-xl border border-white/10 bg-white/5 p-3">
          <div className="text-[10px] uppercase text-slate-500">Total runs</div>
          <div className="text-2xl font-bold text-white">{total}</div>
        </div>
        <div className="rounded-xl border border-white/10 bg-white/5 p-3">
          <div className="text-[10px] uppercase text-slate-500">Cases loaded</div>
          <div className="text-2xl font-bold text-white">{casesLoaded}</div>
        </div>
      </div>

      {LEVELS.map((level) => {
        const count = by[level] ?? 0;
        const pct = total ? Math.round((count / total) * 100) : 0;
        return (
          <div key={level} className="mb-2">
            <div className="mb-1 flex justify-between text-[11px] capitalize text-slate-400">
              <span>{level}</span>
              <span>{count}</span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-white/10">
              <motion.div
                className="h-full rounded-full"
                style={{ background: COLORS[level] }}
                initial={{ width: 0 }}
                animate={{ width: `${pct}%` }}
                transition={{ duration: 0.6, ease: "easeOut" }}
              />
            </div>
          </div>
        );
      })}

      <h3 className="mb-2 mt-6 text-xs font-semibold uppercase tracking-wider text-slate-400">Quick links</h3>
      <div className="flex flex-col gap-1 text-xs">
        <a href={resolveApiPath("/docs")} target="_blank" rel="noreferrer" className="text-cyan-400 hover:underline">
          API Docs
        </a>
        <a href={resolveApiPath("/health")} target="_blank" rel="noreferrer" className="text-cyan-400 hover:underline">
          Health
        </a>
      </div>

      <h3 className="mb-3 mt-6 text-xs font-semibold uppercase tracking-wider text-slate-400">Architecture</h3>
      <ul className="space-y-2">
        {ARCH.map((line, i) => (
          <motion.li
            key={line}
            className="flex items-start gap-2 text-[11px] text-slate-300"
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.08 }}
          >
            <AnimatedArrow delay={i * 0.1} />
            <span>{line}</span>
          </motion.li>
        ))}
      </ul>
    </aside>
  );
}
