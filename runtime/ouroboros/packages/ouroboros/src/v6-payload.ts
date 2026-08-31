/**
 * v6 ecosystem layer — `a11oy_ultimate_replit_payload` v6.0.0.
 *
 * Adds, on top of the v4 `replit_innovate_full_payload`:
 *   - `SHARED_RUNTIME_SERVICES_V6`   — 16-service shared runtime list
 *   - `V6_HALT_CONDITIONS`           — 10 halt reasons (3 new vs v4)
 *   - `TASK_TO_PACK_V6`              — extends v4 routing with regulated_monitoring,
 *                                      record_reconciliation, filings, regulatory,
 *                                      government_data
 *   - `TOOL_PERMISSION_MATRIX`       — least-privilege per pack + risk overrides
 *   - `SECRETS_BROKER_SPEC`          — managed secret list and brokerage rules
 *   - `SANDBOX_POLICY`               — three execution classes
 *   - `AGENT_REGISTRY_REQUIRED_FIELDS` — required inventory fields for every
 *                                       registered agent
 *
 * All surfaces are deeply frozen, deterministic, and dependency-free so the
 * payload can be replayed and audited from the api-server runtime without
 * any ambient state.
 */

import type { DomainPackId } from './domain-pack.js';
import type { RiskTier } from './risk-tier.js';

// ---------------------------------------------------------------------------
// Shared runtime services — top-level capabilities A11oy_core orchestrates.
// ---------------------------------------------------------------------------
export type SharedRuntimeServiceV6 =
  | 'trace_runtime'
  | 'receipt_runtime'
  | 'validator_runtime'
  | 'proof_router'
  | 'approval_gate'
  | 'replay_runtime'
  | 'memory_runtime'
  | 'retrieval_runtime'
  | 'citation_runtime'
  | 'primary_source_runtime'
  | 'health_contract'
  | 'permission_runtime'
  | 'sandbox_runtime'
  | 'secrets_broker'
  | 'evaluation_runtime'
  | 'agent_registry';

export const SHARED_RUNTIME_SERVICES_V6: readonly SharedRuntimeServiceV6[] =
  Object.freeze([
    'trace_runtime',
    'receipt_runtime',
    'validator_runtime',
    'proof_router',
    'approval_gate',
    'replay_runtime',
    'memory_runtime',
    'retrieval_runtime',
    'citation_runtime',
    'primary_source_runtime',
    'health_contract',
    'permission_runtime',
    'sandbox_runtime',
    'secrets_broker',
    'evaluation_runtime',
    'agent_registry',
  ]);

// ---------------------------------------------------------------------------
// Halt conditions — extends v4 with three new v6 reasons.
// ---------------------------------------------------------------------------
export type HaltConditionV6 =
  | 'low_delta_high_consistency'
  | 'validator_stop'
  | 'manual_approval_required'
  | 'risk_escalation_required'
  | 'budget_exhausted'
  | 'health_contract_failed'
  | 'proof_missing'
  | 'primary_source_required_but_unavailable'
  | 'permission_denied'
  | 'sandbox_policy_violation';

export const V6_HALT_CONDITIONS: readonly HaltConditionV6[] = Object.freeze([
  'low_delta_high_consistency',
  'validator_stop',
  'manual_approval_required',
  'risk_escalation_required',
  'budget_exhausted',
  'health_contract_failed',
  'proof_missing',
  'primary_source_required_but_unavailable',
  'permission_denied',
  'sandbox_policy_violation',
]);

/** Halt reasons new in v6 (not present in v4). */
export const V6_NEW_HALT_CONDITIONS: readonly HaltConditionV6[] = Object.freeze([
  'primary_source_required_but_unavailable',
  'permission_denied',
  'sandbox_policy_violation',
]);

// ---------------------------------------------------------------------------
// v6 extended task-type → pack routing.
// ---------------------------------------------------------------------------
export type RoutingTaskTypeV6 =
  | 'security_review'
  | 'regulated_monitoring'
  | 'data_sync'
  | 'record_reconciliation'
  | 'research'
  | 'finance'
  | 'filings'
  | 'legal'
  | 'regulatory'
  | 'government_data'
  | 'property_ops';

export const TASK_TO_PACK_V6: Readonly<Record<RoutingTaskTypeV6, DomainPackId>> =
  Object.freeze({
    security_review: 'Sentra_pack',
    regulated_monitoring: 'Sentra_pack',
    data_sync: 'Amaru_pack',
    record_reconciliation: 'Amaru_pack',
    research: 'research_ops',
    finance: 'finance_ops',
    filings: 'finance_ops',
    legal: 'legal_ops',
    regulatory: 'legal_ops',
    government_data: 'government_workflows',
    property_ops: 'property_ops',
  });

// ---------------------------------------------------------------------------
// Tool permission matrix — least-privilege pack-scoped tool allow-lists.
// ---------------------------------------------------------------------------
export type PermittedToolV6 =
  | 'planner'
  | 'router'
  | 'retrieval_runtime'
  | 'receipt_runtime'
  | 'trace_runtime'
  | 'primary_source_runtime'
  | 'risk_engine'
  | 'merge_engine'
  | 'consistency_engine'
  | 'citation_runtime'
  | 'proof_router';

export interface ToolPermissionEntry {
  readonly packId: DomainPackId;
  readonly allowedTools: readonly PermittedToolV6[];
}

export interface RiskTierOverride {
  readonly tier: RiskTier;
  readonly requireManualApprovalForMutatingTools?: boolean;
  readonly readOnlyUntilApproved?: boolean;
}

export interface ToolPermissionMatrix {
  readonly enabled: true;
  readonly denyByDefault: true;
  readonly requireExplicitAllow: true;
  readonly packPermissions: Readonly<Record<string, ToolPermissionEntry>>;
  readonly riskTierOverrides: readonly RiskTierOverride[];
}

export const TOOL_PERMISSION_MATRIX: ToolPermissionMatrix = Object.freeze({
  enabled: true,
  denyByDefault: true,
  requireExplicitAllow: true,
  packPermissions: Object.freeze({
    A11oy_core: Object.freeze({
      packId: 'A11oy_core' as DomainPackId,
      allowedTools: Object.freeze([
        'planner',
        'router',
        'retrieval_runtime',
        'receipt_runtime',
        'trace_runtime',
      ]) as readonly PermittedToolV6[],
    }),
    Sentra_pack: Object.freeze({
      packId: 'Sentra_pack' as DomainPackId,
      allowedTools: Object.freeze([
        'retrieval_runtime',
        'primary_source_runtime',
        'risk_engine',
        'receipt_runtime',
        'trace_runtime',
      ]) as readonly PermittedToolV6[],
    }),
    Amaru_pack: Object.freeze({
      packId: 'Amaru_pack' as DomainPackId,
      allowedTools: Object.freeze([
        'retrieval_runtime',
        'merge_engine',
        'consistency_engine',
        'receipt_runtime',
        'trace_runtime',
      ]) as readonly PermittedToolV6[],
    }),
    research_ops: Object.freeze({
      packId: 'research_ops' as DomainPackId,
      allowedTools: Object.freeze([
        'retrieval_runtime',
        'citation_runtime',
        'proof_router',
        'receipt_runtime',
      ]) as readonly PermittedToolV6[],
    }),
  }),
  riskTierOverrides: Object.freeze([
    Object.freeze({
      tier: 'R3_high' as RiskTier,
      requireManualApprovalForMutatingTools: true,
    }),
    Object.freeze({
      tier: 'R4_critical' as RiskTier,
      readOnlyUntilApproved: true,
    }),
  ]),
});

/**
 * Permission decision for a tool invocation under the v6 matrix. Pure:
 * deterministic in `(packId, tool, riskTier, mutating)`.
 *
 * Returns:
 *   allowed=false + reason='deny_by_default'        — tool not in pack list
 *   allowed=false + reason='unknown_pack'           — pack not registered
 *   allowed=false + reason='requires_approval'      — R3 mutating + needs approval
 *   allowed=false + reason='read_only_until_approved' — R4 not yet approved
 *   allowed=true  + reason='explicit_allow'         — tool in allow-list, no override
 */
export type PermissionDenyReason =
  | 'deny_by_default'
  | 'unknown_pack'
  | 'requires_approval'
  | 'read_only_until_approved';

export interface PermissionDecision {
  readonly allowed: boolean;
  readonly reason: PermissionDenyReason | 'explicit_allow';
}

export function checkToolPermission(input: {
  packId: string;
  tool: string;
  riskTier?: RiskTier;
  mutating?: boolean;
  approved?: boolean;
}): PermissionDecision {
  if (!Object.hasOwn(TOOL_PERMISSION_MATRIX.packPermissions, input.packId)) {
    return { allowed: false, reason: 'unknown_pack' };
  }
  const entry = TOOL_PERMISSION_MATRIX.packPermissions[input.packId]!;
  if (!entry.allowedTools.includes(input.tool as PermittedToolV6)) {
    return { allowed: false, reason: 'deny_by_default' };
  }
  if (input.riskTier === 'R4_critical' && !input.approved) {
    return { allowed: false, reason: 'read_only_until_approved' };
  }
  if (input.riskTier === 'R3_high' && input.mutating === true && !input.approved) {
    return { allowed: false, reason: 'requires_approval' };
  }
  return { allowed: true, reason: 'explicit_allow' };
}

// ---------------------------------------------------------------------------
// Secrets broker spec — agents never receive raw long-lived secrets.
// ---------------------------------------------------------------------------
export interface SecretsBrokerSpec {
  readonly enabled: true;
  readonly mode: 'runtime_injection_and_scoped_brokerage';
  readonly purpose: string;
  readonly rules: readonly string[];
  readonly managedSecrets: readonly string[];
}

export const SECRETS_BROKER_SPEC: SecretsBrokerSpec = Object.freeze({
  enabled: true,
  mode: 'runtime_injection_and_scoped_brokerage',
  purpose: 'Prevent broad exposure of raw credentials to agents and tools.',
  rules: Object.freeze([
    'Agents never receive unrestricted long-lived secrets in prompt context.',
    'Tool calls request scoped credentials through broker policies.',
    'Secrets use per-tool or per-provider scopes when possible.',
  ]),
  managedSecrets: Object.freeze([
    'KATZILLA_API_KEY',
    'OPENAI_API_KEY',
    'DATABASE_URL',
    'NEON_DATABASE_URL',
  ]),
});

// ---------------------------------------------------------------------------
// Sandbox policy — separates trusted and untrusted execution paths.
// ---------------------------------------------------------------------------
export type SandboxExecutionClassId =
  | 'trusted_internal'
  | 'bounded_code_exec'
  | 'external_network_access';

export interface SandboxExecutionClass {
  readonly classId: SandboxExecutionClassId;
  readonly allowed: readonly string[];
  readonly restrictions?: readonly string[];
}

export interface SandboxPolicy {
  readonly enabled: true;
  readonly purpose: string;
  readonly violationsHaltRun: true;
  readonly classes: readonly SandboxExecutionClass[];
}

export const SANDBOX_POLICY: SandboxPolicy = Object.freeze({
  enabled: true,
  purpose:
    'Separate trusted and untrusted execution paths for code, shell, file, and network actions.',
  violationsHaltRun: true,
  classes: Object.freeze([
    Object.freeze({
      classId: 'trusted_internal' as SandboxExecutionClassId,
      allowed: Object.freeze(['receipt_write', 'trace_write', 'read_only_retrieval']),
    }),
    Object.freeze({
      classId: 'bounded_code_exec' as SandboxExecutionClassId,
      allowed: Object.freeze(['time_limited_code', 'scoped_file_write']),
      restrictions: Object.freeze([
        'no_unapproved_secret_access',
        'no_unapproved_network_egress',
      ]),
    }),
    Object.freeze({
      classId: 'external_network_access' as SandboxExecutionClassId,
      allowed: Object.freeze(['approved_provider_fetches']),
      restrictions: Object.freeze(['approved_domains_only']),
    }),
  ]),
});

// ---------------------------------------------------------------------------
// Agent registry — required inventory fields for every registered agent.
// ---------------------------------------------------------------------------
export const AGENT_REGISTRY_REQUIRED_FIELDS = Object.freeze([
  'agent_id',
  'pack_id',
  'tool_scope',
  'memory_scope',
  'risk_tier_limit',
  'approval_requirement',
  'dataset_access',
  'oversight_level',
] as const);

export type AgentRegistryRequiredField = (typeof AGENT_REGISTRY_REQUIRED_FIELDS)[number];

export interface AgentRegistryEntry {
  readonly [k: string]: unknown;
}

/**
 * Validate that an agent registration entry includes every v6-required
 * inventory field. Returns the list of missing field names; an empty list
 * means the entry is admissible.
 */
export function validateAgentRegistryEntry(
  entry: AgentRegistryEntry,
): AgentRegistryRequiredField[] {
  const missing: AgentRegistryRequiredField[] = [];
  for (const f of AGENT_REGISTRY_REQUIRED_FIELDS) {
    if (!Object.hasOwn(entry, f)) missing.push(f);
  }
  return missing;
}

// ---------------------------------------------------------------------------
// v6 manifest summary — compact read-model for the /api/ouroboros/v6 surface.
// ---------------------------------------------------------------------------
export interface V6ManifestSummary {
  readonly payloadVersion: '6.0.0';
  readonly payloadName: 'a11oy_ultimate_replit_payload';
  readonly controlPlane: 'A11oy_core';
  readonly counts: {
    readonly sharedRuntimeServices: number;
    readonly haltConditions: number;
    readonly newHaltConditionsVsV4: number;
    readonly v6RoutingRules: number;
    readonly toolPermissionPacks: number;
    readonly sandboxClasses: number;
    readonly managedSecrets: number;
    readonly agentRegistryRequiredFields: number;
  };
}

export const V6_MANIFEST_SUMMARY: V6ManifestSummary = Object.freeze({
  payloadVersion: '6.0.0',
  payloadName: 'a11oy_ultimate_replit_payload',
  controlPlane: 'A11oy_core',
  counts: Object.freeze({
    sharedRuntimeServices: SHARED_RUNTIME_SERVICES_V6.length,
    haltConditions: V6_HALT_CONDITIONS.length,
    newHaltConditionsVsV4: V6_NEW_HALT_CONDITIONS.length,
    v6RoutingRules: Object.keys(TASK_TO_PACK_V6).length,
    toolPermissionPacks: Object.keys(TOOL_PERMISSION_MATRIX.packPermissions).length,
    sandboxClasses: SANDBOX_POLICY.classes.length,
    managedSecrets: SECRETS_BROKER_SPEC.managedSecrets.length,
    agentRegistryRequiredFields: AGENT_REGISTRY_REQUIRED_FIELDS.length,
  }),
});
