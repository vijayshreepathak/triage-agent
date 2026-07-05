import type { NextConfig } from "next";

const backend = process.env.API_BACKEND_URL ?? "http://127.0.0.1:8000";

if (process.env.VERCEL && !process.env.API_BACKEND_URL) {
  console.warn(
    "[ViZ Triage] API_BACKEND_URL is not set on Vercel. /api/* rewrites default to localhost and will fail in production.",
  );
}

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${backend}/:path*`,
      },
    ];
  },
};

export default nextConfig;
