import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { test } from "node:test";
import { canonicalReceipt, GENESIS } from "./crypto.ts";
import { evaluateImmune } from "./immune.ts";
import { geometricMean, lambdaVerdict, TRUST_CEILING } from "./lambda.ts";
import { FRONTIERS, GATES } from "./frontier.ts";
import { LOCKED_FORMULAS } from "./estate.ts";

test("geometric mean zero-pins", () => {
  assert.equal(geometricMean([0.9, 0]), 0);
  assert.equal(geometricMean([]), 0);
});

test("geometric mean never exceeds ceiling", () => {
  const v = geometricMean([0.99, 0.99, 0.99]);
  assert.ok(v <= TRUST_CEILING);
});

test("lambda floor deny", () => {
  assert.equal(lambdaVerdict(0), "DENY");
  assert.equal(lambdaVerdict(0.89), "DENY");
  assert.equal(lambdaVerdict(0.93), "ADMIT");
  assert.equal(lambdaVerdict(0.97), "HOLD");
});

test("immune denies threat signatures and zero consent", () => {
  assert.equal(evaluateImmune('{"action":{"cmd":"rm -rf /"}}').verdict, "deny");
  assert.equal(evaluateImmune('{"query":"DROP TABLE users; --"}').verdict, "deny");
  assert.equal(evaluateImmune('{"axes":{"consent":0}}').verdict, "deny");
  assert.equal(evaluateImmune('{"action":{"cmd":"echo hello"}}').verdict, "allow");
});

test("canonical receipt is stable", () => {
  const body = {
    seq: 1,
    prevDigest: GENESIS,
    verdict: "ADMIT",
    hard: false,
    action: "OBSERVE",
    intent: "test",
    reason: "unit",
    trust: 0.93,
    at: "2026-09-11T00:00:00.000Z",
  };
  const a = canonicalReceipt(body);
  const b = canonicalReceipt(body);
  assert.equal(a, b);
  const digest = createHash("sha256").update(a).digest("hex");
  assert.equal(digest.length, 64);
});

test("locked-8 stays eight and gates stay six", () => {
  assert.equal(LOCKED_FORMULAS.length, 8);
  assert.equal(GATES.length, 6);
  assert.ok(FRONTIERS.some((f) => f.id === "N-LAMBDA" && f.band === "CONJECTURE"));
  assert.ok(FRONTIERS.some((f) => f.band === "OUT-OF-SCOPE"));
});
