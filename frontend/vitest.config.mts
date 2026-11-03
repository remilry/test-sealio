import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// Same time zone on every machine (the users are in Switzerland; it also has DST to test against).
process.env.TZ = "Europe/Zurich";

export default defineConfig({
  plugins: [react()],
  resolve: { tsconfigPaths: true },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/shared/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    css: false,
  },
});
