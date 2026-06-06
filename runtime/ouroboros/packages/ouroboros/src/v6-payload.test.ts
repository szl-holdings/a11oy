/**
 * v6 ecosystem layer tests — strict cardinality + behavioral assertions
 * for `a11oy_ultimate_replit_payload` v6.0.0.
 */

import { describe, expect, it } from 'vitest';
import {
  SHARED_RUNTIME_SERVICES_V6,
  V6_HALT_CONDITIONS,
  V6_NEW_HALT_CONDITIONS,
  TASK_TO_PACK_V6,
  TOOL_PERMISSION_MATRIX,
  checkToolPermission,
  SECRETS_BROKER_SPEC,
  SANDBOX_POLICY,
  AGENT_REGISTRY_REQUIRED_FIELDS,
  validateAgentRegistryEntry,
  V6_MANIFEST_SUMMARY,
  DOMAIN_PACKS,
} from './index.js';

describe('v6 shared runtime services', () => {
  it('declares the full v6 16-service shared runtime list', () => {
    expect(SHARED_RUNTIME_SERVICES_V6.length).toBe(16);
  });

  it('includes all v6-new services not present in v3/v4', () => {
    for (const svc of [
      'retrieval_runtime',
      'citation_runtime',
      'primary_source_runtime',
      'permission_runtime',
      'sandbox_runtime',
      'secrets_broker',
      'evaluation_runtime',
      'agent_registry',
    ]) {
      expect(SHARED_RUNTIME_SERVICES_V6).toContain(svc);
    }
  });

  it('the manifest count matches the array length', () => {
    expect(V6_MANIFEST_SUMMARY.counts.sharedRuntimeServices).toBe(
      SHARED_RUNTIME_SERVICES_V6.length,
    );
  });
});

describe('v6 halt conditions', () => {
  it('has exactly 10 halt conditions (v4 7 + v6 3 new)', () => {
    expect(V6_HALT_CONDITIONS.length).toBe(10);
  });

  it('declares the three v6-new halt conditions', () => {
    expect(V6_NEW_HALT_CONDITIONS).toEqual([
      'primary_source_required_but_unavailable',
      'permission_denied',
      'sandbox_policy_violation',
    ]);
  });

  it('every v6-new condition is in the full halt vocabulary', () => {
    for (const c of V6_NEW_HALT_CONDITIONS) {
      expect(V6_HALT_CONDITIONS).toContain(c);
    }
  });
});

describe('v6 routing (TASK_TO_PACK_V6)', () => {
  it('declares the v6 11-rule routing table', () => {
    expect(Object.keys(TASK_TO_PACK_V6)).toHaveLength(11);
  });

  it('routes regulated_monitoring → Sentra_pack', () => {
    expect(TASK_TO_PACK_V6.regulated_monitoring).toBe('Sentra_pack');
  });

  it('routes record_reconciliation → Amaru_pack', () => {
    expect(TASK_TO_PACK_V6.record_reconciliation).toBe('Amaru_pack');
  });

  it('routes filings → finance_ops, regulatory → legal_ops, government_data → government_workflows', () => {
    expect(TASK_TO_PACK_V6.filings).toBe('finance_ops');
    expect(TASK_TO_PACK_V6.regulatory).toBe('legal_ops');
    expect(TASK_TO_PACK_V6.government_data).toBe('government_workflows');
  });

  it('every v6-routed pack id resolves to a registered DOMAIN_PACKS entry', () => {
    for (const packId of Object.values(TASK_TO_PACK_V6)) {
      expect(DOMAIN_PACKS[packId]).toBeDefined();
    }
  });
});

describe('v6 tool permission matrix', () => {
  it('is enabled with deny-by-default', () => {
    expect(TOOL_PERMISSION_MATRIX.enabled).toBe(true);
    expect(TOOL_PERMISSION_MATRIX.denyByDefault).toBe(true);
    expect(TOOL_PERMISSION_MATRIX.requireExplicitAllow).toBe(true);
  });

  it('declares the v6 4 pack permission entries', () => {
    expect(Object.keys(TOOL_PERMISSION_MATRIX.packPermissions)).toHaveLength(4);
  });

  it('A11oy_core gets planner + router + retrieval + receipt + trace runtimes', () => {
    expect(TOOL_PERMISSION_MATRIX.packPermissions.A11oy_core!.allowedTools).toEqual([
      'planner',
      'router',
      'retrieval_runtime',
      'receipt_runtime',
      'trace_runtime',
    ]);
  });

  it('Sentra_pack gets primary_source_runtime + risk_engine', () => {
    const tools = TOOL_PERMISSION_MATRIX.packPermissions.Sentra_pack!.allowedTools;
    expect(tools).toContain('primary_source_runtime');
    expect(tools).toContain('risk_engine');
  });

  it('Amaru_pack gets merge_engine + consistency_engine', () => {
    const tools = TOOL_PERMISSION_MATRIX.packPermissions.Amaru_pack!.allowedTools;
    expect(tools).toContain('merge_engine');
    expect(tools).toContain('consistency_engine');
  });

  it('checkToolPermission allows in-list tools at low risk', () => {
    expect(
      checkToolPermission({
        packId: 'A11oy_core',
        tool: 'planner',
        riskTier: 'R1_low',
      }),
    ).toEqual({ allowed: true, reason: 'explicit_allow' });
  });

  it('checkToolPermission denies tools not in pack list (deny by default)', () => {
    expect(
      checkToolPermission({
        packId: 'A11oy_core',
        tool: 'merge_engine',
      }),
    ).toEqual({ allowed: false, reason: 'deny_by_default' });
  });

  it('checkToolPermission denies on unknown pack', () => {
    expect(
      checkToolPermission({ packId: 'nonexistent_pack', tool: 'planner' }),
    ).toEqual({ allowed: false, reason: 'unknown_pack' });
  });

  // The v6 contract only declares pack_permissions for 4 packs
  // (A11oy_core, Sentra_pack, Amaru_pack, research_ops). Any other
  // routed pack (finance_ops, legal_ops, government_workflows,
  // property_ops) intentionally falls through to deny-by-default
  // per the contract's `defaults.deny_by_default = true`. This test
  // pins that expected behavior so future contract changes that
  // expand pack coverage are caught here.
  it('packs not declared in matrix deny-by-default (per contract defaults)', () => {
    for (const packId of [
      'finance_ops',
      'legal_ops',
      'government_workflows',
      'property_ops',
    ]) {
      expect(
        checkToolPermission({ packId, tool: 'retrieval_runtime' }),
      ).toEqual({ allowed: false, reason: 'unknown_pack' });
    }
  });

  it('checkToolPermission requires approval for R3 mutating', () => {
    expect(
      checkToolPermission({
        packId: 'Sentra_pack',
        tool: 'risk_engine',
        riskTier: 'R3_high',
        mutating: true,
      }),
    ).toEqual({ allowed: false, reason: 'requires_approval' });
  });

  it('checkToolPermission allows R3 mutating after approval', () => {
    expect(
      checkToolPermission({
        packId: 'Sentra_pack',
        tool: 'risk_engine',
        riskTier: 'R3_high',
        mutating: true,
        approved: true,
      }),
    ).toEqual({ allowed: true, reason: 'explicit_allow' });
  });

  it('checkToolPermission keeps R4 read-only until approved', () => {
    expect(
      checkToolPermission({
        packId: 'Sentra_pack',
        tool: 'risk_engine',
        riskTier: 'R4_critical',
      }),
    ).toEqual({ allowed: false, reason: 'read_only_until_approved' });
  });
});

describe('v6 secrets broker spec', () => {
  it('is enabled in runtime injection + scoped brokerage mode', () => {
    expect(SECRETS_BROKER_SPEC.enabled).toBe(true);
    expect(SECRETS_BROKER_SPEC.mode).toBe('runtime_injection_and_scoped_brokerage');
  });

  it('declares all 4 v6 managed secrets', () => {
    expect(SECRETS_BROKER_SPEC.managedSecrets).toEqual([
      'KATZILLA_API_KEY',
      'OPENAI_API_KEY',
      'DATABASE_URL',
      'NEON_DATABASE_URL',
    ]);
  });

  it('declares the 3 brokerage rules', () => {
    expect(SECRETS_BROKER_SPEC.rules).toHaveLength(3);
  });
});

describe('v6 sandbox policy', () => {
  it('declares the 3 v6 execution classes and halts on violation', () => {
    expect(SANDBOX_POLICY.classes).toHaveLength(3);
    expect(SANDBOX_POLICY.violationsHaltRun).toBe(true);
  });

  it('trusted_internal class allows receipt_write + trace_write + read_only_retrieval', () => {
    const c = SANDBOX_POLICY.classes.find((x) => x.classId === 'trusted_internal')!;
    expect(c.allowed).toContain('receipt_write');
    expect(c.allowed).toContain('trace_write');
    expect(c.allowed).toContain('read_only_retrieval');
  });

  it('bounded_code_exec restricts secret access and network egress', () => {
    const c = SANDBOX_POLICY.classes.find((x) => x.classId === 'bounded_code_exec')!;
    expect(c.restrictions).toContain('no_unapproved_secret_access');
    expect(c.restrictions).toContain('no_unapproved_network_egress');
  });

  it('external_network_access is restricted to approved domains only', () => {
    const c = SANDBOX_POLICY.classes.find((x) => x.classId === 'external_network_access')!;
    expect(c.restrictions).toContain('approved_domains_only');
  });
});

describe('v6 agent registry', () => {
  it('requires the 8 v6-mandated inventory fields', () => {
    expect(AGENT_REGISTRY_REQUIRED_FIELDS).toEqual([
      'agent_id',
      'pack_id',
      'tool_scope',
      'memory_scope',
      'risk_tier_limit',
      'approval_requirement',
      'dataset_access',
      'oversight_level',
    ]);
  });

  it('validateAgentRegistryEntry returns missing fields when entry is incomplete', () => {
    const missing = validateAgentRegistryEntry({
      agent_id: 'a1',
      pack_id: 'A11oy_core',
    });
    expect(missing).toContain('tool_scope');
    expect(missing).toContain('memory_scope');
    expect(missing).toContain('oversight_level');
  });

  it('validateAgentRegistryEntry returns [] when entry is complete', () => {
    const missing = validateAgentRegistryEntry({
      agent_id: 'a1',
      pack_id: 'A11oy_core',
      tool_scope: ['planner'],
      memory_scope: 'pack_local',
      risk_tier_limit: 'R2_moderate',
      approval_requirement: 'never',
      dataset_access: ['public'],
      oversight_level: 'minimal',
    });
    expect(missing).toEqual([]);
  });
});

describe('v6 manifest summary', () => {
  it('declares payload version 6.0.0 and A11oy_core control plane', () => {
    expect(V6_MANIFEST_SUMMARY.payloadVersion).toBe('6.0.0');
    expect(V6_MANIFEST_SUMMARY.payloadName).toBe('a11oy_ultimate_replit_payload');
    expect(V6_MANIFEST_SUMMARY.controlPlane).toBe('A11oy_core');
  });

  it('count fields match their underlying registries', () => {
    expect(V6_MANIFEST_SUMMARY.counts.haltConditions).toBe(V6_HALT_CONDITIONS.length);
    expect(V6_MANIFEST_SUMMARY.counts.newHaltConditionsVsV4).toBe(
      V6_NEW_HALT_CONDITIONS.length,
    );
    expect(V6_MANIFEST_SUMMARY.counts.v6RoutingRules).toBe(
      Object.keys(TASK_TO_PACK_V6).length,
    );
    expect(V6_MANIFEST_SUMMARY.counts.toolPermissionPacks).toBe(
      Object.keys(TOOL_PERMISSION_MATRIX.packPermissions).length,
    );
    expect(V6_MANIFEST_SUMMARY.counts.sandboxClasses).toBe(SANDBOX_POLICY.classes.length);
    expect(V6_MANIFEST_SUMMARY.counts.managedSecrets).toBe(
      SECRETS_BROKER_SPEC.managedSecrets.length,
    );
    expect(V6_MANIFEST_SUMMARY.counts.agentRegistryRequiredFields).toBe(
      AGENT_REGISTRY_REQUIRED_FIELDS.length,
    );
  });
});
