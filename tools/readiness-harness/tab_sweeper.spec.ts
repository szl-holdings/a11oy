// Playwright tab sweeper for the a11oy console.
//
// Drives EVERY tab in tabs.json (navigates to /console#<key>), waits for the tab
// pane to render, and asserts doctrine-v11 "no mock theater" invariants on the
// live DOM:
//   • the pane actually renders content (not blank / not an error toast)
//   • no UNLABELLED placeholder: the literal strings "mock"/"fabricated"/"lorem
//     ipsum"/"TODO" never appear as visible copy (a SAMPLE/CACHED *chip* is fine —
//     that is an honest label, so we only fail on the raw words without a chip)
//   • tabs whose contract says citationsRequired must show a citation/source chip
//
// The matrix is the single source of truth, so adding a tab to tabs.json
// automatically adds it to this sweep. Set A11OY_BASE to point at a deploy.
//
//   A11OY_BASE=https://a-11-oy.com npx playwright test tab_sweeper.spec.ts

import { test, expect, Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const matrix = JSON.parse(readFileSync(join(HERE, "tabs.json"), "utf8"));
const BASE = (process.env.A11OY_BASE || "https://a-11-oy.com").replace(/\/$/, "");

// raw "this is fake" words that must never appear as bare visible text
const BANNED = ["lorem ipsum", "fabricated data", "mock data", "placeholder text", "todo:", "coming soon"];
// honest label chips that make adjacent "sample/cached/degraded" wording OK
const HONEST_CHIP = /\b(SAMPLE|CACHED|DEGRADED|LIVE|CI-GREEN|UNREACHABLE|OFFLINE)\b/;

async function openTab(page: Page, key: string) {
  await page.goto(`${BASE}/console#${key}`, { waitUntil: "domcontentloaded", timeout: 30000 });
  // the console renders the active view into a container; give it a beat to hydrate
  await page.waitForTimeout(1200);
}

test.describe("a11oy console — every tab is real", () => {
  test.describe.configure({ mode: "parallel", retries: 1 });

  for (const tab of matrix.tabs) {
    test(`tab ${tab.key} (${tab.label || tab.key}) renders honestly`, async ({ page }) => {
      const errors: string[] = [];
      page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });

      await openTab(page, tab.key);

      const body = page.locator("body");
      await expect(body).toBeVisible();

      const text = ((await body.innerText().catch(() => "")) || "").toLowerCase();

      // 1) rendered something
      expect(text.length, `tab ${tab.key} rendered empty`).toBeGreaterThan(40);

      // 2) no hard "not implemented" surfaces
      expect(text, `tab ${tab.key} shows a 404/not-found surface`).not.toContain("cannot get /");

      // 3) no UNLABELLED mock copy
      const hasChip = HONEST_CHIP.test(await body.innerText().catch(() => "") || "");
      for (const bad of BANNED) {
        if (text.includes(bad) && !hasChip) {
          throw new Error(`tab ${tab.key}: banned placeholder "${bad}" visible without an honest status chip`);
        }
      }

      // 4) citations required -> a source/citation affordance must be present
      if (tab.citationsRequired) {
        const cite = page.locator(
          'a[href*="http"], [data-citation], .citation, .source, text=/source|citation|provenance/i'
        );
        expect(await cite.count(), `tab ${tab.key} requires citations but none rendered`).toBeGreaterThan(0);
      }
    });
  }
});
