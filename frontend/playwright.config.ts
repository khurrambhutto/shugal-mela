import { defineConfig } from "@playwright/test";

// Runs the built frontend through FastAPI, the same way it is served to friends.
// Run `npm run build` first; `npm run test:browser` does both.
const PORT = 8765;

export default defineConfig({
  testDir: "tests/browser",
  testMatch: "*.e2e.ts",
  timeout: 30_000,
  expect: { timeout: 8_000 },
  workers: 1,
  use: { baseURL: `http://localhost:${PORT}`, browserName: "chromium" },
  webServer: {
    command: `uv run uvicorn app.main:app --host 127.0.0.1 --port ${PORT}`,
    cwd: "../backend",
    // Seeded dice make the full-match test repeatable. Never set DICE_SEED for real games.
    env: { APP_MODE: "development", ALLOWED_ORIGINS: `http://localhost:${PORT}`, DICE_SEED: "11" },
    url: `http://localhost:${PORT}/api/health`,
    reuseExistingServer: false,
  },
});
