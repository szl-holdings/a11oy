// SPDX-License-Identifier: Apache-2.0
// (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
//
// Runs the exact bundle `wrangler deploy` would upload inside workerd, with the
// bindings declared in wrangler.toml (wrangler's own test harness). workerd
// provides the real `cloudflare:email` EmailMessage class; the local
// send_email binding parses the raw MIME and rejects a missing Message-ID or a
// From header that differs from the envelope sender. No Cloudflare account and
// no outbound mail. Needs `npm ci` (wrangler from the committed lockfile).

import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, readdirSync, rmSync, statSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { createTestHarness } from "wrangler";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const SECRET = "workerd-synthetic-test-secret-0123456789abcdef";
const REVISION = "fedcba9876543210fedcba9876543210fedcba98";
const ORIGIN = "https://szl-email-sender.example.workers.dev";

function bundle(outdir) {
  execFileSync(
    process.execPath,
    [path.join(ROOT, "node_modules", "wrangler", "bin", "wrangler.js"), "deploy", "--dry-run", "--outdir", outdir],
    { cwd: ROOT, env: { ...process.env, CI: "true", WRANGLER_SEND_METRICS: "false" }, stdio: "pipe" },
  );
}

function emlFiles(directory, since) {
  if (!existsSync(directory)) {
    return [];
  }
  const found = [];
  for (const entry of readdirSync(directory, { withFileTypes: true, recursive: true })) {
    const full = path.join(entry.parentPath ?? entry.path, entry.name);
    if (entry.isFile() && entry.name.endsWith(".eml") && statSync(full).mtimeMs >= since) {
      found.push(full);
    }
  }
  return found;
}

async function waitForStoredEmail(since) {
  // The local binding persists the accepted message after the response.
  for (let attempt = 0; attempt < 100; attempt += 1) {
    const found = emlFiles(path.join(ROOT, ".wrangler"), since);
    if (found.length > 0) {
      assert.equal(found.length, 1, `expected exactly one stored message, got ${found.length}`);
      return readFileSync(found[0], "utf8");
    }
    await new Promise((resolve) => setTimeout(resolve, 50));
  }
  assert.fail("the local send_email binding never stored the accepted message");
}

function decodeSubject(head) {
  const folded = /^Subject: (.*(?:\r\n .*)*)$/m.exec(head)[1].replace(/\r\n /g, " ");
  return folded
    .split(" ")
    .map((word) => Buffer.from(/^=\?UTF-8\?B\?(.*)\?=$/.exec(word)[1], "base64").toString("utf8"))
    .join("");
}

test("workerd accepts the Worker's EmailMessage and MIME through send_email", async (t) => {
  const outdir = mkdtempSync(path.join(tmpdir(), "szl-email-sender-"));
  t.after(() => rmSync(outdir, { recursive: true, force: true }));
  bundle(outdir);

  const server = createTestHarness({
    root: ROOT,
    workers: [
      {
        configPath: "wrangler.toml",
        prebuiltWorkerDir: outdir,
        vars: { SOURCE_REVISION: REVISION },
        secrets: { API_SECRET: SECRET },
      },
    ],
  });
  t.after(() => server.close());
  await server.listen();

  const revision = await server.fetch(`${ORIGIN}/.well-known/szl-worker-revision`);
  assert.equal(revision.status, 200);
  assert.deepEqual(await revision.json(), {
    worker: "szl-email-sender",
    source_revision: REVISION,
    ready: true,
  });

  const subject = "Recibo verificado ✅ — canary";
  const since = Date.now() - 1000;
  const response = await server.fetch(`${ORIGIN}/send`, {
    method: "POST",
    headers: { authorization: `Bearer ${SECRET}`, "content-type": "application/json" },
    body: JSON.stringify({ to: "owner@example.org", subject, body: "Línea uno\nLine two\n.\n" }),
  });
  const result = await response.json();
  assert.equal(response.status, 200, JSON.stringify(result));
  assert.equal(result.success, true);

  const raw = await waitForStoredEmail(since);
  const head = raw.slice(0, raw.indexOf("\r\n\r\n"));
  assert.match(head, /^From: betterwithage@a-11-oy\.com$/m);
  assert.match(head, /^To: owner@example\.org$/m);
  assert.match(head, /^Content-Type: text\/plain; charset=utf-8$/m);
  assert.match(head, /^Content-Transfer-Encoding: base64$/m);
  assert.match(head, /^Message-ID: <[^>\r\n]+>$/m);
  assert.equal(decodeSubject(head), subject);
  const body = Buffer.from(raw.slice(raw.indexOf("\r\n\r\n") + 4).replace(/\r\n/g, ""), "base64");
  assert.equal(body.toString("utf8"), "Línea uno\r\nLine two\r\n.\r\n");

  const injected = await server.fetch(`${ORIGIN}/send`, {
    method: "POST",
    headers: { authorization: `Bearer ${SECRET}`, "content-type": "application/json" },
    body: JSON.stringify({ to: "owner@example.org\r\nBcc: attacker@example.net", subject, body: "x" }),
  });
  assert.equal(injected.status, 400);
  assert.deepEqual(await injected.json(), { error: "invalid_to" });

  const unauthenticated = await server.fetch(`${ORIGIN}/send`, {
    method: "POST",
    headers: { authorization: "Bearer undefined", "content-type": "application/json" },
    body: "{}",
  });
  assert.equal(unauthenticated.status, 401);
  assert.equal(unauthenticated.headers.get("access-control-allow-origin"), null);
});
