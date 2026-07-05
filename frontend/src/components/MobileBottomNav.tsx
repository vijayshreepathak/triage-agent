"use client";

interface MobileBottomNavProps {
  active: "cases" | "chat" | "stats";
  onChange: (view: "cases" | "chat" | "stats") => void;
  caseCount: number;
}

const TABS = [
  { id: "cases" as const, label: "Cases", icon: "📋" },
  { id: "chat" as const, label: "Triage", icon: "⚕" },
  { id: "stats" as const, label: "Stats", icon: "📊" },
];

export function MobileBottomNav({ active, onChange, caseCount }: MobileBottomNavProps) {
  return (
    <nav className="fixed inset-x-0 bottom-0 z-40 border-t border-white/10 bg-[#0a101c]/95 backdrop-blur-xl lg:hidden">
      <div className="mx-auto flex max-w-lg">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => onChange(tab.id)}
            className={`flex flex-1 flex-col items-center gap-0.5 py-2.5 text-[11px] transition ${
              active === tab.id ? "text-cyan-300" : "text-slate-500"
            }`}
          >
            <span className="text-base">{tab.icon}</span>
            <span className="font-medium">{tab.label}</span>
            {tab.id === "cases" && (
              <span className="text-[10px] opacity-70">{caseCount}</span>
            )}
          </button>
        ))}
      </div>
      <div className="h-[env(safe-area-inset-bottom)]" />
    </nav>
  );
}
