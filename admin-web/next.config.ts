import type { NextConfig } from "next";

/**
 * Proxy same-origin `/api/v1/*` to FastAPI (local or Render via BACKEND_URL).
 */
const nextConfig: NextConfig = {
  async rewrites() {
    const backend = (process.env.BACKEND_URL || "http://127.0.0.1:8001").replace(/\/$/, "");
    return [
      {
        source: "/api/v1/:path*",
        destination: `${backend}/api/v1/:path*`,
      },
      // Keep legacy admin rewrite available for MySQL-backed modules.
      {
        source: "/api/admin/:path*",
        destination: `${backend}/api/admin/:path*`,
      },
    ];
  },
};

export default nextConfig;
