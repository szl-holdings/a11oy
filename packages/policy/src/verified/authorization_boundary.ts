/*
 * SPDX-License-Identifier: Apache-2.0
 * (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
 */

import {
  createHash,
  sign as ed25519Sign,
  verify as ed25519Verify,
  type KeyObject,
} from "node:crypto";

export type Environment = "development" | "staging" | "production";

export type ActionType =
  | "deploy.staging"
  | "deploy.production"
  | "secret.rotate"
  | "identity.change"
  | "repository.ruleset.change"
  | "model.promote"
  | "benchmark.publish"
  | "claim.upgrade"
  | "artifact.build";

export interface HumanApproval {
  readonly approver: string;
  readonly action_type: string;
  readonly target_digest: string;
  readonly environment: Environment;
  readonly approved_at: string;
  readonly expires_at: string;
  readonly key_id: string;
  readonly signature: string;
}

export interface ActionRequest {
  readonly request_id: string;
  readonly trace_id: string;
  readonly principal: string;
  readonly action_type: ActionType;
  readonly target: string;
  readonly source_commit: string;
  readonly artifact_digest: string;
  readonly requested_transition: {
    readonly from: Environment;
    readonly to: Environment;
  };
  readonly preconditions: readonly string[];
  readonly test_receipts: readonly string[];
  readonly provenance_receipt: {
    readonly receipt_digest: string;
    readonly subject_digest: string;
    readonly source_commit: string;
    readonly accepted: boolean;
    readonly verifier: string;
    readonly verified_at: string;
    readonly source_repository: "github.com/szl-holdings/a11oy";
  };
  readonly security_receipts: readonly {
    readonly control: string;
    readonly passed: boolean;
    readonly digest: string;
    readonly subject_digest: string;
  }[];
  readonly blast_radius: {
    readonly services: readonly string[];
    readonly users: string;
    readonly data: string;
  };
  readonly rollback: {
    readonly receipt_digest?: string;
    readonly target_digest?: string;
    readonly verified?: boolean;
    readonly tested_at?: string;
  };
  readonly human_approvals: readonly HumanApproval[];
  readonly expires_at: string;
}

export interface AuthorizationRule {
  readonly id: string;
  readonly principals: readonly string[];
  readonly actions: readonly ActionType[];
  readonly environments: readonly Environment[];
  readonly artifactDigests: readonly string[];
}

export interface PolicyState {
  readonly now: string;
  readonly policyVersion: string;
  readonly formalArtifactDigest: string;
  readonly currentTargetEnvironments: Readonly<Record<string, Environment>>;
  readonly rules: readonly AuthorizationRule[];
  readonly revokedPrincipals: readonly string[];
  readonly revokedPolicyVersions: readonly string[];
  readonly approvalPublicKeys: Readonly<Record<string, KeyObject>>;
  readonly approvalKeyOwners: Readonly<Record<string, string>>;
  readonly authorizationReceiptPublicKeys: Readonly<Record<string, KeyObject>>;
  readonly revokedAuthorizationReceiptKeyIds: readonly string[];
  readonly trustedProvenanceVerifiers: readonly string[];
  readonly acceptedProvenanceReceipts: readonly {
    readonly receipt_digest: string;
    readonly subject_digest: string;
    readonly source_commit: string;
    readonly verifier: string;
    readonly verified_at: string;
    readonly source_repository: "github.com/szl-holdings/a11oy";
  }[];
  readonly acceptedSecurityReceipts: readonly {
    readonly control: string;
    readonly digest: string;
    readonly subject_digest: string;
  }[];
  readonly requiredSecurityControls: readonly string[];
  readonly acceptedTestReceipts: readonly {
    readonly receipt_digest: string;
    readonly subject_digest: string;
  }[];
  readonly acceptedRollbackReceipts: readonly {
    readonly receipt_digest: string;
    readonly source_digest: string;
    readonly target_digest: string;
    readonly tested_at: string;
  }[];
}

export interface PolicyDecision {
  readonly decision: "ALLOW" | "REJECT";
  readonly reasonCodes: readonly string[];
  readonly requestDigest: string;
  readonly traceId: string | null;
  readonly ruleId: string | null;
}

export interface AuthorizationReceipt {
  readonly decision: "ALLOW";
  readonly request_digest: string;
  readonly policy_version: string;
  readonly formal_artifact_digest: string;
  readonly principal: string;
  readonly target_digest: string;
  readonly environment: Environment;
  readonly issued_at: string;
  readonly expires_at: string;
  readonly trace_id: string;
  readonly algorithm: "Ed25519";
  readonly key_id: string;
  readonly signature: string;
}

export interface ReceiptVerification {
  readonly valid: boolean;
  readonly reasons: readonly string[];
}

const ACTION_TYPES = new Set<ActionType>([
  "deploy.staging",
  "deploy.production",
  "secret.rotate",
  "identity.change",
  "repository.ruleset.change",
  "model.promote",
  "benchmark.publish",
  "claim.upgrade",
  "artifact.build",
]);

const ENVIRONMENTS = new Set<Environment>([
  "development",
  "staging",
  "production",
]);

const HIGH_RISK_ACTIONS = new Set<ActionType>([
  "deploy.production",
  "secret.rotate",
  "identity.change",
  "repository.ruleset.change",
  "model.promote",
  "benchmark.publish",
  "claim.upgrade",
]);

const LEGAL_TRANSITIONS: Readonly<
  Record<ActionType, readonly (readonly [Environment, Environment])[]>
> = {
  "deploy.staging": [["development", "staging"]],
  "deploy.production": [["staging", "production"]],
  "secret.rotate": [
    ["development", "development"],
    ["staging", "staging"],
    ["production", "production"],
  ],
  "identity.change": [
    ["development", "development"],
    ["staging", "staging"],
    ["production", "production"],
  ],
  "repository.ruleset.change": [["production", "production"]],
  "model.promote": [["staging", "production"]],
  "benchmark.publish": [["staging", "production"]],
  "claim.upgrade": [["staging", "production"]],
  "artifact.build": [["development", "staging"]],
};

const REQUEST_KEYS = [
  "action_type",
  "artifact_digest",
  "blast_radius",
  "expires_at",
  "human_approvals",
  "preconditions",
  "principal",
  "provenance_receipt",
  "request_id",
  "requested_transition",
  "rollback",
  "security_receipts",
  "source_commit",
  "target",
  "test_receipts",
  "trace_id",
] as const;

const RECEIPT_KEYS = [
  "algorithm",
  "decision",
  "environment",
  "expires_at",
  "formal_artifact_digest",
  "issued_at",
  "key_id",
  "policy_version",
  "principal",
  "request_digest",
  "signature",
  "target_digest",
  "trace_id",
] as const;

const DIGEST = /^sha256:[0-9a-f]{64}$/;
const SHA = /^[0-9a-f]{40}$/;
const TRACE_ID = /^(?!0{32}$)[0-9a-f]{32}$/;
const UUID =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const PRINCIPAL = /^[A-Za-z0-9][A-Za-z0-9:._/-]{2,255}$/;
const KEY_ID = /^[A-Za-z0-9][A-Za-z0-9:._/-]{2,255}$/;
const RFC3339 =
  /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isPlainRecord(value: unknown): value is Record<string, unknown> {
  if (!isRecord(value)) {
    return false;
  }
  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
}

function ownRecordValue(
  record: unknown,
  key: string,
): unknown {
  if (!isPlainRecord(record)) {
    return undefined;
  }
  return Object.prototype.hasOwnProperty.call(record, key)
    ? record[key]
    : undefined;
}

function jsonComplexityError(value: unknown): string | null {
  const stack: { readonly value: unknown; readonly depth: number }[] = [
    { value, depth: 0 },
  ];
  const seen = new WeakSet<object>();
  let nodes = 0;
  let stringUnits = 0;
  while (stack.length) {
    const current = stack.pop();
    if (!current) {
      break;
    }
    nodes += 1;
    if (nodes > 2048) {
      return "request:node-limit-exceeded";
    }
    if (current.depth > 16) {
      return "request:depth-limit-exceeded";
    }
    const item = current.value;
    if (item === null || typeof item === "boolean") {
      continue;
    }
    if (typeof item === "string") {
      if (item.length > 4096) {
        return "request:string-limit-exceeded";
      }
      stringUnits += item.length;
      if (stringUnits > 65536) {
        return "request:total-string-limit-exceeded";
      }
      continue;
    }
    if (typeof item === "number") {
      if (!Number.isFinite(item)) {
        return "request:non-finite-number";
      }
      continue;
    }
    if (typeof item !== "object") {
      return "request:non-json-value";
    }
    if (seen.has(item)) {
      return "request:cyclic-value";
    }
    seen.add(item);
    if (Array.isArray(item)) {
      if (item.length > 256) {
        return "request:array-limit-exceeded";
      }
      for (const child of item) {
        stack.push({ value: child, depth: current.depth + 1 });
      }
      continue;
    }
    const prototype = Object.getPrototypeOf(item);
    if (prototype !== Object.prototype && prototype !== null) {
      return "request:non-json-object";
    }
    const entries = Object.entries(item);
    if (entries.length > 64) {
      return "request:object-key-limit-exceeded";
    }
    for (const [key, child] of entries) {
      if (key.length > 4096) {
        return "request:object-key-string-limit-exceeded";
      }
      stringUnits += key.length;
      if (stringUnits > 65536) {
        return "request:total-string-limit-exceeded";
      }
      stack.push({ value: child, depth: current.depth + 1 });
    }
  }
  return null;
}

function exactKeys(
  value: Record<string, unknown>,
  allowed: readonly string[],
  location: string,
): string[] {
  const allowedSet = new Set(allowed);
  return Object.keys(value)
    .filter((key) => !allowedSet.has(key))
    .map((key) => `${location}:unknown-field:${key}`);
}

function validTimestamp(value: unknown): value is string {
  return (
    typeof value === "string" &&
    RFC3339.test(value) &&
    Number.isFinite(Date.parse(value))
  );
}

function timestamp(value: string): number {
  return Date.parse(value);
}

function isDigest(value: unknown): value is string {
  return typeof value === "string" && DIGEST.test(value);
}

function isImmutableTarget(value: unknown): value is string {
  if (typeof value !== "string" || value.length > 1024) {
    return false;
  }
  return (
    /^oci:\/\/\S+@sha256:[0-9a-f]{64}$/.test(value) ||
    /^(?:hf|github):\/\/[^@\s]+@[0-9a-f]{40}$/.test(value) ||
    /^urn:sha256:[0-9a-f]{64}$/.test(value)
  );
}

function targetMatchesRequest(
  target: string,
  artifactDigest: string,
  sourceCommit: string,
): boolean {
  if (target.startsWith("oci://")) {
    return target.endsWith(`@${artifactDigest}`);
  }
  if (target.startsWith("urn:sha256:")) {
    return target === artifactDigest.replace(/^sha256:/, "urn:sha256:");
  }
  if (target.startsWith("hf://") || target.startsWith("github://")) {
    return target.endsWith(`@${sourceCommit}`);
  }
  return false;
}

function validateApproval(value: unknown, index: number): string[] {
  const location = `human_approvals[${index}]`;
  if (!isRecord(value)) {
    return [`${location}:not-object`];
  }
  const errors = exactKeys(
    value,
    [
      "action_type",
      "approved_at",
      "approver",
      "environment",
      "expires_at",
      "key_id",
      "signature",
      "target_digest",
    ],
    location,
  );
  if (typeof value.approver !== "string" || !PRINCIPAL.test(value.approver)) {
    errors.push(`${location}:invalid-approver`);
  }
  if (
    typeof value.action_type !== "string" ||
    value.action_type.length > 64
  ) {
    errors.push(`${location}:invalid-action-type`);
  }
  if (!isDigest(value.target_digest)) {
    errors.push(`${location}:invalid-target-digest`);
  }
  if (
    typeof value.environment !== "string" ||
    !ENVIRONMENTS.has(value.environment as Environment)
  ) {
    errors.push(`${location}:invalid-environment`);
  }
  if (!validTimestamp(value.approved_at)) {
    errors.push(`${location}:invalid-approved-at`);
  }
  if (!validTimestamp(value.expires_at)) {
    errors.push(`${location}:invalid-expires-at`);
  }
  if (typeof value.key_id !== "string" || !KEY_ID.test(value.key_id)) {
    errors.push(`${location}:invalid-key-id`);
  }
  if (
    typeof value.signature !== "string" ||
    !/^[A-Za-z0-9_-]{64,256}$/.test(value.signature)
  ) {
    errors.push(`${location}:invalid-signature`);
  }
  return errors;
}

export function validateActionRequest(
  input: unknown,
  now: string,
): readonly string[] {
  if (!isRecord(input)) {
    return ["request:not-object"];
  }
  const errors = exactKeys(input, REQUEST_KEYS, "request");
  if (typeof input.request_id !== "string" || !UUID.test(input.request_id)) {
    errors.push("request:invalid-request-id");
  }
  if (typeof input.trace_id !== "string" || !TRACE_ID.test(input.trace_id)) {
    errors.push("request:invalid-trace-id");
  }
  if (typeof input.principal !== "string" || !PRINCIPAL.test(input.principal)) {
    errors.push("request:invalid-principal");
  }
  if (
    typeof input.action_type !== "string" ||
    !ACTION_TYPES.has(input.action_type as ActionType)
  ) {
    errors.push("request:unsupported-action-type");
  }
  if (!isImmutableTarget(input.target)) {
    errors.push("request:mutable-or-invalid-target");
  }
  if (typeof input.source_commit !== "string" || !SHA.test(input.source_commit)) {
    errors.push("request:invalid-source-commit");
  }
  if (!isDigest(input.artifact_digest)) {
    errors.push("request:invalid-artifact-digest");
  }
  if (
    isImmutableTarget(input.target) &&
    isDigest(input.artifact_digest) &&
    typeof input.source_commit === "string" &&
    SHA.test(input.source_commit) &&
    !targetMatchesRequest(
      input.target,
      input.artifact_digest,
      input.source_commit,
    )
  ) {
    errors.push("request:target-binding-mismatch");
  }

  if (!isRecord(input.requested_transition)) {
    errors.push("request:invalid-transition");
  } else {
    const transition = input.requested_transition;
    errors.push(
      ...exactKeys(transition, ["from", "to"], "transition"),
    );
    for (const key of ["from", "to"] as const) {
      const value = transition[key];
      if (
        typeof value !== "string" ||
        !ENVIRONMENTS.has(value as Environment)
      ) {
        errors.push(`transition:invalid-${key}`);
      }
    }
    if (
      typeof input.action_type === "string" &&
      ACTION_TYPES.has(input.action_type as ActionType) &&
      typeof transition.from === "string" &&
      typeof transition.to === "string" &&
      ENVIRONMENTS.has(transition.from as Environment) &&
      ENVIRONMENTS.has(transition.to as Environment) &&
      !LEGAL_TRANSITIONS[input.action_type as ActionType].some(
        ([from, to]) =>
          from === transition.from &&
          to === transition.to,
      )
    ) {
      errors.push("transition:illegal-for-action");
    }
  }

  if (
    !Array.isArray(input.preconditions) ||
    input.preconditions.length > 64 ||
    input.preconditions.some(
      (item) =>
        typeof item !== "string" || !item || item.length > 256,
    )
  ) {
    errors.push("request:invalid-preconditions");
  }
  if (
    !Array.isArray(input.test_receipts) ||
    input.test_receipts.length > 64 ||
    input.test_receipts.some((item) => !isDigest(item))
  ) {
    errors.push("request:invalid-test-receipts");
  }

  if (!isRecord(input.provenance_receipt)) {
    errors.push("request:invalid-provenance-receipt");
  } else {
    const provenance = input.provenance_receipt;
    errors.push(
      ...exactKeys(
        provenance,
        [
          "accepted",
          "receipt_digest",
          "source_commit",
          "source_repository",
          "subject_digest",
          "verified_at",
          "verifier",
        ],
        "provenance",
      ),
    );
    if (!isDigest(provenance.receipt_digest)) {
      errors.push("provenance:invalid-receipt-digest");
    }
    if (!isDigest(provenance.subject_digest)) {
      errors.push("provenance:invalid-subject-digest");
    }
    if (
      typeof provenance.source_commit !== "string" ||
      !SHA.test(provenance.source_commit)
    ) {
      errors.push("provenance:invalid-source-commit");
    }
    if (typeof provenance.accepted !== "boolean") {
      errors.push("provenance:invalid-accepted");
    }
    if (
      typeof provenance.verifier !== "string" ||
      provenance.verifier.length < 3 ||
      provenance.verifier.length > 256
    ) {
      errors.push("provenance:invalid-verifier");
    }
    if (!validTimestamp(provenance.verified_at)) {
      errors.push("provenance:invalid-verified-at");
    }
    if (provenance.source_repository !== "github.com/szl-holdings/a11oy") {
      errors.push("provenance:wrong-source-repository");
    }
  }

  if (
    !Array.isArray(input.security_receipts) ||
    input.security_receipts.length > 64
  ) {
    errors.push("request:invalid-security-receipts");
  } else {
    input.security_receipts.forEach((receipt, index) => {
      const location = `security_receipts[${index}]`;
      if (!isRecord(receipt)) {
        errors.push(`${location}:not-object`);
        return;
      }
      errors.push(
        ...exactKeys(
          receipt,
          ["control", "digest", "passed", "subject_digest"],
          location,
        ),
      );
      if (
        typeof receipt.control !== "string" ||
        !receipt.control ||
        receipt.control.length > 128
      ) {
        errors.push(`${location}:invalid-control`);
      }
      if (typeof receipt.passed !== "boolean") {
        errors.push(`${location}:invalid-passed`);
      }
      if (!isDigest(receipt.digest)) {
        errors.push(`${location}:invalid-digest`);
      }
      if (!isDigest(receipt.subject_digest)) {
        errors.push(`${location}:invalid-subject-digest`);
      }
    });
  }

  if (!isRecord(input.blast_radius)) {
    errors.push("request:invalid-blast-radius");
  } else {
    errors.push(
      ...exactKeys(
        input.blast_radius,
        ["data", "services", "users"],
        "blast-radius",
      ),
    );
    if (
      !Array.isArray(input.blast_radius.services) ||
      input.blast_radius.services.length > 64 ||
      input.blast_radius.services.some(
        (service) =>
          typeof service !== "string" ||
          !service ||
          service.length > 128,
      )
    ) {
      errors.push("blast-radius:invalid-services");
    }
    if (
      typeof input.blast_radius.users !== "string" ||
      !input.blast_radius.users ||
      input.blast_radius.users.length > 256
    ) {
      errors.push("blast-radius:invalid-users");
    }
    if (
      typeof input.blast_radius.data !== "string" ||
      !input.blast_radius.data ||
      input.blast_radius.data.length > 256
    ) {
      errors.push("blast-radius:invalid-data");
    }
  }

  if (!isRecord(input.rollback)) {
    errors.push("request:invalid-rollback");
  } else {
    errors.push(
      ...exactKeys(
        input.rollback,
        ["receipt_digest", "target_digest", "tested_at", "verified"],
        "rollback",
      ),
    );
    if (
      input.rollback.receipt_digest !== undefined &&
      !isDigest(input.rollback.receipt_digest)
    ) {
      errors.push("rollback:invalid-receipt-digest");
    }
    if (
      input.rollback.target_digest !== undefined &&
      !isDigest(input.rollback.target_digest)
    ) {
      errors.push("rollback:invalid-target-digest");
    }
    if (
      input.rollback.verified !== undefined &&
      typeof input.rollback.verified !== "boolean"
    ) {
      errors.push("rollback:invalid-verified");
    }
    if (
      input.rollback.tested_at !== undefined &&
      !validTimestamp(input.rollback.tested_at)
    ) {
      errors.push("rollback:invalid-tested-at");
    }
  }

  if (
    !Array.isArray(input.human_approvals) ||
    input.human_approvals.length > 16
  ) {
    errors.push("request:invalid-human-approvals");
  } else {
    input.human_approvals.forEach((approval, index) => {
      errors.push(...validateApproval(approval, index));
    });
  }
  if (!validTimestamp(input.expires_at)) {
    errors.push("request:invalid-expires-at");
  } else if (!validTimestamp(now) || timestamp(input.expires_at) <= timestamp(now)) {
    errors.push("request:expired");
  }
  return [...new Set(errors)].sort();
}

function canonicalize(value: unknown): string {
  if (value === null || typeof value === "boolean" || typeof value === "string") {
    return JSON.stringify(value);
  }
  if (typeof value === "number") {
    if (!Number.isFinite(value)) {
      throw new TypeError("non-finite numbers are not canonicalizable");
    }
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) {
    return `[${value.map(canonicalize).join(",")}]`;
  }
  if (isRecord(value)) {
    const fields = Object.keys(value)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${canonicalize(value[key])}`);
    return `{${fields.join(",")}}`;
  }
  throw new TypeError(`unsupported canonical value: ${typeof value}`);
}

export function sha256Digest(value: unknown): string {
  const complexityError = jsonComplexityError(value);
  if (complexityError) {
    throw new TypeError(complexityError);
  }
  return `sha256:${createHash("sha256").update(canonicalize(value)).digest("hex")}`;
}

function isEd25519PublicKey(value: unknown): value is KeyObject {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const candidate = value as {
    readonly type?: unknown;
    readonly asymmetricKeyType?: unknown;
  };
  return (
    candidate.type === "public" &&
    candidate.asymmetricKeyType === "ed25519"
  );
}

export function validatePolicyState(input: unknown): readonly string[] {
  if (!isPlainRecord(input)) {
    return ["state:not-object"];
  }
  const state = input as unknown as PolicyState;
  const errors: string[] = [];
  if (!validTimestamp(state.now)) {
    errors.push("state:invalid-now");
  }
  if (typeof state.policyVersion !== "string" || !SHA.test(state.policyVersion)) {
    errors.push("state:invalid-policy-version");
  }
  if (!isDigest(state.formalArtifactDigest)) {
    errors.push("state:invalid-formal-artifact-digest");
  }
  if (
    !isPlainRecord(state.currentTargetEnvironments) ||
    Object.entries(state.currentTargetEnvironments).some(
      ([target, environment]) =>
        !isImmutableTarget(target) ||
        typeof environment !== "string" ||
        !ENVIRONMENTS.has(environment as Environment),
    )
  ) {
    errors.push("state:invalid-current-target-environments");
  }
  if (!Array.isArray(state.rules)) {
    errors.push("state:invalid-rules");
  } else {
    state.rules.forEach((rule, index) => {
      const location = `state:rules[${index}]`;
      if (!isPlainRecord(rule)) {
        errors.push(`${location}:not-object`);
        return;
      }
      if (typeof rule.id !== "string" || !rule.id) {
        errors.push(`${location}:invalid-id`);
      }
      if (
        !Array.isArray(rule.principals) ||
        rule.principals.some(
          (principal: unknown) =>
            typeof principal !== "string" || !PRINCIPAL.test(principal),
        )
      ) {
        errors.push(`${location}:invalid-principals`);
      }
      if (
        !Array.isArray(rule.actions) ||
        rule.actions.some(
          (action: unknown) =>
            typeof action !== "string" ||
            !ACTION_TYPES.has(action as ActionType),
        )
      ) {
        errors.push(`${location}:invalid-actions`);
      }
      if (
        !Array.isArray(rule.environments) ||
        rule.environments.some(
          (environment: unknown) =>
            typeof environment !== "string" ||
            !ENVIRONMENTS.has(environment as Environment),
        )
      ) {
        errors.push(`${location}:invalid-environments`);
      }
      if (
        !Array.isArray(rule.artifactDigests) ||
        rule.artifactDigests.some((digest: unknown) => !isDigest(digest))
      ) {
        errors.push(`${location}:invalid-artifact-digests`);
      }
    });
  }
  if (
    !Array.isArray(state.revokedPrincipals) ||
    state.revokedPrincipals.some(
      (principal) => typeof principal !== "string" || !PRINCIPAL.test(principal),
    )
  ) {
    errors.push("state:invalid-revoked-principals");
  }
  if (
    !Array.isArray(state.revokedPolicyVersions) ||
    state.revokedPolicyVersions.some(
      (version) => typeof version !== "string" || !SHA.test(version),
    )
  ) {
    errors.push("state:invalid-revoked-policy-versions");
  }
  if (
    !isPlainRecord(state.approvalPublicKeys) ||
    Object.entries(state.approvalPublicKeys).some(
      ([keyId, key]) => !KEY_ID.test(keyId) || !isEd25519PublicKey(key),
    )
  ) {
    errors.push("state:invalid-approval-public-keys");
  }
  if (
    !isPlainRecord(state.approvalKeyOwners) ||
    Object.entries(state.approvalKeyOwners).some(
      ([keyId, approver]) =>
        !KEY_ID.test(keyId) ||
        typeof approver !== "string" ||
        !PRINCIPAL.test(approver) ||
        !isEd25519PublicKey(
          ownRecordValue(state.approvalPublicKeys, keyId),
        ),
    ) ||
    (isPlainRecord(state.approvalPublicKeys)
      ? Object.keys(state.approvalPublicKeys)
      : []
    ).some(
      (keyId) =>
        typeof ownRecordValue(state.approvalKeyOwners, keyId) !== "string",
    )
  ) {
    errors.push("state:invalid-approval-key-owners");
  }
  if (
    !isPlainRecord(state.authorizationReceiptPublicKeys) ||
    Object.entries(state.authorizationReceiptPublicKeys).some(
      ([keyId, key]) => !KEY_ID.test(keyId) || !isEd25519PublicKey(key),
    )
  ) {
    errors.push("state:invalid-authorization-receipt-public-keys");
  }
  if (
    !Array.isArray(state.revokedAuthorizationReceiptKeyIds) ||
    state.revokedAuthorizationReceiptKeyIds.some(
      (keyId) => typeof keyId !== "string" || !KEY_ID.test(keyId),
    )
  ) {
    errors.push("state:invalid-revoked-authorization-receipt-key-ids");
  }
  if (
    !Array.isArray(state.trustedProvenanceVerifiers) ||
    state.trustedProvenanceVerifiers.some(
      (verifier) => typeof verifier !== "string" || !PRINCIPAL.test(verifier),
    )
  ) {
    errors.push("state:invalid-trusted-provenance-verifiers");
  }
  if (
    !Array.isArray(state.acceptedProvenanceReceipts) ||
    state.acceptedProvenanceReceipts.some(
      (receipt: unknown) =>
        !isRecord(receipt) ||
        !isDigest(receipt.receipt_digest) ||
        !isDigest(receipt.subject_digest) ||
        typeof receipt.source_commit !== "string" ||
        !SHA.test(receipt.source_commit) ||
        typeof receipt.verifier !== "string" ||
        !(
          Array.isArray(state.trustedProvenanceVerifiers) &&
          state.trustedProvenanceVerifiers.includes(receipt.verifier)
        ) ||
        !validTimestamp(receipt.verified_at) ||
        receipt.source_repository !== "github.com/szl-holdings/a11oy",
    )
  ) {
    errors.push("state:invalid-accepted-provenance-receipts");
  }
  if (
    !Array.isArray(state.acceptedSecurityReceipts) ||
    state.acceptedSecurityReceipts.some(
      (receipt: unknown) =>
        !isRecord(receipt) ||
        typeof receipt.control !== "string" ||
        !receipt.control ||
        !isDigest(receipt.digest) ||
        !isDigest(receipt.subject_digest),
    )
  ) {
    errors.push("state:invalid-accepted-security-receipts");
  }
  if (
    !Array.isArray(state.acceptedTestReceipts) ||
    state.acceptedTestReceipts.some(
      (receipt: unknown) =>
        !isRecord(receipt) ||
        !isDigest(receipt.receipt_digest) ||
        !isDigest(receipt.subject_digest),
    )
  ) {
    errors.push("state:invalid-accepted-test-receipts");
  }
  if (
    !Array.isArray(state.acceptedRollbackReceipts) ||
    state.acceptedRollbackReceipts.some(
      (receipt: unknown) =>
        !isRecord(receipt) ||
        !isDigest(receipt.receipt_digest) ||
        !isDigest(receipt.source_digest) ||
        !isDigest(receipt.target_digest) ||
        !validTimestamp(receipt.tested_at),
    )
  ) {
    errors.push("state:invalid-accepted-rollback-receipts");
  }
  if (
    !Array.isArray(state.requiredSecurityControls) ||
    state.requiredSecurityControls.some(
      (control) => typeof control !== "string" || !control,
    )
  ) {
    errors.push("state:invalid-required-security-controls");
  }
  return [...new Set(errors)].sort();
}

type UnsignedHumanApproval = Omit<HumanApproval, "signature">;

function unsignedHumanApproval(
  approval: HumanApproval,
): UnsignedHumanApproval {
  const { signature: _signature, ...unsigned } = approval;
  return unsigned;
}

export function issueHumanApproval(
  approval: UnsignedHumanApproval,
  privateKey: KeyObject,
): HumanApproval {
  if (
    privateKey.type !== "private" ||
    privateKey.asymmetricKeyType !== "ed25519"
  ) {
    throw new TypeError("human approval signing key must be an Ed25519 private key");
  }
  const signature = ed25519Sign(
    null,
    Buffer.from(canonicalize(approval), "utf-8"),
    privateKey,
  ).toString("base64url");
  return { ...approval, signature };
}

function matchingRule(
  request: ActionRequest,
  state: PolicyState,
): AuthorizationRule | null {
  return (
    state.rules.find(
      (rule) =>
        rule.principals.includes(request.principal) &&
        rule.actions.includes(request.action_type) &&
        rule.environments.includes(request.requested_transition.to) &&
        rule.artifactDigests.includes(request.artifact_digest),
    ) ?? null
  );
}

function validApproval(
  approval: HumanApproval,
  request: ActionRequest,
  state: PolicyState,
): boolean {
  const publicKey = ownRecordValue(
    state.approvalPublicKeys,
    approval.key_id,
  );
  if (
    !isEd25519PublicKey(publicKey) ||
    ownRecordValue(state.approvalKeyOwners, approval.key_id) !==
      approval.approver
  ) {
    return false;
  }
  const bindingsValid =
    approval.approver !== request.principal &&
    approval.action_type === request.action_type &&
    approval.target_digest === request.artifact_digest &&
    approval.environment === request.requested_transition.to &&
    timestamp(approval.approved_at) <= timestamp(state.now) &&
    timestamp(approval.expires_at) > timestamp(state.now);
  if (!bindingsValid) {
    return false;
  }
  try {
    return ed25519Verify(
      null,
      Buffer.from(canonicalize(unsignedHumanApproval(approval)), "utf-8"),
      publicKey,
      Buffer.from(approval.signature, "base64url"),
    );
  } catch {
    return false;
  }
}

export function evaluateAction(
  input: unknown,
  state: PolicyState,
): PolicyDecision {
  let requestDigest: string;
  try {
    requestDigest = sha256Digest(input);
  } catch {
    return {
      decision: "REJECT",
      reasonCodes: ["SCHEMA_REQUEST_NON_CANONICAL"],
      requestDigest: sha256Digest({ invalid_request: true }),
      traceId: null,
      ruleId: null,
    };
  }
  const stateErrors = validatePolicyState(state);
  const stateNow =
    isPlainRecord(state) && typeof state.now === "string" ? state.now : "";
  const errors = validateActionRequest(input, stateNow);
  const traceId =
    isRecord(input) && typeof input.trace_id === "string" ? input.trace_id : null;
  if (stateErrors.length || errors.length) {
    return {
      decision: "REJECT",
      reasonCodes: [
        ...stateErrors.map((error) => `POLICY_${error.toUpperCase()}`),
        ...errors.map((error) => `SCHEMA_${error.toUpperCase()}`),
      ].sort(),
      requestDigest,
      traceId,
      ruleId: null,
    };
  }
  const request = input as unknown as ActionRequest;
  const reasons: string[] = [];
  if (state.revokedPrincipals.includes(request.principal)) {
    reasons.push("PRINCIPAL_REVOKED");
  }
  if (state.revokedPolicyVersions.includes(state.policyVersion)) {
    reasons.push("POLICY_VERSION_REVOKED");
  }
  if (
    ownRecordValue(state.currentTargetEnvironments, request.target) !==
    request.requested_transition.from
  ) {
    reasons.push("CURRENT_ENVIRONMENT_MISMATCH");
  }
  const rule = matchingRule(request, state);
  if (!rule) {
    reasons.push("DEFAULT_DENY_NO_MATCHING_RULE");
  }
  if (
    HIGH_RISK_ACTIONS.has(request.action_type) &&
    !request.human_approvals.some((approval) =>
      validApproval(approval, request, state),
    )
  ) {
    reasons.push("VALID_HUMAN_APPROVAL_REQUIRED");
  }
  const trustedSecurityReceipt = (
    receipt: ActionRequest["security_receipts"][number],
  ): boolean =>
    receipt.subject_digest === request.artifact_digest &&
    state.acceptedSecurityReceipts.some(
      (accepted) =>
        accepted.control === receipt.control &&
        accepted.digest === receipt.digest &&
        accepted.subject_digest === receipt.subject_digest,
    );
  if (
    request.security_receipts.some(
      (receipt) => !receipt.passed || !trustedSecurityReceipt(receipt),
    )
  ) {
    reasons.push("SECURITY_RECEIPT_FAILED_OR_UNTRUSTED");
  }
  if (
    state.requiredSecurityControls.some(
      (control) =>
        !request.security_receipts.some(
          (receipt) =>
            receipt.control === control &&
            receipt.passed &&
            trustedSecurityReceipt(receipt),
        ),
    )
  ) {
    reasons.push("REQUIRED_SECURITY_CONTROL_MISSING");
  }
  if (
    request.test_receipts.some(
      (digest) =>
        !state.acceptedTestReceipts.some(
          (accepted) =>
            accepted.receipt_digest === digest &&
            accepted.subject_digest === request.artifact_digest,
        ),
    )
  ) {
    reasons.push("UNTRUSTED_TEST_RECEIPT");
  }
  if (
    !request.provenance_receipt.accepted ||
    request.provenance_receipt.subject_digest !== request.artifact_digest ||
    request.provenance_receipt.source_commit !== request.source_commit ||
    !state.trustedProvenanceVerifiers.includes(
      request.provenance_receipt.verifier,
    ) ||
    !state.acceptedProvenanceReceipts.some(
      (accepted) =>
        accepted.receipt_digest ===
          request.provenance_receipt.receipt_digest &&
        accepted.subject_digest ===
          request.provenance_receipt.subject_digest &&
        accepted.source_commit === request.provenance_receipt.source_commit &&
        accepted.verifier === request.provenance_receipt.verifier &&
        accepted.verified_at === request.provenance_receipt.verified_at &&
        accepted.source_repository ===
          request.provenance_receipt.source_repository,
    ) ||
    timestamp(request.provenance_receipt.verified_at) > timestamp(state.now)
  ) {
    reasons.push("ACCEPTED_PROVENANCE_REQUIRED");
  }
  if (request.action_type === "deploy.production") {
    if (request.test_receipts.length === 0) {
      reasons.push("TEST_RECEIPT_REQUIRED");
    }
    if (
      !request.rollback.verified ||
      !isDigest(request.rollback.receipt_digest) ||
      !isDigest(request.rollback.target_digest) ||
      request.rollback.target_digest === request.artifact_digest ||
      !validTimestamp(request.rollback.tested_at) ||
      timestamp(request.rollback.tested_at) > timestamp(state.now) ||
      !state.acceptedRollbackReceipts.some(
        (accepted) =>
          accepted.receipt_digest === request.rollback.receipt_digest &&
          accepted.source_digest === request.artifact_digest &&
          accepted.target_digest === request.rollback.target_digest &&
          accepted.tested_at === request.rollback.tested_at,
      )
    ) {
      reasons.push("VERIFIED_ROLLBACK_REQUIRED");
    }
  }
  return {
    decision: reasons.length ? "REJECT" : "ALLOW",
    reasonCodes: reasons.length ? [...new Set(reasons)].sort() : ["AUTHORIZED"],
    requestDigest,
    traceId: request.trace_id,
    ruleId: reasons.length ? null : rule?.id ?? null,
  };
}

function unsignedReceipt(receipt: AuthorizationReceipt): Omit<
  AuthorizationReceipt,
  "signature"
> {
  const { signature: _signature, ...unsigned } = receipt;
  return unsigned;
}

export function issueAuthorizationReceipt(
  request: ActionRequest,
  state: PolicyState,
  privateKey: KeyObject,
  keyId: string,
  ttlSeconds = 300,
): AuthorizationReceipt {
  if (!Number.isInteger(ttlSeconds) || ttlSeconds < 1 || ttlSeconds > 900) {
    throw new RangeError("receipt TTL must be an integer from 1 through 900 seconds");
  }
  const decision = evaluateAction(request, state);
  if (decision.decision !== "ALLOW") {
    throw new Error(`authorization rejected: ${decision.reasonCodes.join(",")}`);
  }
  const configuredPublicKey = ownRecordValue(
    state.authorizationReceiptPublicKeys,
    keyId,
  );
  if (
    !isEd25519PublicKey(configuredPublicKey) ||
    state.revokedAuthorizationReceiptKeyIds.includes(keyId)
  ) {
    throw new Error("authorization receipt signing key is untrusted or revoked");
  }
  const keyBindingChallenge = Buffer.from(
    "a11oy-authorization-receipt-key-binding-v1",
    "utf-8",
  );
  const keyBindingSignature = ed25519Sign(
    null,
    keyBindingChallenge,
    privateKey,
  );
  if (
    !ed25519Verify(
      null,
      keyBindingChallenge,
      configuredPublicKey,
      keyBindingSignature,
    )
  ) {
    throw new Error("authorization receipt private key does not match key_id");
  }
  const issued = timestamp(state.now);
  const expires = Math.min(
    issued + ttlSeconds * 1000,
    timestamp(request.expires_at),
  );
  const base = {
    decision: "ALLOW",
    request_digest: decision.requestDigest,
    policy_version: state.policyVersion,
    formal_artifact_digest: state.formalArtifactDigest,
    principal: request.principal,
    target_digest: request.artifact_digest,
    environment: request.requested_transition.to,
    issued_at: new Date(issued).toISOString(),
    expires_at: new Date(expires).toISOString(),
    trace_id: request.trace_id,
    algorithm: "Ed25519",
    key_id: keyId,
  } as const;
  const signature = ed25519Sign(
    null,
    Buffer.from(canonicalize(base), "utf-8"),
    privateKey,
  ).toString("base64url");
  return { ...base, signature };
}

function validateReceiptShape(input: unknown): readonly string[] {
  if (!isRecord(input)) {
    return ["receipt:not-object"];
  }
  const errors = exactKeys(input, RECEIPT_KEYS, "receipt");
  if (input.decision !== "ALLOW") {
    errors.push("receipt:decision-not-allow");
  }
  if (!isDigest(input.request_digest)) {
    errors.push("receipt:invalid-request-digest");
  }
  if (typeof input.policy_version !== "string" || !SHA.test(input.policy_version)) {
    errors.push("receipt:invalid-policy-version");
  }
  if (!isDigest(input.formal_artifact_digest)) {
    errors.push("receipt:invalid-formal-artifact-digest");
  }
  if (typeof input.principal !== "string" || !PRINCIPAL.test(input.principal)) {
    errors.push("receipt:invalid-principal");
  }
  if (!isDigest(input.target_digest)) {
    errors.push("receipt:invalid-target-digest");
  }
  if (
    typeof input.environment !== "string" ||
    !ENVIRONMENTS.has(input.environment as Environment)
  ) {
    errors.push("receipt:invalid-environment");
  }
  if (!validTimestamp(input.issued_at)) {
    errors.push("receipt:invalid-issued-at");
  }
  if (!validTimestamp(input.expires_at)) {
    errors.push("receipt:invalid-expires-at");
  }
  if (typeof input.trace_id !== "string" || !TRACE_ID.test(input.trace_id)) {
    errors.push("receipt:invalid-trace-id");
  }
  if (input.algorithm !== "Ed25519") {
    errors.push("receipt:unsupported-algorithm");
  }
  if (typeof input.key_id !== "string" || input.key_id.length < 3) {
    errors.push("receipt:invalid-key-id");
  }
  if (
    typeof input.signature !== "string" ||
    !/^[A-Za-z0-9_-]{64,256}$/.test(input.signature)
  ) {
    errors.push("receipt:invalid-signature");
  }
  return [...new Set(errors)].sort();
}

export function verifyAuthorizationReceipt(
  input: unknown,
  request: ActionRequest,
  state: PolicyState,
): ReceiptVerification {
  const reasons = [...validateReceiptShape(input)];
  const stateErrors = validatePolicyState(state);
  if (stateErrors.length) {
    return {
      valid: false,
      reasons: stateErrors.map((error) =>
        `POLICY_${error.toUpperCase()}`,
      ),
    };
  }
  if (reasons.length) {
    return { valid: false, reasons };
  }
  const receipt = input as AuthorizationReceipt;
  const expectedDecision = evaluateAction(request, state);
  if (expectedDecision.decision !== "ALLOW") {
    reasons.push("CURRENT_POLICY_REJECTS_REQUEST");
  }
  if (receipt.request_digest !== expectedDecision.requestDigest) {
    reasons.push("REQUEST_DIGEST_MISMATCH");
  }
  if (receipt.policy_version !== state.policyVersion) {
    reasons.push("POLICY_VERSION_MISMATCH");
  }
  if (receipt.formal_artifact_digest !== state.formalArtifactDigest) {
    reasons.push("FORMAL_ARTIFACT_MISMATCH");
  }
  if (receipt.principal !== request.principal) {
    reasons.push("PRINCIPAL_MISMATCH");
  }
  if (receipt.target_digest !== request.artifact_digest) {
    reasons.push("TARGET_DIGEST_MISMATCH");
  }
  if (receipt.environment !== request.requested_transition.to) {
    reasons.push("ENVIRONMENT_MISMATCH");
  }
  if (receipt.trace_id !== request.trace_id) {
    reasons.push("TRACE_ID_MISMATCH");
  }
  if (timestamp(receipt.issued_at) > timestamp(state.now)) {
    reasons.push("RECEIPT_NOT_YET_VALID");
  }
  if (timestamp(receipt.expires_at) <= timestamp(state.now)) {
    reasons.push("RECEIPT_EXPIRED");
  }
  if (state.revokedPrincipals.includes(receipt.principal)) {
    reasons.push("PRINCIPAL_REVOKED");
  }
  if (state.revokedPolicyVersions.includes(receipt.policy_version)) {
    reasons.push("POLICY_VERSION_REVOKED");
  }
  const publicKey = isPlainRecord(state.authorizationReceiptPublicKeys)
    ? ownRecordValue(
        state.authorizationReceiptPublicKeys,
        receipt.key_id,
      )
    : undefined;
  if (!isEd25519PublicKey(publicKey)) {
    reasons.push("RECEIPT_KEY_UNTRUSTED");
  }
  if (
    Array.isArray(state.revokedAuthorizationReceiptKeyIds) &&
    state.revokedAuthorizationReceiptKeyIds.includes(receipt.key_id)
  ) {
    reasons.push("RECEIPT_KEY_REVOKED");
  }
  let signatureValid = false;
  try {
    if (!isEd25519PublicKey(publicKey)) {
      throw new Error("missing authorization receipt public key");
    }
    signatureValid = ed25519Verify(
      null,
      Buffer.from(canonicalize(unsignedReceipt(receipt)), "utf-8"),
      publicKey,
      Buffer.from(receipt.signature, "base64url"),
    );
  } catch {
    signatureValid = false;
  }
  if (!signatureValid) {
    reasons.push("SIGNATURE_INVALID");
  }
  return {
    valid: reasons.length === 0,
    reasons: [...new Set(reasons)].sort(),
  };
}

export function canExecute(
  receipt: unknown,
  request: ActionRequest,
  state: PolicyState,
): boolean {
  return verifyAuthorizationReceipt(receipt, request, state).valid;
}
