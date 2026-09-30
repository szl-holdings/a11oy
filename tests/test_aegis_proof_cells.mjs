// SPDX-License-Identifier: Apache-2.0
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  canonicalJSONString,
  evaluateCase,
  evaluateCaseWithReceipt,
} from "../console/3d/aegis-proof-cells/app.mjs";

const registry = JSON.parse(
  await readFile(new URL("../console/3d/aegis-proof-cells/registry.json", import.meta.url), "utf8"),
);

const baseline = {
  tenant_id: "tenant-a",
  passport_tenant_id: "tenant-a",
  alert_id: "alert-1",
  source: "SIEM",
  severity: "HIGH",
  mission: "phishing",
  requested_action: "investigate",
  evidence_count: 4,
  evidence_fresh: true,
  human_approved: false,
};

test("valid defensive investigation produces a bounded sandbox plan", () => {
  const result = evaluateCase(baseline, registry);
  assert.equal(result.decision.state, "SANDBOX_PLAN");
  assert.equal(result.decision.reason, "DEFENSIVE_PLAN_READY");
  assert.equal(result.decision.evidence_class, "MODELED");
  assert.equal(result.decision.production_authorization, false);
  assert.ok(result.decision.score > 0);
  assert.ok(result.decision.score <= 0.97);
  assert.equal(result.procedure_capsule, "phishing-investigation-v1");
  assert.ok(result.plan.length >= 6);
  assert.equal(result.authority.external_writes, "DISABLED");
  assert.deepEqual(result.authority.effectors, []);
});

test("cross-tenant scope is hard denied", () => {
  const result = evaluateCase(
    { ...baseline, passport_tenant_id: "tenant-b" },
    registry,
  );
  assert.equal(result.decision.state, "DENIED");
  assert.equal(result.decision.reason, "CROSS_TENANT_SCOPE");
  assert.equal(result.decision.score, 0);
});

test("offensive and destructive requests are hard denied", () => {
  for (const action of [
    "exploit the target",
    "exfiltrate evidence",
    "dump credential hashes",
    "deploy malware",
    "destructive cleanup",
  ]) {
    const result = evaluateCase({ ...baseline, requested_action: action }, registry);
    assert.equal(result.decision.state, "DENIED");
    assert.equal(result.decision.reason, "PROHIBITED_ACTION");
    assert.equal(result.decision.score, 0);
  }
});

test("stale evidence abstains and remediation requires approval", () => {
  const stale = evaluateCase(
    { ...baseline, evidence_fresh: false },
    registry,
  );
  assert.equal(stale.decision.state, "ABSTAINED");
  assert.equal(stale.decision.reason, "EVIDENCE_NOT_FRESH");

  const gated = evaluateCase(
    { ...baseline, requested_action: "purge-email", human_approved: false },
    registry,
  );
  assert.equal(gated.decision.state, "AWAITING_APPROVAL");
  assert.equal(gated.decision.reason, "HUMAN_APPROVAL_REQUIRED");

  const approved = evaluateCase(
    { ...baseline, requested_action: "purge-email", human_approved: true },
    registry,
  );
  assert.equal(approved.decision.state, "SANDBOX_PLAN");
  assert.equal(approved.decision.production_authorization, false);
});

test("identical input produces an identical unsigned deterministic receipt", async () => {
  const first = await evaluateCaseWithReceipt(baseline, registry);
  const second = await evaluateCaseWithReceipt(baseline, registry);
  assert.equal(first.proof_chain.sha256, second.proof_chain.sha256);
  assert.equal(first.proof_chain.sha256.length, 64);
  assert.equal(first.proof_chain.signature_status, "UNAVAILABLE");
  assert.equal(first.proof_chain.persisted, false);
  assert.equal(canonicalJSONString(first).includes("undefined"), false);
});
