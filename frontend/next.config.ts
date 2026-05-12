import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // `output: "standalone"` lo activa OpenCode en build de Docker via env var
  // NEXT_OUTPUT_STANDALONE. En Windows local rompe con EPERM symlink.
  ...(process.env.NEXT_OUTPUT_STANDALONE === "1"
    ? { output: "standalone" as const }
    : {}),
};

export default nextConfig;
