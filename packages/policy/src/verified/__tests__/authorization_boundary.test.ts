/*
 * SPDX-License-Identifier: Apache-2.0
 * (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
 */

import assert from "node:assert/strict";
import { generateKeyPairSync } from "node:crypto";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import Ajv2020 from "ajv/dist/2020.js";
import addFormats from "ajv-formats";
import {
  canExecute,
  evaluateAction,
  issueAuthorizationReceipt,
  issueHumanApproval,
  sha256Digest,
  validateActionRequest,
  verifyAuthorizationReceipt,
  type ActionRequest,
  type ActionType,
  type AuthorizationRule,
  type Environment,
  type PolicyState,
} from "../authorization_boundary.js";

const NOW = "2026-07-26T05:00:00.000Z";
const LATER = "2026-07-26T05:10:00.000Z";
const DIGEST = `sha256:${"a".repeat(64)}`;
const TARGET = `oci://ghcr.io/szl-holdings/a11oy@${DIGEST}`;
const ROLLBACK_DIGEST = `sha256:${"b".repeat(64)}`;
const FORMAL_DIGEST = `sha256:${"f".repeat(64)}`;
const SOURCE_COMMIT = "c".repeat(40);
const POLICY_VERSION = "d".repeat(40);
const TRACE_ID = "1234567890abcdef1234567890abcdef";
const { privateKey, publicKey } = generateKeyPairSync("ed25519");
const {
  privateKey: approvalPrivateKey,
  publicKey: approvalPublicKey,
} = generateKeyPairSync("ed25519");
const APPROVAL_KEY_ID = "human-approval-key";
const PROVENANCE_RECEIPT_DIGEST = `sha256:${"6".repeat(64)}`;
const SECURITY_RECEIPT_DIGEST = `sha256:${"2".repeat(64)}`;
const TEST_RECEIPT_DIGEST = `sha256:${"1".repeat(64)}`;
const ROLLBACK_RECEIPT_DIGEST = `sha256:${"7".repeat(64)}`;

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

function request(
  overrides: Partial<ActionRequest> = {},
): ActionRequest {
  return {
    request_id: "3d594650-3436-4bda-9fe4-8b53a2da1c00",
    trace_id: TRACE_ID,
    principal: "agent:build-1",
    action_type: "artifact.build",
    target: TARGET,
    source_commit: SOURCE_COMMIT,
    artifact_digest: DIGEST,
    requested_transition: {
      from: "development",
      to: "staging",
    },
    preconditions: ["clean-checkout"],
    test_receipts: [TEST_RECEIPT_DIGEST],
    provenance_receipt: {
      receipt_digest: PROVENANCE_RECEIPT_DIGEST,
      subject_digest: DIGEST,
      source_commit: SOURCE_COMMIT,
      accepted: true,
      verifier: "independent-verifier",
      verified_at: NOW,
      source_repository: "github.com/szl-holdings/a11oy",
    },
    security_receipts: [
      {
        control: "secret-scan",
        passed: true,
        digest: SECURITY_RECEIPT_DIGEST,
        subject_digest: DIGEST,
      },
    ],
    blast_radius: {
      services: ["staging/a11oy"],
      users: "internal-testers",
      data: "synthetic-only",
    },
    rollback: {},
    human_approvals: [],
    expires_at: LATER,
    ...overrides,
  };
}

function signedApproval(
  actionType: ActionType = "deploy.production",
  environment: Environment = "production",
) {
  return issueHumanApproval(
    {
      approver: "human:founder",
      action_type: actionType,
      target_digest: DIGEST,
      environment,
      approved_at: NOW,
      expires_at: LATER,
      key_id: APPROVAL_KEY_ID,
    },
    approvalPrivateKey,
  );
}

function productionRequest(): ActionRequest {
  return request({
    action_type: "deploy.production",
    requested_transition: {
      from: "staging",
      to: "production",
    },
    rollback: {
      receipt_digest: ROLLBACK_RECEIPT_DIGEST,
      target_digest: ROLLBACK_DIGEST,
      verified: true,
      tested_at: NOW,
    },
    human_approvals: [signedApproval()],
  });
}

function state(
  rules?: readonly AuthorizationRule[],
  currentEnvironment: Environment = "development",
): PolicyState {
  return {
    now: NOW,
    policyVersion: POLICY_VERSION,
    formalArtifactDigest: FORMAL_DIGEST,
    currentTargetEnvironments: {
      [TARGET]: currentEnvironment,
    },
    rules:
      rules ??
      [
        {
          id: "rule-staging-build",
          principals: ["agent:build-1"],
          actions: ["artifact.build"],
          environments: ["staging"],
          artifactDigests: [DIGEST],
        },
        {
          id: "rule-production-deploy",
          principals: ["agent:build-1"],
          actions: ["deploy.production"],
          environments: ["production"],
          artifactDigests: [DIGEST],
        },
      ],
    revokedPrincipals: [],
    revokedPolicyVersions: [],
    approvalPublicKeys: {
      [APPROVAL_KEY_ID]: approvalPublicKey,
    },
    approvalKeyOwners: {
      [APPROVAL_KEY_ID]: "human:founder",
    },
    authorizationReceiptPublicKeys: {
      "test-ed25519-key": publicKey,
    },
    revokedAuthorizationReceiptKeyIds: [],
    trustedProvenanceVerifiers: ["independent-verifier"],
    acceptedProvenanceReceipts: [
      {
        receipt_digest: PROVENANCE_RECEIPT_DIGEST,
        subject_digest: DIGEST,
        source_commit: SOURCE_COMMIT,
        verifier: "independent-verifier",
        verified_at: NOW,
        source_repository: "github.com/szl-holdings/a11oy",
      },
    ],
    acceptedSecurityReceipts: [
      {
        control: "secret-scan",
        digest: SECURITY_RECEIPT_DIGEST,
        subject_digest: DIGEST,
      },
    ],
    requiredSecurityControls: ["secret-scan"],
    acceptedTestReceipts: [
      {
        receipt_digest: TEST_RECEIPT_DIGEST,
        subject_digest: DIGEST,
      },
    ],
    acceptedRollbackReceipts: [
      {
        receipt_digest: ROLLBACK_RECEIPT_DIGEST,
        source_digest: DIGEST,
        target_digest: ROLLBACK_DIGEST,
        tested_at: NOW,
      },
    ],
  };
}

function productionState(rules?: readonly AuthorizationRule[]): PolicyState {
  return state(rules, "staging");
}

function schema(name: string): unknown {
  const here = path.dirname(fileURLToPath(import.meta.url));
  const schemaPath = path.resolve(here, "../../../../../schemas", name);
  return JSON.parse(readFileSync(schemaPath, "utf-8")) as unknown;
}

function contractSuite(): number {
  let assertions = 0;
  const ajv = new Ajv2020({ allErrors: true, strict: true });
  addFormats(ajv);
  const validateRequest = ajv.compile(schema("action-request.schema.json"));
  const validateReceipt = ajv.compile(
    schema("authorization-receipt.schema.json"),
  );
  const validateIdentity = ajv.compile(
    schema("deployment-identity.schema.json"),
  );

  const allowed = request();
  assert.equal(validateRequest(allowed), true, JSON.stringify(validateRequest.errors));
  assertions++;
  assert.deepEqual(validateActionRequest(allowed, NOW), []);
  assertions++;
  assert.equal(evaluateAction(allowed, state()).decision, "ALLOW");
  assertions++;
  assert.equal(
    validateRequest({
      ...allowed,
      target: "oci://ghcr.io/szl-holdings/a11oy:latest",
    }),
    false,
  );
  assertions++;
  assert.equal(
    validateRequest({
      ...allowed,
      action_type: "deploy.production",
      requested_transition: {
        from: "development",
        to: "production",
      },
    }),
    false,
  );
  assertions++;

  const receipt = issueAuthorizationReceipt(
    allowed,
    state(),
    privateKey,
    "test-ed25519-key",
  );
  assert.equal(validateReceipt(receipt), true, JSON.stringify(validateReceipt.errors));
  assertions++;
  assert.equal(canExecute(receipt, allowed, state()), true);
  assertions++;
  assert.deepEqual(
    verifyAuthorizationReceipt(receipt, allowed, state()),
    { valid: true, reasons: [] },
  );
  assertions++;
  assert.equal(receipt.request_digest, sha256Digest(allowed));
  assertions++;
  assert.equal(
    validateIdentity({
      service: "inference-gateway",
      source_commit: SOURCE_COMMIT,
      workflow_ref: `reusable-build.yml@${SOURCE_COMMIT}`,
      image_digest: DIGEST,
      attestation_digest: `sha256:${"3".repeat(64)}`,
      sbom_digest: `sha256:${"4".repeat(64)}`,
      policy_version: POLICY_VERSION,
      formal_artifact_digest: FORMAL_DIGEST,
      model_revision: "5".repeat(40),
      runtime: "vllm",
      runtime_version: "pinned-test-version",
      hardware: "identical-test-profile",
      deployed_at: NOW,
      trace_id: TRACE_ID,
    }),
    true,
    JSON.stringify(validateIdentity.errors),
  );
  assertions++;
  assert.throws(
    () =>
      issueAuthorizationReceipt(
        allowed,
        state(),
        privateKey,
        "test-ed25519-key",
        901,
      ),
    /TTL/,
  );
  assertions++;
  return assertions;
}

function negativeSuite(): number {
  let assertions = 0;
  const withUnknown = { ...request(), injected_allow: true };
  assert.match(
    validateActionRequest(withUnknown, NOW).join(","),
    /unknown-field:injected_allow/,
  );
  assertions++;
  assert.equal(evaluateAction(withUnknown, state()).decision, "REJECT");
  assertions++;

  const malformedPrincipal = request({ principal: "../admin" });
  assert.equal(evaluateAction(malformedPrincipal, state()).decision, "REJECT");
  assertions++;

  const mutableTarget = request({
    target: "oci://ghcr.io/szl-holdings/a11oy:latest",
  });
  assert.equal(evaluateAction(mutableTarget, state()).decision, "REJECT");
  assertions++;

  const unsupported = {
    ...request(),
    action_type: "deploy.anything",
  };
  assert.equal(evaluateAction(unsupported, state()).decision, "REJECT");
  assertions++;

  const expired = request({ expires_at: "2026-07-26T04:59:59.000Z" });
  assert.equal(evaluateAction(expired, state()).decision, "REJECT");
  assertions++;

  const dateOnlyExpiry = request({ expires_at: "2026-07-27" });
  assert.equal(evaluateAction(dateOnlyExpiry, state()).decision, "REJECT");
  assertions++;

  assert.equal(
    evaluateAction({ ...request(), noncanonical: 1n }, state()).decision,
    "REJECT",
  );
  assertions++;

  assert.equal(
    evaluateAction(
      {
        ...request(),
        preconditions: Array.from({ length: 257 }, () => "bounded"),
      },
      state(),
    ).decision,
    "REJECT",
  );
  assertions++;

  const cyclic = { ...request() } as Record<string, unknown>;
  cyclic.self = cyclic;
  assert.equal(evaluateAction(cyclic, state()).decision, "REJECT");
  assertions++;

  const oversizedKey = {
    ...request(),
    ["x".repeat(70_000)]: true,
  };
  const oversizedKeyDecision = evaluateAction(oversizedKey, state());
  assert.equal(oversizedKeyDecision.decision, "REJECT");
  assert.match(
    oversizedKeyDecision.reasonCodes.join(","),
    /SCHEMA_REQUEST_NON_CANONICAL/,
  );
  assert.ok(oversizedKeyDecision.reasonCodes.join(",").length < 512);
  assertions += 3;

  const denied = request();
  assert.equal(evaluateAction(denied, state([])).decision, "REJECT");
  assertions++;
  assert.throws(
    () =>
      issueAuthorizationReceipt(
        denied,
        state([]),
        privateKey,
        "test-ed25519-key",
      ),
    /authorization rejected/,
  );
  assertions++;

  const failedSecurity = request({
    security_receipts: [
      {
        control: "secret-scan",
        passed: false,
        digest: SECURITY_RECEIPT_DIGEST,
        subject_digest: DIGEST,
      },
    ],
  });
  assert.match(
    evaluateAction(failedSecurity, state()).reasonCodes.join(","),
    /SECURITY_RECEIPT_FAILED/,
  );
  assertions++;

  const production = productionRequest();
  const noApproval = clone(production);
  (noApproval as { human_approvals: unknown[] }).human_approvals = [];
  assert.match(
    evaluateAction(noApproval, productionState()).reasonCodes.join(","),
    /VALID_HUMAN_APPROVAL_REQUIRED/,
  );
  assertions++;

  const forgedApproval = clone(production);
  const forgedSignature = Buffer.from(
    forgedApproval.human_approvals[0].signature,
    "base64url",
  );
  forgedSignature[0] ^= 0x01;
  (
    forgedApproval as {
      human_approvals: { signature: string }[];
    }
  ).human_approvals[0].signature = forgedSignature.toString("base64url");
  assert.match(
    evaluateAction(forgedApproval, productionState()).reasonCodes.join(","),
    /VALID_HUMAN_APPROVAL_REQUIRED/,
  );
  assertions++;

  const wrongApprovalIdentity = clone(production);
  (
    wrongApprovalIdentity as {
      human_approvals: ReturnType<typeof signedApproval>[];
    }
  ).human_approvals = [
    issueHumanApproval(
      {
        approver: "human:other",
        action_type: "deploy.production",
        target_digest: DIGEST,
        environment: "production",
        approved_at: NOW,
        expires_at: LATER,
        key_id: APPROVAL_KEY_ID,
      },
      approvalPrivateKey,
    ),
  ];
  assert.match(
    evaluateAction(wrongApprovalIdentity, productionState()).reasonCodes.join(","),
    /VALID_HUMAN_APPROVAL_REQUIRED/,
  );
  assertions++;

  const noProvenance = clone(production);
  (
    noProvenance as {
      provenance_receipt: { accepted: boolean };
    }
  ).provenance_receipt.accepted = false;
  assert.match(
    evaluateAction(noProvenance, productionState()).reasonCodes.join(","),
    /ACCEPTED_PROVENANCE_REQUIRED/,
  );
  assertions++;

  const untrustedProvenance = clone(production);
  untrustedProvenance.provenance_receipt.receipt_digest =
    `sha256:${"8".repeat(64)}`;
  assert.match(
    evaluateAction(untrustedProvenance, productionState()).reasonCodes.join(","),
    /ACCEPTED_PROVENANCE_REQUIRED/,
  );
  assertions++;

  const noRollback = clone(production);
  (noRollback as { rollback: Record<string, never> }).rollback = {};
  assert.match(
    evaluateAction(noRollback, productionState()).reasonCodes.join(","),
    /VERIFIED_ROLLBACK_REQUIRED/,
  );
  assertions++;

  const untrustedSecurity = request({
    security_receipts: [
      {
        control: "secret-scan",
        passed: true,
        digest: `sha256:${"9".repeat(64)}`,
        subject_digest: DIGEST,
      },
    ],
  });
  assert.match(
    evaluateAction(untrustedSecurity, state()).reasonCodes.join(","),
    /SECURITY_RECEIPT_FAILED_OR_UNTRUSTED/,
  );
  assertions++;

  const reboundSecurity = request({
    security_receipts: [
      {
        control: "secret-scan",
        passed: true,
        digest: SECURITY_RECEIPT_DIGEST,
        subject_digest: `sha256:${"9".repeat(64)}`,
      },
    ],
  });
  assert.match(
    evaluateAction(reboundSecurity, state()).reasonCodes.join(","),
    /SECURITY_RECEIPT_FAILED_OR_UNTRUSTED/,
  );
  assertions++;

  const targetMismatch = productionRequest();
  (
    targetMismatch as {
      target: string;
    }
  ).target = `oci://ghcr.io/attacker/unrelated@sha256:${"9".repeat(64)}`;
  assert.match(
    evaluateAction(targetMismatch, productionState()).reasonCodes.join(","),
    /TARGET-BINDING-MISMATCH/,
  );
  assertions++;

  const sourceMismatch = productionRequest();
  (
    sourceMismatch as {
      source_commit: string;
    }
  ).source_commit = "e".repeat(40);
  assert.match(
    evaluateAction(sourceMismatch, productionState()).reasonCodes.join(","),
    /ACCEPTED_PROVENANCE_REQUIRED/,
  );
  assertions++;

  const buildWithoutAcceptedProvenance = request();
  (
    buildWithoutAcceptedProvenance as {
      provenance_receipt: ActionRequest["provenance_receipt"];
    }
  ).provenance_receipt = {
    ...buildWithoutAcceptedProvenance.provenance_receipt,
    accepted: false,
    verifier: "attacker-verifier",
    receipt_digest: `sha256:${"8".repeat(64)}`,
    source_commit: "e".repeat(40),
  };
  assert.match(
    evaluateAction(buildWithoutAcceptedProvenance, state()).reasonCodes.join(","),
    /ACCEPTED_PROVENANCE_REQUIRED/,
  );
  assertions++;

  assert.match(
    evaluateAction(productionRequest(), state()).reasonCodes.join(","),
    /CURRENT_ENVIRONMENT_MISMATCH/,
  );
  assertions++;

  const inheritedApprovalState: PolicyState = {
    ...productionState(),
    approvalPublicKeys: Object.create({
      [APPROVAL_KEY_ID]: approvalPublicKey,
    }) as PolicyState["approvalPublicKeys"],
    approvalKeyOwners: Object.create({
      [APPROVAL_KEY_ID]: "human:founder",
    }) as PolicyState["approvalKeyOwners"],
  };
  assert.match(
    evaluateAction(productionRequest(), inheritedApprovalState).reasonCodes.join(","),
    /POLICY_STATE:INVALID-APPROVAL-(?:PUBLIC-KEYS|KEY-OWNERS)/,
  );
  assertions++;

  const inheritedReceiptState: PolicyState = {
    ...state(),
    authorizationReceiptPublicKeys: Object.create({
      "test-ed25519-key": publicKey,
    }) as PolicyState["authorizationReceiptPublicKeys"],
  };
  assert.throws(
    () =>
      issueAuthorizationReceipt(
        request(),
        inheritedReceiptState,
        privateKey,
        "test-ed25519-key",
      ),
    /authorization rejected/,
  );
  assertions++;

  const malformedDependentRegistryState: PolicyState = {
    ...state(),
    approvalPublicKeys:
      undefined as unknown as PolicyState["approvalPublicKeys"],
    approvalKeyOwners: {
      "evil-human-key": "human:reviewer",
    },
  };
  const malformedDependentRegistryDecision = evaluateAction(
    request(),
    malformedDependentRegistryState,
  );
  assert.equal(malformedDependentRegistryDecision.decision, "REJECT");
  assert.match(
    malformedDependentRegistryDecision.reasonCodes.join(","),
    /POLICY_STATE:INVALID-APPROVAL-PUBLIC-KEYS/,
  );
  assertions += 2;

  const malformedProvenanceDependencyState: PolicyState = {
    ...state(),
    trustedProvenanceVerifiers:
      undefined as unknown as PolicyState["trustedProvenanceVerifiers"],
  };
  const malformedProvenanceDependencyDecision = evaluateAction(
    request(),
    malformedProvenanceDependencyState,
  );
  assert.equal(malformedProvenanceDependencyDecision.decision, "REJECT");
  assert.match(
    malformedProvenanceDependencyDecision.reasonCodes.join(","),
    /POLICY_STATE:INVALID-TRUSTED-PROVENANCE-VERIFIERS/,
  );
  assertions += 2;

  const malformedRuleState: PolicyState = {
    ...state(),
    rules: [null] as unknown as PolicyState["rules"],
  };
  assert.match(
    evaluateAction(request(), malformedRuleState).reasonCodes.join(","),
    /POLICY_STATE:RULES\[0\]:NOT-OBJECT/,
  );
  assertions++;

  assert.match(
    evaluateAction(
      request(),
      null as unknown as PolicyState,
    ).reasonCodes.join(","),
    /POLICY_STATE:NOT-OBJECT/,
  );
  assertions++;

  const illegalTransition = productionRequest();
  (
    illegalTransition as {
      requested_transition: {
        from: Environment;
        to: Environment;
      };
    }
  ).requested_transition = {
    from: "development",
    to: "production",
  };
  assert.match(
    evaluateAction(illegalTransition, state()).reasonCodes.join(","),
    /TRANSITION:ILLEGAL-FOR-ACTION/,
  );
  assertions++;

  const invalidPolicy = {
    ...state(),
    acceptedTestReceipts: [
      {
        receipt_digest: "not-a-digest",
        subject_digest: DIGEST,
      },
    ],
  };
  assert.match(
    evaluateAction(request(), invalidPolicy).reasonCodes.join(","),
    /POLICY_STATE:INVALID-ACCEPTED-TEST-RECEIPTS/,
  );
  assertions++;
  return assertions;
}

function mutationSuite(): number {
  let assertions = 0;
  const allowed = request();
  const receipt = issueAuthorizationReceipt(
    allowed,
    state(),
    privateKey,
    "test-ed25519-key",
  );

  const targetMutation = {
    ...receipt,
    target_digest: `sha256:${"9".repeat(64)}`,
  };
  assert.equal(
    verifyAuthorizationReceipt(targetMutation, allowed, state()).valid,
    false,
  );
  assertions++;

  const mutatedSignatureBytes = Buffer.from(receipt.signature, "base64url");
  mutatedSignatureBytes[0] ^= 0x01;
  const signatureMutation = {
    ...receipt,
    signature: mutatedSignatureBytes.toString("base64url"),
  };
  assert.equal(
    verifyAuthorizationReceipt(signatureMutation, allowed, state())
      .valid,
    false,
  );
  assertions++;

  const unknownKey = {
    ...receipt,
    key_id: "unknown-receipt-key",
  };
  assert.match(
    verifyAuthorizationReceipt(unknownKey, allowed, state()).reasons.join(","),
    /RECEIPT_KEY_UNTRUSTED/,
  );
  assertions++;

  assert.throws(
    () =>
      issueAuthorizationReceipt(
        allowed,
        state(),
        approvalPrivateKey,
        "test-ed25519-key",
      ),
    /does not match key_id/,
  );
  assertions++;

  const revokedReceiptKey = {
    ...state(),
    revokedAuthorizationReceiptKeyIds: ["test-ed25519-key"],
  };
  assert.match(
    verifyAuthorizationReceipt(receipt, allowed, revokedReceiptKey).reasons.join(
      ",",
    ),
    /RECEIPT_KEY_REVOKED/,
  );
  assertions++;

  const principalMutation = request({ principal: "agent:other" });
  assert.equal(
    verifyAuthorizationReceipt(receipt, principalMutation, state())
      .valid,
    false,
  );
  assertions++;

  const production = productionRequest();
  const productionReceipt = issueAuthorizationReceipt(
    production,
    productionState(),
    privateKey,
    "test-ed25519-key",
  );
  const stagingReplay = request({
    action_type: "deploy.production",
    human_approvals: production.human_approvals,
  });
  assert.equal(
    verifyAuthorizationReceipt(
      productionReceipt,
      stagingReplay,
      productionState(),
    ).valid,
    false,
  );
  assertions++;

  const revoked = {
    ...state(),
    revokedPrincipals: [allowed.principal],
  };
  assert.equal(
    verifyAuthorizationReceipt(receipt, allowed, revoked).valid,
    false,
  );
  assertions++;

  const changedPolicy = {
    ...state(),
    policyVersion: "e".repeat(40),
  };
  assert.equal(
    verifyAuthorizationReceipt(receipt, allowed, changedPolicy).valid,
    false,
  );
  assertions++;

  const artifactRuleMutation = state([
    {
      id: "mutated-artifact-rule",
      principals: ["agent:build-1"],
      actions: ["artifact.build"],
      environments: ["staging"],
      artifactDigests: [`sha256:${"8".repeat(64)}`],
    },
  ]);
  assert.equal(evaluateAction(allowed, artifactRuleMutation).decision, "REJECT");
  assertions++;
  return assertions;
}

function referenceDecision(
  candidate: ActionRequest,
  candidateState: PolicyState,
): "ALLOW" | "REJECT" {
  if (validateActionRequest(candidate, candidateState.now).length) {
    return "REJECT";
  }
  if (
    candidateState.revokedPrincipals.includes(candidate.principal) ||
    candidateState.revokedPolicyVersions.includes(candidateState.policyVersion)
  ) {
    return "REJECT";
  }
  if (
    candidateState.currentTargetEnvironments[candidate.target] !==
    candidate.requested_transition.from
  ) {
    return "REJECT";
  }
  const ruleExists = candidateState.rules.some(
    (rule) =>
      rule.principals.some((principal) => principal === candidate.principal) &&
      rule.actions.some((action) => action === candidate.action_type) &&
      rule.environments.some(
        (environment) => environment === candidate.requested_transition.to,
      ) &&
      rule.artifactDigests.some(
        (digest) => digest === candidate.artifact_digest,
      ),
  );
  if (!ruleExists) {
    return "REJECT";
  }
  const highRisk = new Set<ActionType>([
    "deploy.production",
    "secret.rotate",
    "identity.change",
    "repository.ruleset.change",
    "model.promote",
    "benchmark.publish",
    "claim.upgrade",
  ]);
  if (
    highRisk.has(candidate.action_type) &&
    !candidate.human_approvals.some(
      (approval) =>
        approval.approver !== candidate.principal &&
        approval.action_type === candidate.action_type &&
        approval.target_digest === candidate.artifact_digest &&
        approval.environment === candidate.requested_transition.to &&
        Date.parse(approval.approved_at) <= Date.parse(candidateState.now) &&
        Date.parse(approval.expires_at) > Date.parse(candidateState.now),
    )
  ) {
    return "REJECT";
  }
  if (candidate.security_receipts.some((receipt) => !receipt.passed)) {
    return "REJECT";
  }
  if (
    !candidate.provenance_receipt.accepted ||
    candidate.provenance_receipt.subject_digest !== candidate.artifact_digest ||
    candidate.provenance_receipt.source_commit !== candidate.source_commit ||
    !candidateState.trustedProvenanceVerifiers.includes(
      candidate.provenance_receipt.verifier,
    ) ||
    !candidateState.acceptedProvenanceReceipts.some(
      (accepted) =>
        accepted.receipt_digest ===
          candidate.provenance_receipt.receipt_digest &&
        accepted.subject_digest ===
          candidate.provenance_receipt.subject_digest &&
        accepted.source_commit === candidate.provenance_receipt.source_commit &&
        accepted.verifier === candidate.provenance_receipt.verifier &&
        accepted.verified_at === candidate.provenance_receipt.verified_at &&
        accepted.source_repository ===
          candidate.provenance_receipt.source_repository,
    )
  ) {
    return "REJECT";
  }
  if (
    candidate.action_type === "deploy.production" &&
    (!candidate.rollback.verified ||
      !candidate.rollback.target_digest ||
      !candidate.rollback.tested_at)
  ) {
    return "REJECT";
  }
  return "ALLOW";
}

function differentialSuite(): number {
  let assertions = 0;
  const principals = ["agent:build-1", "agent:other"] as const;
  const actions = [
    "artifact.build",
    "deploy.production",
    "secret.rotate",
  ] as const;
  const environments = ["staging", "production"] as const;
  const revokedModes = [false, true] as const;
  for (const principal of principals) {
    for (const action of actions) {
      for (const environment of environments) {
        for (const revoked of revokedModes) {
          const base =
            action === "deploy.production" ? productionRequest() : request();
          const candidate = clone(base);
          (
            candidate as {
              principal: string;
              action_type: ActionType;
              requested_transition: {
                from: Environment;
                to: Environment;
              };
            }
          ).principal = principal;
          (
            candidate as {
              action_type: ActionType;
            }
          ).action_type = action;
          (
            candidate as {
              requested_transition: {
                from: Environment;
                to: Environment;
              };
            }
          ).requested_transition = {
            from: environment === "production" ? "staging" : "development",
            to: environment,
          };
          if (candidate.human_approvals.length) {
            (
              candidate as {
                human_approvals: ReturnType<typeof signedApproval>[];
              }
            ).human_approvals[0] = signedApproval(action, environment);
          }
          const rule: AuthorizationRule = {
            id: "finite-domain-rule",
            principals: ["agent:build-1"],
            actions: [action],
            environments: [environment],
            artifactDigests: [DIGEST],
          };
          const candidateState: PolicyState = {
            ...state([rule]),
            currentTargetEnvironments: {
              [candidate.target]: candidate.requested_transition.from,
            },
            revokedPrincipals: revoked ? [principal] : [],
          };
          const actual = evaluateAction(candidate, candidateState).decision;
          const expected = referenceDecision(candidate, candidateState);
          assert.equal(
            actual,
            expected,
            `${principal}/${action}/${environment}/revoked=${revoked}`,
          );
          assertions++;
          if (actual === "REJECT") {
            assert.throws(
              () =>
                issueAuthorizationReceipt(
                  candidate,
                  candidateState,
                  privateKey,
                  "test-ed25519-key",
                ),
              /authorization rejected/,
            );
            assertions++;
          }
        }
      }
    }
  }
  return assertions;
}

const suites: Record<string, () => number> = {
  contract: contractSuite,
  negative: negativeSuite,
  mutation: mutationSuite,
  differential: differentialSuite,
};

const selected = process.argv[2] ?? "all";
const names = selected === "all" ? Object.keys(suites) : [selected];
let assertionCount = 0;
for (const name of names) {
  const suite = suites[name];
  if (!suite) {
    throw new Error(`unknown suite: ${name}`);
  }
  assertionCount += suite();
}
console.log(
  JSON.stringify({
    status: "PASS",
    claim_label: "IMPLEMENTED NOT DEPLOYED",
    suites: names,
    assertions: assertionCount,
  }),
);
