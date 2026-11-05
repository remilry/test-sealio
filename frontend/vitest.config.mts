import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// Same time zone on every machine (the users are in Switzerland; it also has DST to test against).
process.env.TZ = "Europe/Zurich";

export default defineConfig({
  plugins: [react()],
  resolve: {
    tsconfigPaths: true,
    // PDF.js cannot render in jsdom: pages are stubbed, the field overlay stays real.
    alias: [
      // The package itself only: its stylesheets (the text layer's) still load.
      {
        find: /^react-pdf$/,
        replacement: fileURLToPath(
          new URL("./src/shared/test/mocks/react-pdf.tsx", import.meta.url),
        ),
      },
    ],
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/shared/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    css: false,
  },
});
