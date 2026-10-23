import type { NextConfig } from "next";

/**
 * API proxying is handled by App Router handlers:
 *   app/api/v1/[...path]/route.ts
 *   app/api/admin/[...path]/route.ts
 * Those read BACKEND_URL at runtime (required on Netlify).
 */
const nextConfig: NextConfig = {
  images: {
    // AVIF first (smallest), WebP fallback. Optimized results are cached for a day.
    formats: ["image/avif", "image/webp"],
    minimumCacheTTL: 86400,
    // Marketing and login images use quality={70}; 75 is the default.
    qualities: [70, 75],
    remotePatterns: [
      {
        protocol: "https",
        hostname: "images.unsplash.com",
      },
    ],
  },
  // Old School Admin menu slugs now have dedicated pages.
  async redirects() {
    return [
      { source: "/school/students-admission", destination: "/school/students/new", permanent: false },
      { source: "/school/student-details", destination: "/school/students", permanent: false },
      { source: "/school/guardian", destination: "/school/parents", permanent: false },
      { source: "/school/manage-teachers", destination: "/school/teachers", permanent: false },
    ];
  },
};

export default nextConfig;
