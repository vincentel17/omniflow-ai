import type { NextConfig } from "next";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));

const nextConfig: NextConfig = {
  reactStrictMode: true,
  output: process.env.NEXT_OUTPUT_STANDALONE === "1" ? "standalone" : undefined,
  outputFileTracingRoot: join(__dirname, "../.."),
  allowedDevOrigins: ["127.0.0.1"],
  distDir:
    process.env.PLAYWRIGHT === "1"
      ? ".next-playwright"
      : process.env.NEXT_DIST_DIR ?? ".next-build"
};

export default nextConfig;

