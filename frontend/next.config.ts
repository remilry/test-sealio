import path from "node:path";
import type { NextConfig } from "next";

// The frontend is a standalone pnpm project inside the repo (no workspace): pin its root.
const root = path.join(__dirname);

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  outputFileTracingRoot: root,
  turbopack: {
    root,
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
