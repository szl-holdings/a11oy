import { defineConfig, devices } from "@playwright/test";

// Config for the a11oy readiness tab sweeper. Point A11OY_BASE at a live deploy
// (defaults to https://a-11-oy.com). No webServer is started — the sweeper checks a
// real running console, never a mock.
export default defineConfig({
  testDir: ".",
  testMatch: ["tab_sweeper.spec.ts"],
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 1,
  workers: process.env.CI ? 3 : 4,
  reporter: process.env.CI
    ? [["list"], ["json", { outputFile: "sweeper-report.json" }]]
    : [["list"]],
  use: {
    baseURL: process.env.A11OY_BASE || "https://a-11-oy.com",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
