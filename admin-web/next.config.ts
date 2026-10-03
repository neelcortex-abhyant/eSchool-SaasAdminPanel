import type { NextConfig } from "next";

/**
 * Local FastAPI listens on 8001 while Laravel owns 8000.
 * Production cutover is reverse-proxy only; do not hardcode temporary FastAPI hostnames in client payloads.
 */
const nextConfig: NextConfig = {
  async rewrites() {
    const backend = process.env.BACKEND_URL || "http://127.0.0.1:8001";
    return [
      {
        source: "/api/admin/:path*",
        destination: `${backend}/api/admin/:path*`,
      },
    ];
  },
};

export default nextConfig;
