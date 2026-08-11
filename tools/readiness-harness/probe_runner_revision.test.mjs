import test from "node:test";
import assert from "node:assert/strict";

import { observeBuildRevision } from "./probe_runner.mjs";

test("strict revision observation preserves failure", async () => {
  const failure = async () => { throw new Error("timeout"); };
  await assert.rejects(() => observeBuildRevision(failure, false), /timeout/);
});

test("soft revision observation records unavailable evidence", async () => {
  const failure = async () => { throw new Error("timeout"); };
  assert.deepEqual(await observeBuildRevision(failure, true), {
    status: "UNAVAILABLE",
    revision: null,
    error: "timeout",
  });
});

test("successful revision observation remains immutable", async () => {
  const sha = "a".repeat(40);
  const success = async () => sha;
  assert.deepEqual(await observeBuildRevision(success, true), {
    status: "OBSERVED",
    revision: sha,
    error: null,
  });
});
