import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Нужен для docker-образа frontend (копируется .next/standalone).
  output: "standalone",
};

export default nextConfig;
