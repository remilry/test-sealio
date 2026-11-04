import path from "node:path";
import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./src/shared/i18n/request.ts");

// The frontend is a standalone pnpm project inside the repo (no workspace): pin its root.
const root = path.join(__dirname);

const nextConfig: NextConfig = {
  // The e2e build goes to its own folder (playwright.config.ts) so it never touches the dev server's.
  distDir: process.env.NEXT_DIST_DIR ?? ".next",
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

export default withNextIntl(nextConfig);
