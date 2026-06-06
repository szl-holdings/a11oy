// Copyright 2026 SZL Holdings
// SPDX-License-Identifier: Apache-2.0
//
// Playwright config for szl-receipts journey tests.
// Reference: https://github.com/defenseunicorns/uds-common/blob/main/docs/uds-packages/guidelines/testing-guidelines.md

import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: ".",
  timeout: 30_000,
  use: {
    baseURL: process.env.RECEIPTS_HOST ?? "https://receipts.uds.dev",
    ignoreHTTPSErrors: true,
  },
  projects: [
    { name: "setup", testMatch: /auth\.setup\.ts/ },
    {
      name: "szl-receipts",
      dependencies: ["setup"],
      use: { storageState: "playwright/.auth/user.json" },
    },
  ],
});
