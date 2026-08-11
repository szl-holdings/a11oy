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

test("timeout cannot exceed the public eight-second ceiling", async () => {
  await assert.rejects(
    observeJson("https://example.invalid", { timeoutMs: 8_001 }),
    /no greater than 8000/,
  );
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
        id: "deployment",
        endpoints: Array.from({ length: 4 }, () => ({
          liveness: { reachable: true, http_status: 200, mode: "live" },
        })),
      },
      {
        id: "identity",
        healthz_mode: "live",
        version_mode: "live",
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
  const sha = "a".repeat(40);
  const result = assessReadiness({
    summary: { endpoints_reachable: 4, endpoints_total: 4 },
    sections: [
      {
        id: "deployment",
        endpoints: Array.from({ length: 4 }, () => ({
          liveness: { reachable: true, http_status: 200, mode: "live" },
        })),
      },
      {
        id: "identity",
        healthz_mode: "live",
        version_mode: "live",
        raw_version: {
          release_state: "VERIFIED",
          verify: { release_assets_status: "VERIFIED" },
        },
      },
      {
        id: "parity",
        build: {
          status: "current",
          deployed_git_sha: sha,
          repo_head_sha: sha,
          deployed_mode: "live",
          repo_mode: "live",
        },
        hf_space: {
          status: "match",
          deployed_hf_space_sha: sha,
          live_hf_space_sha: sha,
          mode: "live",
        },
      },
    ],
  });
  assert.equal(result.state, "VERIFIED");
});

test("readiness accepts the live producer's exact HF match state", () => {
  const sha = "b".repeat(40);
  const result = assessReadiness({
    summary: { endpoints_reachable: 4, endpoints_total: 4 },
    sections: [
      {
        id: "deployment",
        endpoints: Array.from({ length: 4 }, () => ({
          liveness: { reachable: true, http_status: 204, mode: "live" },
        })),
      },
      {
        id: "identity",
        healthz_mode: "live",
        version_mode: "live",
        raw_version: {
          release_state: "VERIFIED",
          verify: { release_assets_status: "VERIFIED" },
        },
      },
      {
        id: "parity",
        build: {
          status: "current",
          deployed_git_sha: sha,
          repo_head_sha: sha,
          deployed_mode: "live",
          repo_mode: "live",
        },
        hf_space: {
          status: "match",
          deployed_hf_space_sha: sha,
          live_hf_space_sha: sha,
          mode: "live",
        },
      },
    ],
  });
  assert.equal(result.state, "VERIFIED");
});

test("readiness rejects cached, unhealthy, or unbound evidence", () => {
  const sha = "c".repeat(40);
  const payload = {
    summary: { endpoints_reachable: 1, endpoints_total: 1 },
    sections: [
      {
        id: "deployment",
        endpoints: [
          { liveness: { reachable: true, http_status: 503, mode: "live" } },
        ],
      },
      {
        id: "identity",
        healthz_mode: "cached",
        version_mode: "live",
        raw_version: {
          release_state: "VERIFIED",
          verify: { release_assets_status: "VERIFIED" },
        },
      },
      {
        id: "parity",
        build: {
          status: "current",
          deployed_git_sha: sha,
          repo_head_sha: "d".repeat(40),
          deployed_mode: "cached",
          repo_mode: "live",
        },
        hf_space: { status: "match", mode: "cached" },
      },
    ],
  };
  const result = assessReadiness(payload);
  assert.equal(result.state, "BLOCKED");
  assert.deepEqual(
    result.reasons.map((item) => item.id),
    [
      "ENDPOINT_PARITY",
      "IDENTITY_NOT_LIVE",
      "DEPLOYED_SOURCE_DRIFT",
      "HF_SERVED_SOURCE_DRIFT",
    ],
  );
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
