import { defineConfig, devices } from "@playwright/test";

/**
 * FinAlly E2E config.
 *
 * Specs share one app instance and one database, so they run serially in file
 * order (01-fresh-start first, while the DB is still fresh). Point BASE_URL at
 * the app: the docker-compose.test.yml run sets it to http://app:8000.
 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 30_000,
  expect: { timeout: 10_000 },
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: process.env.BASE_URL ?? "http://localhost:8000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1600, height: 1000 } } }],
});
