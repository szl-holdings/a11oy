import test from "node:test";
import assert from "node:assert/strict";

import {
  TERMINAL_STATES,
  assessHonesty,
  assessReadiness,
  isTerminalState,
  observation,
  observeJson,
} from "../src/index.js";

test("public states exclude indefinite loading labels", () => {
  assert.equal(isTerminalState("CHECKING"), false);
  assert.equal(isTerminalState("CONNECTING"), false);
  assert.equal(isTerminalState("LOADING"), false);
  assert.deepEqual(TERMINAL_STATES, [
    "VERIFIED",
    "REACHABLE",
    "DEGRADED",
    "STALE",
    "FAILED",
    "BLOCKED",
    "UNAVAILABLE",
  ]);
});

test("unsupported public states fail closed", () => {
  assert.throws(() => observation("GREEN", "not a contract state"), TypeError);
});

test("missing fetch transport terminates as unavailable", async () => {
  const result = await observeJson("https://example.invalid", { fetchImpl: null });
  assert.equal(result.state, "UNAVAILABLE");
});

test("timeout terminates as unavailable", async () => {
  const result = await observeJson("https://example.invalid", {
    timeoutMs: 10,
    fetchImpl: () => new Promise(() => {}),
  });
  assert.equal(result.state, "UNAVAILABLE");
  assert.match(result.detail, /10 ms/);
});

test("non-2xx response terminates as failed", async () => {
  const result = await observeJson("https://example.invalid", {
    fetchImpl: async () => ({ ok: false, status: 503 }),
  });
  assert.equal(result.state, "FAILED");
  assert.equal(result.httpStatus, 503);
});

test("invalid JSON terminates as failed", async () => {
  const result = await observeJson("https://example.invalid", {
    fetchImpl: async () => ({
      ok: true,
      status: 200,
      json: async () => {
        throw new SyntaxError("bad JSON");
      },
    }),
  });
  assert.equal(result.state, "FAILED");
});

test("readiness remains blocked while release or parity gates are open", () => {
  const result = assessReadiness({
    summary: { endpoints_reachable: 4, endpoints_total: 4 },
    sections: [
      {
        id: "identity",
        raw_version: {
          release_state: "CANDIDATE",
          verify: { release_assets_status: "PENDING_RELEASE" },
        },
      },
      {
        id: "parity",
        build: { status: "behind", behind_by: 2 },
        hf_space: { status: "unknown" },
      },
    ],
  });
  assert.equal(result.state, "BLOCKED");
  assert.deepEqual(
    result.reasons.map((item) => item.id),
    [
      "RELEASE_NOT_VERIFIED",
      "RELEASE_ASSETS_NOT_VERIFIED",
      "DEPLOYED_SOURCE_DRIFT",
      "HF_SERVED_SOURCE_DRIFT",
    ],
  );
});

test("readiness verifies only when all gates pass", () => {
  const result = assessReadiness({
    summary: { endpoints_reachable: 4, endpoints_total: 4 },
    sections: [
      {
        id: "identity",
        raw_version: {
          release_state: "VERIFIED",
          verify: { release_assets_status: "VERIFIED" },
        },
      },
      {
        id: "parity",
        build: { status: "aligned" },
        hf_space: { status: "current" },
      },
    ],
  });
  assert.equal(result.state, "VERIFIED");
});

test("honesty contract requires locked doctrine and Conjecture 1", () => {
  assert.equal(
    assessHonesty({ doctrine_lock: { state: "LOCKED", lambda: "Conjecture 1" } })
      .state,
    "VERIFIED",
  );
  assert.equal(
    assessHonesty({ doctrine_lock: { state: "LOCKED", lambda: "THEOREM" } })
      .state,
    "BLOCKED",
  );
});
