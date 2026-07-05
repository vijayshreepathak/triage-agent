"use client";

import { useMemo, useRef, useState } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { StanceAgentLogo } from "./StanceAgentLogo";
import type { CaseItem } from "@/lib/types";

interface CaseSidebarProps {
  cases: CaseItem[];
  selectedId: string;
  onSelect: (item: CaseItem, index: number) => void;
  tab: "cases" | "history";
  onTabChange: (tab: "cases" | "history") => void;
  historySlot?: React.ReactNode;
  className?: string;
  onGuideTour: () => void;
  trace: boolean;
  onTraceChange: (value: boolean) => void;
}

export function CaseSidebar({
  cases,
  selectedId,
  onSelect,
  tab,
  onTabChange,
  historySlot,
  className = "",
  onGuideTour,
  trace,
  onTraceChange,
}: CaseSidebarProps) {
  const [query, setQuery] = useState("");
  const parentRef = useRef<HTMLDivElement>(null);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return cases;
    return cases.filter(
      (c) => c.patient_id.includes(q) || c.message.toLowerCase().includes(q),
    );
  }, [cases, query]);

  const selectedIndex = filtered.findIndex((c) => c.patient_id === selectedId);

  const virtualizer = useVirtualizer({
    count: filtered.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 104,
    overscan: 10,
  });

  const navigate = (delta: number) => {
    if (!filtered.length) return;
    let idx = selectedIndex >= 0 ? selectedIndex + delta : delta > 0 ? 0 : filtered.length - 1;
    if (idx < 0) idx = filtered.length - 1;
    if (idx >= filtered.length) idx = 0;
    onSelect(filtered[idx], idx);
  };

  return (
    <aside
      className={`flex h-full min-h-0 flex-col border-r border-white/10 bg-[#0c1220]/95 backdrop-blur-xl ${className}`}
    >
      <div className="hidden border-b border-white/10 p-4 lg:block">
        <StanceAgentLogo showWordmark />
      </div>
      <div className="border-b border-white/10 p-3 lg:hidden">
        <p className="text-sm font-semibold text-white">ViZ Triage agent</p>
        <p className="text-xs text-slate-400">{cases.length} clinical scenarios</p>
      </div>

      <div className="mx-3 mt-3 space-y-2.5 rounded-2xl border border-violet-500/25 bg-gradient-to-br from-indigo-600/15 via-transparent to-cyan-600/10 p-3 shadow-inner">
        <button
          type="button"
          onClick={onGuideTour}
          className="flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-violet-600 to-cyan-600 px-4 py-3 text-sm font-semibold text-white shadow-lg shadow-indigo-500/25 transition hover:brightness-110"
        >
          <span aria-hidden>✨</span>
          Give me a guide tour
        </button>
        <label className="flex cursor-pointer items-center gap-3 rounded-xl border border-white/10 bg-black/25 px-3.5 py-3 transition hover:border-cyan-500/30 hover:bg-white/[0.03]">
          <input
            type="checkbox"
            checked={trace}
            onChange={(e) => onTraceChange(e.target.checked)}
            className="h-4 w-4 shrink-0 rounded border-white/20 accent-cyan-500"
          />
          <div>
            <span className="block text-sm font-medium text-white">Execution trace</span>
            <span className="block text-[11px] leading-snug text-slate-400">
              LangGraph node-by-node details on each run
            </span>
          </div>
        </label>
      </div>

      <div className="flex gap-2 p-3">
        <button
          type="button"
          onClick={() => onTabChange("cases")}
          className={`flex-1 rounded-xl border px-3 py-2.5 text-sm font-medium transition ${
            tab === "cases"
              ? "border-cyan-500/50 bg-cyan-500/15 text-cyan-100"
              : "border-white/10 text-slate-400 hover:border-white/20"
          }`}
        >
          Cases <span className="ml-1 rounded-full bg-white/10 px-2 text-xs">{cases.length}</span>
        </button>
        <button
          type="button"
          onClick={() => onTabChange("history")}
          className={`flex-1 rounded-xl border px-3 py-2.5 text-sm font-medium transition ${
            tab === "history"
              ? "border-cyan-500/50 bg-cyan-500/15 text-cyan-100"
              : "border-white/10 text-slate-400 hover:border-white/20"
          }`}
        >
          History
        </button>
      </div>

      {tab === "cases" ? (
        <>
          <div className="space-y-2 px-3 pb-3">
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search all 100 cases…"
              className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm outline-none ring-cyan-500/40 placeholder:text-slate-500 focus:ring-2"
            />
            <div className="flex items-center justify-between text-sm text-slate-400">
              <button type="button" onClick={() => navigate(-1)} className="rounded-lg px-3 py-1.5 hover:bg-white/5">
                ◀ Prev
              </button>
              <span className="font-medium">
                {selectedIndex >= 0 ? `${selectedIndex + 1} / ${filtered.length}` : `— / ${filtered.length}`}
              </span>
              <button type="button" onClick={() => navigate(1)} className="rounded-lg px-3 py-1.5 hover:bg-white/5">
                Next ▶
              </button>
            </div>
          </div>

          <div ref={parentRef} className="min-h-0 flex-1 overflow-y-auto px-3 pb-4">
            <div style={{ height: `${virtualizer.getTotalSize()}px`, position: "relative" }}>
              {virtualizer.getVirtualItems().map((row) => {
                const item = filtered[row.index];
                const active = item.patient_id === selectedId;
                return (
                  <button
                    key={item.patient_id}
                    type="button"
                    onClick={() => onSelect(item, row.index)}
                    className={`absolute left-0 right-0 rounded-2xl border px-4 py-3 text-left transition ${
                      active
                        ? "border-cyan-500/50 bg-cyan-500/10 shadow-[0_0_24px_rgba(34,211,238,0.12)]"
                        : "border-white/5 bg-white/[0.02] hover:border-white/15 hover:bg-white/5"
                    }`}
                    style={{
                      top: 0,
                      height: `${row.size}px`,
                      transform: `translateY(${row.start}px)`,
                    }}
                  >
                    <div className="text-sm font-semibold text-cyan-200">{item.patient_id}</div>
                    <div className="mt-1 line-clamp-3 text-[13px] leading-relaxed text-slate-300">
                      {item.message}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        </>
      ) : (
        <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-4">{historySlot}</div>
      )}
    </aside>
  );
}
