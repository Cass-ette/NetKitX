import type { NextConfig } from "next";
import { dirname } from "path";
import { fileURLToPath } from "url";

const turbopackRoot = dirname(fileURLToPath(import.meta.url));

const nextConfig: NextConfig = {
  output: "standalone",
  turbopack: {
    root: turbopackRoot,
  },
};

export default nextConfig;
