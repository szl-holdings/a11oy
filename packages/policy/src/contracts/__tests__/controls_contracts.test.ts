import assert from "node:assert/strict";
import { verifyReceipt } from "../../../../receipt-substrate/src/index.ts";
import {
  createActionContractEnvelope,
  createControlEvidenceEnvelope,
  emitActionContractReceipt,
  emitControlEvidenceReceipt,
  getActionContractManifest,
  getControlEvidence,
  getControlsEvidenceMap,
} from "../controls.ts";

const controlsMap = getControlsEvidenceMap();
assert.equal(controlsMap.controls.length, 10);
assert.match(controlsMap.cleanRoomRule, /no external control catalog/i);

const claimGate = getControlEvidence("A11OY-CE-001");
assert.equal(claimGate.claimStatus, "verified-runtime");
assert.ok(claimGate.evidencePaths.includes("docs/PROVENANCE.md"));
assert.throws(() => getControlEvidence("A11OY-CE-999"), /Unknown A11oy control/);

const controlEnvelope = createControlEvidenceEnvelope({
  controlId: "A11OY-CE-001",
  actorId: "did:key:z6MkControlsOperator",
  sourceCommit: "35f6e5c",
  outcome: "pass",
  details: { validator: "ecosystem:os:audit" },
});
assert.equal(controlEnvelope.protocol, "a11oy");
assert.equal(controlEnvelope.tool_name, "a11oy_control_evidence");
assert.deepEqual(controlEnvelope.lambda_axes, [
  "measurabilityHonesty",
  "moralGrounding",
  "provenanceIntegrity",
]);
assert.equal((controlEnvelope.payload as Record<string, unknown>).controlId, "A11OY-CE-001");

const controlReceipt = emitControlEvidenceReceipt({
  controlId: "A11OY-CE-002",
  actorId: "did:key:z6MkControlsOperator",
  sourceCommit: "35f6e5c",
  outcome: "pass",
});
assert.equal(controlReceipt.event_type, "A11OY_OPERATION");
assert.equal(controlReceipt.policy?.vertical, "a11oy-controls");
assert.equal(verifyReceipt(controlReceipt).valid, true);

const actionContract = getActionContractManifest();
assert.equal(actionContract.schemaVersion, "a11oy.action-contract.v0.1");
assert.equal(actionContract.cleanRoom.copyingRule, "pattern-only");
assert.equal(actionContract.egressLimits.defaultDeny, true);
assert.ok(actionContract.egressLimits.deniedCapabilities.includes("private-repo-ingestion"));

const actionEnvelope = createActionContractEnvelope({
  actorId: "did:key:z6MkOperator",
  sourceCommit: "35f6e5c",
  payloadDigest: "sha256:demo",
  policyHash: "sha256:policy",
  outcome: "preflight-pass",
});
assert.equal(actionEnvelope.tool_name, "a11oy_action_contract_preflight");
assert.equal((actionEnvelope.payload as Record<string, unknown>).contractId, actionContract.contractId);
assert.equal((actionEnvelope.payload as Record<string, unknown>).outcome, "preflight-pass");

const actionReceipt = emitActionContractReceipt({
  actorId: "did:key:z6MkOperator",
  sourceCommit: "35f6e5c",
  payloadDigest: "sha256:demo",
  policyHash: "sha256:policy",
  outcome: "preflight-pass",
});
assert.equal(actionReceipt.event_type, "A11OY_OPERATION");
assert.equal(actionReceipt.policy?.vertical, "a11oy");
assert.equal(actionReceipt.policy?.regime, "doctrine-v6");
assert.equal(verifyReceipt(actionReceipt).valid, true);

console.log("[policy-contracts] OK controls/action-contract receipts");
