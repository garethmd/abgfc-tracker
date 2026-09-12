import type { NextConfig } from "next";

// The browser only ever talks to the Next origin; /api/* is proxied to FastAPI so the
// session cookie is first-party and there's no CORS to configure.
const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${BACKEND_URL}/api/:path*` }];
  },
};

export default nextConfig;
