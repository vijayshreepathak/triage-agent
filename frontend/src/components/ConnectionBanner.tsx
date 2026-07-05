"use client";

import { motion } from "framer-motion";

function isProductionHost(): boolean {
  if (typeof window === "undefined") return false;
  const host = window.location.hostname;
  return host !== "localhost" && host !== "127.0.0.1";
}

export function ConnectionBanner({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  const production = isProductionHost();

  return (
    <motion.div
      className="mx-auto max-w-xl rounded-2xl border border-amber-500/30 bg-amber-500/10 p-5 text-center"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
    >
      <p className="text-sm font-medium text-amber-100">Connection issue</p>
      <p className="mt-2 text-sm leading-relaxed text-amber-200/80">{message}</p>
      <button
        type="button"
        onClick={onRetry}
        className="mt-4 rounded-xl bg-amber-500/20 px-5 py-2 text-sm font-medium text-amber-100 ring-1 ring-amber-500/40 transition hover:bg-amber-500/30"
      >
        Try again
      </button>

      {production ? (
        <div className="mt-4 rounded-xl border border-white/10 bg-black/20 p-3 text-left text-xs text-slate-300">
          <p className="font-semibold text-amber-100">Vercel fix (2 steps)</p>
          <ol className="mt-2 list-decimal space-y-2 pl-4 leading-relaxed text-slate-400">
            <li>
              Deploy the FastAPI backend on{" "}
              <a
                href="https://render.com"
                target="_blank"
                rel="noreferrer"
                className="text-cyan-400 underline"
              >
                Render
              </a>{" "}
              (use this repo root + <code className="text-slate-300">render.yaml</code>).
            </li>
            <li>
              In Vercel → <strong className="text-slate-200">Settings → Environment Variables</strong>, add{" "}
              <code className="rounded bg-black/40 px-1 py-0.5 text-[11px] text-cyan-300">API_BACKEND_URL</code>{" "}
              = your public API URL, then <strong className="text-slate-200">Redeploy</strong>.
            </li>
          </ol>
        </div>
      ) : (
        <p className="mt-3 text-xs text-slate-500">
          Run in a terminal:{" "}
          <code className="rounded bg-black/30 px-1.5 py-0.5 text-[11px] text-slate-300">
            uvicorn app.api.main:app --port 8000
          </code>
        </p>
      )}
    </motion.div>
  );
}

export function LoadingShell() {
  return (
    <div className="flex flex-col items-center justify-center gap-4 py-24">
      <motion.div
        className="h-10 w-10 rounded-full border-2 border-indigo-500/30 border-t-cyan-400"
        animate={{ rotate: 360 }}
        transition={{ repeat: Infinity, duration: 0.9, ease: "linear" }}
      />
      <p className="text-sm text-slate-400">Connecting to ViZ Triage agent…</p>
    </div>
  );
}
