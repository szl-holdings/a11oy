// Copyright 2026 SZL Holdings
// SPDX-License-Identifier: Apache-2.0
//
// Playwright auth setup — handles Keycloak SSO login before journey tests.

import { test as setup } from "@playwright/test";
import * as fs from "fs";

const authFile = "playwright/.auth/user.json";

setup("authenticate via Keycloak SSO", async ({ page }) => {
  const host = process.env.RECEIPTS_HOST ?? "https://receipts.uds.dev";
  const username = process.env.SSO_USER ?? "testuser";
  const password = process.env.SSO_PASSWORD ?? "testpassword";

  await page.goto(host);
  // Keycloak login form
  await page.fill("#username", username);
  await page.fill("#password", password);
  await page.click('input[type="submit"]');
  await page.waitForURL(host + "/**");

  fs.mkdirSync("playwright/.auth", { recursive: true });
  await page.context().storageState({ path: authFile });
});
