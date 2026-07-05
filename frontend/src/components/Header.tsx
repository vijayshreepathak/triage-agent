"use client";

import { Show, SignInButton, UserButton } from "@clerk/nextjs";
import { StanceAgentLogo } from "./StanceAgentLogo";
import type { HealthResponse } from "@/lib/types";

const hasClerkKey = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY);

function AccountIcon({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" aria-hidden>
      <circle cx="12" cy="8" r="4" stroke="currentColor" strokeWidth="1.75" />
      <path
        d="M5 20c0-3.314 3.134-6 7-6s7 2.686 7 6"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
      />
    </svg>
  );
}

interface HeaderProps {
  health: HealthResponse | null;
  onClear: () => void;
  onGuideTour?: () => void;
}

export function Header({ health, onClear, onGuideTour }: HeaderProps) {
  return (
    <header className="flex flex-wrap items-center gap-2 border-b border-white/10 bg-[#0c1220]/80 px-3 py-2.5 backdrop-blur-md sm:px-4 sm:py-3">
      <div className="mr-2 lg:hidden">
        <StanceAgentLogo size={36} />
      </div>
      <div className="flex max-w-full flex-1 gap-1.5 overflow-x-auto pb-0.5 sm:flex-wrap sm:overflow-visible sm:pb-0">
        {health && (
          <>
            <span className="shrink-0 rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] text-slate-400">
              LLM · {health.llm_provider}
            </span>
            <span className="shrink-0 rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] text-slate-400">
              Search · {health.search_provider}
            </span>
            {health.mcp_agent && (
              <span
                className={`shrink-0 rounded-full border px-2 py-0.5 text-[10px] ${
                  health.mcp_connected
                    ? "border-cyan-500/40 text-cyan-300"
                    : "border-amber-500/40 text-amber-300"
                }`}
              >
                MCP · {health.mcp_connected ? "live" : "offline"}
              </span>
            )}
            <span
              className={`shrink-0 rounded-full border px-2 py-0.5 text-[10px] ${
                health.database_connected
                  ? "border-emerald-500/40 text-emerald-400"
                  : "border-amber-500/40 text-amber-400"
              }`}
            >
              DB · {health.database} {health.database_connected ? "✓" : ""}
            </span>
          </>
        )}
      </div>
      <div className="hidden flex-1 lg:block" />
      <div className="flex shrink-0 items-center gap-1.5">
        {onGuideTour && (
          <button
            type="button"
            onClick={onGuideTour}
            className="rounded-lg border border-violet-500/40 bg-violet-500/15 px-2.5 py-1.5 text-xs font-medium text-violet-200 hover:bg-violet-500/25 lg:hidden"
          >
            Guide tour
          </button>
        )}
        <button
          type="button"
          onClick={onClear}
          className="rounded-lg border border-white/10 px-2.5 py-1.5 text-xs hover:bg-white/5 sm:px-3"
        >
          Clear chat
        </button>
        {hasClerkKey && (
          <div className="flex items-center">
            <Show when="signed-out">
              <SignInButton mode="modal">
                <button
                  type="button"
                  className="flex items-center gap-1.5 rounded-lg border border-indigo-500/40 bg-indigo-500/15 px-2.5 py-1.5 text-xs font-medium text-indigo-100 hover:bg-indigo-500/25"
                  aria-label="Sign in"
                >
                  <AccountIcon />
                  <span className="hidden sm:inline">Sign in</span>
                </button>
              </SignInButton>
            </Show>
            <Show when="signed-in">
              <UserButton
                appearance={{
                  variables: { colorPrimary: "#6366f1", colorBackground: "#0c1220" },
                  elements: {
                    avatarBox: "h-8 w-8 ring-2 ring-indigo-500/40",
                  },
                }}
              />
            </Show>
          </div>
        )}
      </div>
    </header>
  );
}
