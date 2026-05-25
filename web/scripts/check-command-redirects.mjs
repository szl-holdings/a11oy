#!/usr/bin/env node
/**
 * Static smoke test for the legacy `/command/*` → canonical `/a11oy/command/*`
 * redirect map in `artifacts/a11oy/src/App.tsx`. Guards the task #5090
 * consolidation against future route refactors.
 *
 * Run via: `node artifacts/a11oy/scripts/check-command-redirects.mjs`
 * or (wired) `pnpm run check:command-redirects`.
 */
import { readFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const appPath = resolve(here, "../src/App.tsx");
const src = readFileSync(appPath, "utf8");

const expectations = [
  { name: "canonical /a11oy/command home route", needle: 'path="/a11oy/command"' },
  { name: "canonical /a11oy/command/inbox route", needle: 'path="/a11oy/command/inbox"' },
  {
    name: "canonical /a11oy/command/frontier/proposals route",
    needle: 'path="/a11oy/command/frontier/proposals"',
  },
  {
    name: "canonical /a11oy/command/approvals route",
    needle: 'path="/a11oy/command/approvals"',
  },
  { name: "/command → /a11oy/command exact redirect", needle: '<RedirectTo to="/a11oy/command" />' },
  { name: "/command/:rest* wildcard redirect", needle: 'path="/command/:rest*"' },
  { name: "wildcard redirect targets /a11oy/command", needle: "to={`/a11oy/command${rest" },
  { name: "WithShell wraps CommandHome", needle: "<WithShell><CommandHome /></WithShell>" },
  { name: "WithShell wraps CommandInbox", needle: "<WithShell><CommandInbox /></WithShell>" },
  {
    name: "WithShell wraps CommandFrontierProposals",
    needle: "<WithShell><CommandFrontierProposals /></WithShell>",
  },
  { name: "WithShell wraps CommandApprovals", needle: "<WithShell><CommandApprovals /></WithShell>" },
];

const failures = expectations.filter((e) => !src.includes(e.needle));

if (failures.length > 0) {
  console.error("[check-command-redirects] FAIL — App.tsx is missing expected wiring:");
  for (const f of failures) {
    console.error(`  • ${f.name}\n      missing: ${f.needle}`);
  }
  process.exit(1);
}

console.log(
  `[check-command-redirects] OK · ${expectations.length} canonical Command routes + legacy redirects + WithShell wraps verified in App.tsx`,
);
