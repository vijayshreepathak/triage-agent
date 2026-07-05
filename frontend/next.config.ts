import type { NextConfig } from "next";

/** Strip trailing slashes and a mistaken /api suffix (FastAPI routes are at /health not /api/health). */
function normalizeBackendUrl(raw: string): string {
  let url = raw.trim().replace(/\/+$/, "");
  if (url.endsWith("/api")) url = url.slice(0, -4);
  return url;
}

const backend = normalizeBackendUrl(process.env.API_BACKEND_URL ?? "http://127.0.0.1:8000");

if (process.env.VERCEL && !process.env.API_BACKEND_URL) {
  console.warn(
    "[ViZ Triage] API_BACKEND_URL is not set on Vercel. /engine/* rewrites default to localhost and will fail in production.",
  );
}

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        // Use /engine — not /api — so Clerk middleware does not intercept proxy requests.
        source: "/engine/:path*",
        destination: `${backend}/:path*`,
      },
    ];
  },
};

export default nextConfig;
