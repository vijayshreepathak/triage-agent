"use client";

import { motion } from "framer-motion";

export function AnimatedArrow({ delay = 0 }: { delay?: number }) {
  return (
    <motion.span
      className="inline-flex text-indigo-400"
      initial={{ opacity: 0, x: -6 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay, duration: 0.4 }}
    >
      <motion.svg
        width="14"
        height="14"
        viewBox="0 0 24 24"
        fill="none"
        aria-hidden
        animate={{ x: [0, 4, 0] }}
        transition={{ repeat: Infinity, duration: 1.6, delay, ease: "easeInOut" }}
      >
        <path
          d="M5 12h14M13 6l6 6-6 6"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </motion.svg>
    </motion.span>
  );
}
