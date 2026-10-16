import type { NextConfig } from "next";

/**
 * API proxying is handled by App Router handlers:
 *   app/api/v1/[...path]/route.ts
 *   app/api/admin/[...path]/route.ts
 * Those read BACKEND_URL at runtime (required on Netlify).
 */
const nextConfig: NextConfig = {
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "images.unsplash.com",
      },
    ],
  },
};

export default nextConfig;
