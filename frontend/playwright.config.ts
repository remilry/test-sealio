import path from "node:path";
import { defineConfig, devices } from "@playwright/test";

/**
 * One e2e test for the main scenario (see docs/ARCHITECTURE.md), always in a dedicated, clean
 * environment, never the dev one: its own database (`formpilot_e2e`, dropped and created again at
 * each run), its own data folder (emptied), its own back and front on their own ports, the front
 * built into its own folder. PostgreSQL must be up (`make db`, done by `make e2e`).
 */
const API_PORT = 8100;
const FRONT_PORT = 3100;
const API_URL = `http://localhost:${API_PORT}`;
const FRONT_URL = `http://localhost:${FRONT_PORT}`;

const DATABASE_URL = "postgresql+psycopg://formpilot:formpilot@localhost:5432/formpilot_e2e";
const DATA_DIR = path.resolve(__dirname, "../data-e2e");

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: FRONT_URL,
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      // Clean state first, then the app migrates and seeds the empty database as on a first start.
      command: `uv run python -m scripts.reset_e2e && uv run fastapi run --port ${API_PORT}`,
      cwd: "../backend",
      env: {
        FORMPILOT_DATABASE_URL: DATABASE_URL,
        FORMPILOT_DATA_DIR: DATA_DIR,
        FORMPILOT_CORS_ORIGINS: JSON.stringify([FRONT_URL]),
        FORMPILOT_FAKE_LLM_LATENCY: "none",
      },
      url: `${API_URL}/health`,
      // Never reuse a server: it could be one with data, or the dev one.
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: `pnpm build && pnpm start --port ${FRONT_PORT}`,
      env: { NEXT_PUBLIC_API_URL: API_URL, NEXT_DIST_DIR: ".next-e2e" },
      url: FRONT_URL,
      reuseExistingServer: false,
      timeout: 180_000,
    },
  ],
});
