// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// healthz-sha.test.ts — proves /healthz returns A11OY_GIT_SHA when the env is set.
//
// This is the L1 test: red-team finding L1 required /healthz to surface the
// running revision SHA, not "unknown". The fix is:
//   1. Dockerfile runtime stage: ARG REVISION=unknown; ENV A11OY_GIT_SHA=${REVISION}
//   2. docker-build.yml: --build-arg REVISION=${{ github.sha }}
//   3. serve.ts resolveGitSha(): already prefers process.env.A11OY_GIT_SHA
//
// This test verifies path 3 end-to-end using the real handleRoute function
// (no mocks; no stub asserts).
//
// Run: node --experimental-strip-types --test src/healthz-sha.test.ts
//
// Authored for SZL Holdings. Signed-off per repository DCO.
// Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>

import { test } from "node:test";
import assert from "node:assert/strict";
import { handleRoute, parseServeConfig } from "./serve.ts";

const FAKE_SHA = "abc123def456abc123def456abc123def456abc1";

test("GET /healthz returns A11OY_GIT_SHA env value when env is set", () => {
  // Set the env before calling parseServeConfig so resolveGitSha picks it up.
  const prev = process.env.A11OY_GIT_SHA;
  try {
    process.env.A11OY_GIT_SHA = FAKE_SHA;
    const config = parseServeConfig(["--port", "0", "--ledger", "/tmp/l1-test.jsonl"]);
    assert.equal(config.sha, FAKE_SHA, "parseServeConfig should read A11OY_GIT_SHA from env");

    const response = handleRoute("GET", new URL("http://localhost/healthz"), "", config);
    assert.equal(response.status, 200);

    const body = response.body as { status: string; sha: string; ts: string };
    assert.equal(body.status, "ok");
    assert.equal(body.sha, FAKE_SHA, "/healthz sha must match the env-supplied SHA");
    // ts must be a valid ISO timestamp.
    assert.ok(!Number.isNaN(Date.parse(body.ts)), "ts must be a valid ISO timestamp");
  } finally {
    // Restore env to avoid polluting other tests.
    if (prev === undefined) {
      delete process.env.A11OY_GIT_SHA;
    } else {
      process.env.A11OY_GIT_SHA = prev;
    }
  }
});

test("GET /healthz returns a non-empty sha when env is unset (git or unknown)", () => {
  const prev = process.env.A11OY_GIT_SHA;
  try {
    delete process.env.A11OY_GIT_SHA;
    const config = parseServeConfig(["--port", "0", "--ledger", "/tmp/l1-test2.jsonl"]);
    // Without the env, resolveGitSha falls back to git rev-parse or "unknown".
    assert.ok(config.sha.length > 0, "sha must be non-empty even without env");

    const response = handleRoute("GET", new URL("http://localhost/healthz"), "", config);
    assert.equal(response.status, 200);
    const body = response.body as { sha: string };
    assert.ok(body.sha.length > 0, "/healthz sha must be non-empty");
  } finally {
    if (prev === undefined) {
      delete process.env.A11OY_GIT_SHA;
    } else {
      process.env.A11OY_GIT_SHA = prev;
    }
  }
});
