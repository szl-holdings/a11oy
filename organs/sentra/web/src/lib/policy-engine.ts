/**
 * Sentra Policy Engine — centralizes allow/deny action class lists.
 * Denied classes have NO callable code path — not just a UI hide.
 *
 * Public doctrine alignment:
 *   NIST CSF 2.0, NIST SP 800-61r2, CISA CIRCIA, MITRE ATT&CK/D3FEND,
 *   NSA Cybersecurity Directorate public guidance, DARPA published programs,
 *   FBI IC3, NCSC ACD
 */

import type { ActionClass, OwnershipStatus } from './sentra-store';
import { EXECUTABLE_STATUSES } from './sentra-store';

// ─── Allowed action classes ───────────────────────────────────────────────────
// These are the ONLY action classes that can be requested, approved, or executed.

export const ALLOWED_ACTION_CLASSES: readonly ActionClass[] = [
  'detect',
  'enrich',
  'alert',
  'approve',
  'contain_owned_asset',
  'revoke_owned_access',
  'rotate_owned_secret',
  'preserve_evidence',
  'generate_report',
  'notify',
  'create_ticket',
  'update_case',
  'export_evidence',
  'restore_owned_asset',
] as const;

// ─── Denied action classes ─────────────────────────────────────────────────────
// These strings are listed for documentation only. No code anywhere in this
// platform can request, route, or execute these actions. There is no callable
// code path. Adding any of these as a new ActionClass type would be a policy
// violation and fail code review.

export const DENIED_ACTION_CLASSES_DOCUMENTATION_ONLY = [
  'offensive',
  'retaliatory',
  'hack_back',
  'exploit',
  'payload',
  'unauthorized_access',
  'external_scan',
  'external_probe',
  'malware',
  'credential_theft',
  'ddos',
  'destructive_external_action',
  'third_party_code_execution',
  'exfiltration',
  'attacker_system_execution',
] as const;

// ─── High-impact actions requiring approval ─────────────────────────────────

export const HIGH_IMPACT_ACTIONS: readonly ActionClass[] = [
  'contain_owned_asset',
  'revoke_owned_access',
  'rotate_owned_secret',
  'export_evidence',
  'restore_owned_asset',
] as const;

// ─── Doctrine citations per action class ────────────────────────────────────

export const DOCTRINE_CITATIONS: Record<ActionClass, string[]> = {
  detect: ['NIST CSF 2.0 DE.AE', 'NIST SP 800-61r2 §3.1', 'CISA ACD Detection'],
  enrich: ['NIST SP 800-61r2 §3.2', 'MITRE ATT&CK Enrichment', 'FBI IC3 §4.2'],
  alert: ['NIST CSF 2.0 DE.CM', 'NIST SP 800-61r2 §3.2', 'CISA CIRCIA §6'],
  approve: ['NIST SP 800-61r2 §3.3', 'NSA Cybersecurity Advisory AA22-320A', 'MITRE D3FEND D3-HITL'],
  contain_owned_asset: ['NIST SP 800-61r2 §3.3', 'MITRE D3FEND D3-NI', 'CISA CIRCIA §3(a)', 'NSA CISA Joint Advisory'],
  revoke_owned_access: ['NIST SP 800-61r2 §3.3', 'MITRE D3FEND D3-DA', 'NIST IR 8374 §3.2', 'CISA KEV'],
  rotate_owned_secret: ['NIST SP 800-61r2 §3.3', 'MITRE D3FEND D3-CR', 'NSA Hardening Guide §5'],
  preserve_evidence: ['NIST SP 800-61r2 §3.4', 'FBI IC3 Evidence §2', 'CISA CIRCIA §7', 'NCSC ACD Evidence'],
  generate_report: ['NIST SP 800-61r2 §3.5', 'CISA CIRCIA Reporting', 'FBI IC3 Referral Standards'],
  notify: ['NIST SP 800-61r2 §3.2', 'CISA CIRCIA §6', 'FBI IC3 §3'],
  create_ticket: ['NIST SP 800-61r2 §3.2', 'NCSC ACD Playbooks'],
  update_case: ['NIST SP 800-61r2 §3.4', 'MITRE D3FEND D3-HITL'],
  export_evidence: ['NIST SP 800-61r2 §3.4', 'FBI IC3 §2.3', 'CISA CIRCIA §7'],
  restore_owned_asset: ['NIST SP 800-61r2 §3.4', 'NIST CSF 2.0 RC.RP', 'MITRE D3FEND D3-ROS'],
};

// ─── Policy Gate Result ──────────────────────────────────────────────────────

export interface PolicyGateResult {
  allowed: boolean;
  action_class: string;
  reason: string;
  denial_message?: string;
  doctrine_citations: string[];
  checked_at: string;
}

export const SENTRA_DENIAL_MESSAGE =
  'Action blocked by Sentra Policy Enforcement: target is not registered as an owned or authorized tenant asset, or the action is outside defensive scope.';

// ─── Policy Gate ─────────────────────────────────────────────────────────────

export interface GateContext {
  action_class: ActionClass;
  target_asset_id: string;
  target_ownership_status: OwnershipStatus;
  integration_tenant_id: string | null;
  requesting_tenant_id: string;
  asset_tenant_id: string;
  approval_status?: 'pending' | 'approved' | 'rejected' | 'expired' | 'canceled' | null;
  audit_logging_enabled: boolean;
  rollback_strategy_exists: boolean;
  asset_exists: boolean;
}

export function runPolicyGate(ctx: GateContext): PolicyGateResult {
  const now = new Date().toISOString();
  const citations = DOCTRINE_CITATIONS[ctx.action_class] ?? [];

  // 1. Action class must be in allowed list
  if (!ALLOWED_ACTION_CLASSES.includes(ctx.action_class)) {
    return {
      allowed: false,
      action_class: ctx.action_class,
      reason: `Action class '${ctx.action_class}' is not in the allowed defensive action list`,
      denial_message: SENTRA_DENIAL_MESSAGE,
      doctrine_citations: citations,
      checked_at: now,
    };
  }

  // 2. Target asset must exist in registry
  if (!ctx.asset_exists) {
    return {
      allowed: false,
      action_class: ctx.action_class,
      reason: 'Target asset does not exist in the Sentra Asset Registry',
      denial_message: SENTRA_DENIAL_MESSAGE,
      doctrine_citations: citations,
      checked_at: now,
    };
  }

  // 3. Ownership status must be executable
  if (!EXECUTABLE_STATUSES.includes(ctx.target_ownership_status)) {
    return {
      allowed: false,
      action_class: ctx.action_class,
      reason: `Target asset ownership_status '${ctx.target_ownership_status}' is not executable. Only owned, authorized, contracted_scope, and lab assets are executable.`,
      denial_message: SENTRA_DENIAL_MESSAGE,
      doctrine_citations: citations,
      checked_at: now,
    };
  }

  // 4. Integration must belong to same tenant (if integration is specified)
  if (ctx.integration_tenant_id && ctx.integration_tenant_id !== ctx.requesting_tenant_id) {
    return {
      allowed: false,
      action_class: ctx.action_class,
      reason: 'Integration belongs to a different tenant — cross-tenant action blocked',
      denial_message: SENTRA_DENIAL_MESSAGE,
      doctrine_citations: citations,
      checked_at: now,
    };
  }

  // 5. Asset must belong to same tenant
  if (ctx.asset_tenant_id !== ctx.requesting_tenant_id) {
    return {
      allowed: false,
      action_class: ctx.action_class,
      reason: 'Asset belongs to a different tenant — cross-tenant action blocked',
      denial_message: SENTRA_DENIAL_MESSAGE,
      doctrine_citations: citations,
      checked_at: now,
    };
  }

  // 6. High-impact actions require an approved approval record
  if (HIGH_IMPACT_ACTIONS.includes(ctx.action_class)) {
    if (!ctx.approval_status || ctx.approval_status !== 'approved') {
      return {
        allowed: false,
        action_class: ctx.action_class,
        reason: `High-impact action '${ctx.action_class}' requires an approved approval record. Current approval status: ${ctx.approval_status ?? 'none'}`,
        denial_message: SENTRA_DENIAL_MESSAGE,
        doctrine_citations: citations,
        checked_at: now,
      };
    }
  }

  // 7. Audit logging must be enabled
  if (!ctx.audit_logging_enabled) {
    return {
      allowed: false,
      action_class: ctx.action_class,
      reason: 'Audit logging is not enabled — action blocked per policy',
      denial_message: SENTRA_DENIAL_MESSAGE,
      doctrine_citations: citations,
      checked_at: now,
    };
  }

  // 8. Rollback strategy must exist for contain/restore actions
  if (
    (ctx.action_class === 'contain_owned_asset' || ctx.action_class === 'restore_owned_asset') &&
    !ctx.rollback_strategy_exists
  ) {
    return {
      allowed: false,
      action_class: ctx.action_class,
      reason: 'Containment and restore actions require a documented rollback strategy',
      denial_message: SENTRA_DENIAL_MESSAGE,
      doctrine_citations: citations,
      checked_at: now,
    };
  }

  return {
    allowed: true,
    action_class: ctx.action_class,
    reason: 'All policy checks passed — action is within defensive scope on an owned/authorized asset',
    doctrine_citations: citations,
    checked_at: now,
  };
}

// ─── Convenience checker ─────────────────────────────────────────────────────

export function isAllowedActionClass(ac: string): ac is ActionClass {
  return ALLOWED_ACTION_CLASSES.includes(ac as ActionClass);
}

export function requiresApproval(ac: ActionClass): boolean {
  return HIGH_IMPACT_ACTIONS.includes(ac);
}
