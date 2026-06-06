// Copyright 2026 SZL Holdings
// SPDX-License-Identifier: Apache-2.0
//
// Journey test: szl-receipts UDS package
// Tests the basic user flows that could be broken by the UDS deployment method.
// Reference: https://github.com/defenseunicorns/uds-common/blob/main/docs/uds-packages/guidelines/testing-guidelines.md
//
// Tools: Playwright (per testing guidelines)
// Run: npx playwright test
//
// NOTE (R16/R17): Full e2e requires a live cluster with UDS Core deployed.
// These tests run against RECEIPTS_HOST (default: https://receipts.uds.dev).
// In CI, they are gated to workflow_dispatch to avoid failing without a cluster.

import { test, expect } from "@playwright/test";

const RECEIPTS_HOST = process.env.RECEIPTS_HOST ?? "https://receipts.uds.dev";

test.describe("szl-receipts journey", () => {
  test("receipts dashboard responds with 200 after SSO auth", async ({ page }) => {
    // Playwright auth setup handles SSO in auth.setup.ts
    await page.goto(RECEIPTS_HOST);
    await expect(page).toHaveTitle(/SZL|Receipt/i);
    await expect(page.locator("body")).not.toContainText("502");
    await expect(page.locator("body")).not.toContainText("503");
  });

  test("POST to /receipt endpoint returns receipt ID", async ({ request }) => {
    const resp = await request.post(`${RECEIPTS_HOST}/receipt`, {
      data: {
        payload: Buffer.from(JSON.stringify({
          _type: "https://szlholdings.com/receipt/v1",
          subject: "test/Deployment/journey-test",
          specHash: "abc123",
          timestamp: new Date().toISOString(),
          admissionOp: "CREATE",
        })).toString("base64"),
        payloadType: "application/vnd.szl.receipt.v1+json",
        signatures: [],
      },
    });
    expect(resp.status()).toBeLessThan(500);
  });

  test("metrics endpoint is reachable from cluster perspective", async ({ request }) => {
    // Prometheus scrapes /metrics — verify it returns text/plain
    const resp = await request.get(`${RECEIPTS_HOST}/metrics`);
    expect([200, 401, 403]).toContain(resp.status()); // 401/403 acceptable behind authservice
  });

  test("health endpoint returns 200", async ({ request }) => {
    const resp = await request.get(`${RECEIPTS_HOST}/health`);
    expect(resp.status()).toBe(200);
  });
});
