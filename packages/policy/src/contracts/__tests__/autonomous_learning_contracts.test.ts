import assert from "node:assert/strict";
import { verifyReceipt } from "../../../../receipt-substrate/src/index.ts";
import {
  createAutonomousLearningProposalEnvelope,
  emitAutonomousLearningEvaluationReceipt,
  emitAutonomousLearningProposalReceipt,
  emitHumanPromotionReceipt,
  verifyAutonomousLearningChain,
  type AutonomousLearningProposalInput,
} from "../autonomous_learning.ts";

const policy = {
  algorithm: "SHA3-256" as const,
  chaining: "hash_chain" as const,
  quorum: "2-of-3",
  nodes: ["node-primary", "node-backup", "node-witness"],
};

const proposalInput: AutonomousLearningProposalInput = {
  proposalId: "alp-001",
  runId: "alr-001",
  actorId: "agent:dreamer",
  proposalKind: "json-map",
  sourceCommit: "5fc5887",
  policyHash: "sha256:policy",
  lambdaAxes: ["moralGrounding", "measurabilityHonesty", "provenanceIntegrity"],
  toolVersions: { runtime: "tsx", policy: "0.1.0" },
  sourceIngress: [
    {
      sourceUri: "https://github.com/szl-holdings/a11oy",
      licenseClass: "user-owned",
      contentHash: "sha256:source",
    },
  ],
  intendedFiles: ["docs/example.json"],
  expectedBehavior: "Emit a staged proposal only.",
  riskClass: "medium",
  proposalPayloadDigest: "sha256:proposal",
  forbiddenClaimScan: {
    passed: true,
    scanner: "doctrine-v6",
    forbiddenMatches: [],
  },
  stagedAdvisory: "proposal-only",
  claimStatus: "staged",
};

const proposalEnvelope = createAutonomousLearningProposalEnvelope(proposalInput);
assert.equal(proposalEnvelope.protocol, "a11oy");
assert.equal(proposalEnvelope.tool_name, "autonomous_learning_proposal");
assert.equal((proposalEnvelope.payload as Record<string, unknown>).proposalId, "alp-001");

const proposalReceipt = emitAutonomousLearningProposalReceipt(proposalInput, {
  policy,
  quorumSignatures: ["node-primary", "node-backup"],
  timestamp: new Date("2026-05-30T00:00:00.000Z"),
});
assert.equal(proposalReceipt.event_type, "AUTONOMOUS_LEARNING_PROPOSAL");
assert.equal(verifyReceipt(proposalReceipt).valid, true);

assert.throws(
  () => emitAutonomousLearningProposalReceipt({
    ...proposalInput,
    forbiddenClaimScan: { passed: false, scanner: "doctrine-v6", forbiddenMatches: ["cracked Putnam"] },
  }),
  /forbidden claim scan/,
);

assert.throws(
  () => emitAutonomousLearningEvaluationReceipt({
    proposalId: "alp-001",
    runId: "alr-001",
    actorId: "agent:dreamer",
    proposalActorId: "agent:dreamer",
    proposalReceiptId: proposalReceipt.receipt_id,
    sourceCommit: "5fc5887",
    policyHash: "sha256:policy",
    harnessCommitSha: "5fc5887",
    replaySeeds: [1, 2, 3, 4, 5],
    frozenTime: "2026-05-30T00:00:00.000Z",
    inputRoots: ["sha256:input"],
    outputRoots: ["sha256:output"],
    deterministicPass: true,
    varianceBounds: { max: 0 },
    adversarialChecks: ["tamper", "replay"],
    failureReceipts: [],
    outcome: "pass",
  }),
  /distinct/,
);

assert.throws(
  () => emitAutonomousLearningEvaluationReceipt({
    proposalId: "alp-001",
    runId: "alr-001",
    actorId: "agent:evaluator",
    proposalActorId: "agent:dreamer",
    proposalReceiptId: proposalReceipt.receipt_id,
    sourceCommit: "5fc5887",
    policyHash: "sha256:policy",
    harnessCommitSha: "5fc5887",
    replaySeeds: [1, 2],
    frozenTime: "2026-05-30T00:00:00.000Z",
    inputRoots: ["sha256:input"],
    outputRoots: ["sha256:output"],
    deterministicPass: true,
    varianceBounds: { max: 0 },
    adversarialChecks: ["tamper", "replay"],
    failureReceipts: [],
    outcome: "pass",
  }),
  /five replay seeds/,
);

const evaluationReceipt = emitAutonomousLearningEvaluationReceipt({
  proposalId: "alp-001",
  runId: "alr-001",
  actorId: "agent:evaluator",
  proposalActorId: "agent:dreamer",
  proposalReceiptId: proposalReceipt.receipt_id,
  sourceCommit: "5fc5887",
  policyHash: "sha256:policy",
  harnessCommitSha: "5fc5887",
  replaySeeds: [1, 2, 3, 4, 5],
  frozenTime: "2026-05-30T00:00:00.000Z",
  inputRoots: ["sha256:input"],
  outputRoots: ["sha256:output"],
  deterministicPass: true,
  varianceBounds: { max: 0 },
  adversarialChecks: ["tamper", "replay", "duplicate", "timestamp", "quorum"],
  failureReceipts: [],
  outcome: "pass",
}, {
  previousReceipt: proposalReceipt,
  policy,
  quorumSignatures: ["node-primary", "node-witness"],
  timestamp: new Date("2026-05-30T00:00:01.000Z"),
});
assert.equal(evaluationReceipt.event_type, "AUTONOMOUS_LEARNING_EVALUATION");
assert.equal(verifyReceipt(evaluationReceipt).valid, true);

assert.throws(
  () => emitHumanPromotionReceipt({
    proposalId: "alp-001",
    runId: "alr-001",
    actorId: "agent:dreamer",
    proposalActorId: "agent:dreamer",
    evaluationActorId: "agent:evaluator",
    proposalReceiptId: proposalReceipt.receipt_id,
    evaluationReceiptId: evaluationReceipt.receipt_id,
    humanReviewerId: "agent:dreamer",
    approvedBy: "agent:dreamer",
    approvalTime: "2026-05-30T00:00:02.000Z",
    approvalBasis: "bad self approval",
    sourceCommit: "5fc5887",
    policyHash: "sha256:policy",
    ciRuns: ["https://github.com/szl-holdings/a11oy/actions/runs/demo"],
    manifestSha256: "sha256:manifest",
    bundleSha256: "sha256:bundle",
    rollbackRef: "git revert HEAD",
    publishedSurfaces: ["github"],
  }),
  /human reviewer must be distinct/,
);

const promotionReceipt = emitHumanPromotionReceipt({
  proposalId: "alp-001",
  runId: "alr-001",
  actorId: "human:reviewer",
  proposalActorId: "agent:dreamer",
  evaluationActorId: "agent:evaluator",
  proposalReceiptId: proposalReceipt.receipt_id,
  evaluationReceiptId: evaluationReceipt.receipt_id,
  humanReviewerId: "human:reviewer",
  approvedBy: "human:reviewer",
  approvalTime: "2026-05-30T00:00:02.000Z",
  approvalBasis: "CI passed and rollback is defined.",
  sourceCommit: "5fc5887",
  policyHash: "sha256:policy",
  ciRuns: ["https://github.com/szl-holdings/a11oy/actions/runs/demo"],
  manifestSha256: "sha256:manifest",
  bundleSha256: "sha256:bundle",
  rollbackRef: "git revert HEAD",
  publishedSurfaces: ["github"],
}, {
  previousReceipt: evaluationReceipt,
  policy,
  quorumSignatures: ["node-backup", "node-witness"],
  timestamp: new Date("2026-05-30T00:00:02.000Z"),
});
assert.equal(promotionReceipt.event_type, "HUMAN_PROMOTION");
assert.equal(verifyReceipt(promotionReceipt).valid, true);

const chainResult = verifyAutonomousLearningChain([proposalReceipt, evaluationReceipt, promotionReceipt]);
assert.equal(chainResult.valid, true);
assert.equal(chainResult.proposalCount, 1);
assert.equal(chainResult.evaluationCount, 1);
assert.equal(chainResult.promotionCount, 1);

const driftedEvaluation = emitAutonomousLearningEvaluationReceipt({
  proposalId: "alp-001",
  runId: "alr-001",
  actorId: "agent:evaluator",
  proposalActorId: "agent:dreamer",
  proposalReceiptId: proposalReceipt.receipt_id,
  sourceCommit: "different",
  policyHash: "sha256:policy",
  harnessCommitSha: "5fc5887",
  replaySeeds: [1, 2, 3, 4, 5],
  frozenTime: "2026-05-30T00:00:00.000Z",
  inputRoots: ["sha256:input"],
  outputRoots: ["sha256:output"],
  deterministicPass: true,
  varianceBounds: { max: 0 },
  adversarialChecks: ["tamper", "replay"],
  failureReceipts: [],
  outcome: "pass",
}, {
  previousReceipt: proposalReceipt,
  policy,
  quorumSignatures: ["node-primary", "node-witness"],
  timestamp: new Date("2026-05-30T00:00:03.000Z"),
});
const driftResult = verifyAutonomousLearningChain([proposalReceipt, driftedEvaluation]);
assert.equal(driftResult.valid, false);
assert.match(driftResult.errors.join("\n"), /source commit drift/);

console.log("[autonomous-learning-contracts] OK proposal/evaluation/promotion receipts");
