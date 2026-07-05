"use client";

import { motion } from "framer-motion";

interface LogoProps {
  size?: number;
  showWordmark?: boolean;
}

export function StanceAgentLogo({ size = 44, showWordmark = false }: LogoProps) {
  return (
    <div className="flex items-center gap-3">
      <motion.div
        className="relative shrink-0"
        style={{ width: size, height: size }}
        whileHover={{ scale: 1.04 }}
        transition={{ type: "spring", stiffness: 400, damping: 18 }}
      >
        <motion.div
          className="absolute inset-0 rounded-[14px] bg-gradient-to-br from-cyan-400 via-indigo-500 to-violet-600 opacity-40 blur-md"
          animate={{ scale: [1, 1.08, 1], opacity: [0.35, 0.55, 0.35] }}
          transition={{ repeat: Infinity, duration: 3, ease: "easeInOut" }}
        />
        <svg
          viewBox="0 0 48 48"
          width={size}
          height={size}
          className="relative rounded-[14px] shadow-lg shadow-indigo-500/30"
          aria-hidden
        >
          <defs>
            <linearGradient id="sa-bg" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#22d3ee" />
              <stop offset="50%" stopColor="#6366f1" />
              <stop offset="100%" stopColor="#8b5cf6" />
            </linearGradient>
            <linearGradient id="sa-stroke" x1="0%" y1="100%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#a5f3fc" />
              <stop offset="100%" stopColor="#c4b5fd" />
            </linearGradient>
          </defs>
          <rect x="2" y="2" width="44" height="44" rx="13" fill="url(#sa-bg)" />
          <text x="24" y="28" fill="#fff" fontSize="14" fontWeight="700" textAnchor="middle">ViZ</text>
        </svg>
      </motion.div>
      {showWordmark && (
        <div>
          <div className="text-sm font-semibold tracking-tight text-white">
            ViZ Triage <span className="text-cyan-300">agent</span>
          </div>
          <div className="text-[11px] text-slate-400">Clinical co-pilot · LangGraph</div>
        </div>
      )}
    </div>
  );
}
