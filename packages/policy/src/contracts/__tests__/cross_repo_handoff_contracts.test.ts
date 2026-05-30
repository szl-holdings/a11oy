import assert from "node:assert/strict";
import { verifyReceipt } from "../../../../receipt-substrate/src/index.ts";
import {
  createCrossRepoHandoffEnvelope,
  emitCrossRepoHandoffReceipt,
  getCrossRepoHandoff,
  getCrossRepoHandoffManifest,
} from "../cross_repo_handoff.ts";

const manifest = getCrossRepoHandoffManifest();
assert.equal(manifest.handoffs.length, 4);
assert.match(manifest.canonicalRule, /not complete until/i);
assert.ok(manifest.forbiddenClaims.includes("all green"));

const agi = getCrossRepoHandoff("XREPO-AGI-FORECAST-FG-PIPELINE");
assert.equal(agi.targetRepo, "szl-holdings/agi-forecast");
assert.equal(agi.accessState, "blocked-by-access");
assert.equal(agi.handoffState, "ready-for-owner-apply");
assert.throws(() => getCrossRepoHandoff("XREPO-MISSING"), /Unknown cross-repo handoff/);

const envelope = createCrossRepoHandoffEnvelope({
  handoffId: "XREPO-AGI-FORECAST-FG-PIPELINE",
  actorId: "did:key:z6MkHandoffOperator",
  sourceCommit: "9c8d5c7",
  outcome: "queued",
});
assert.equal(envelope.tool_name, "a11oy_cross_repo_handoff");
assert.equal((envelope.payload as Record<string, unknown>).patchSha256, agi.patchSha256);
assert.equal((envelope.payload as Record<string, unknown>).outcome, "queued");

const receipt = emitCrossRepoHandoffReceipt({
  handoffId: "XREPO-LUTAR-LEAN-SIMPLE-API-DRIFT",
  actorId: "did:key:z6MkHandoffOperator",
  sourceCommit: "9c8d5c7",
  outcome: "blocked",
});
assert.equal(receipt.event_type, "A11OY_OPERATION");
assert.equal(receipt.policy?.vertical, "cross-repo-handoff");
assert.equal(verifyReceipt(receipt).valid, true);

assert.throws(
  () => createCrossRepoHandoffEnvelope({
    handoffId: "XREPO-LUTAR-LEAN-SIMPLE-API-DRIFT",
    actorId: "did:key:z6MkHandoffOperator",
    outcome: "target-ci-passed",
  }),
  /requires upstreamPrUrl and upstreamCiUrl/,
);

const completedEvidenceReceipt = emitCrossRepoHandoffReceipt({
  handoffId: "XREPO-AGI-FORECAST-FG-PIPELINE",
  actorId: "did:key:z6MkHandoffOperator",
  sourceCommit: "9c8d5c7",
  outcome: "target-ci-passed",
  upstreamPrUrl: "https://github.com/szl-holdings/agi-forecast/pull/42",
  upstreamCiUrl: "https://github.com/szl-holdings/agi-forecast/actions/runs/example",
});
assert.equal(verifyReceipt(completedEvidenceReceipt).valid, true);

console.log("[cross-repo-handoff-contracts] OK handoff manifest receipts");
