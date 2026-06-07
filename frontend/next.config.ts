import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [{ key: "Content-Type", value: "text/html; charset=utf-8" }],
      },
    ];
  },
  async rewrites() {
    return [{ source: "/operation", destination: "/" }];
  },
};

export default nextConfig;
