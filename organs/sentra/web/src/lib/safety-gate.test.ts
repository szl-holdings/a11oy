/**
 * Sentra Safety Gate — Deny-By-Default Unit Tests
 *
 * Self-contained vitest suite verifying that the policy engine denies
 * all offensive, cross-tenant, unregistered-asset, and missing-approval
 * actions. Run with: pnpm --filter @workspace/sentra test
 *
 * Doctrine: NIST SP 800-61r2, CISA CIRCIA §3(a), MITRE D3FEND, NSA AA22-320A
 */

import { describe, it, expect } from 'vitest';
import { runPolicyGate, ALLOWED_ACTION_CLASSES, SENTRA_DENIAL_MESSAGE } from './policy-engine';

// ─── Helper ───────────────────────────────────────────────────────────────────

function allowCtx(overrides: Partial<Parameters<typeof runPolicyGate>[0]> = {}): Parameters<typeof runPolicyGate>[0] {
  return {
    action_class: 'detect',
    target_asset_id: 'ASSET-0001',
    target_ownership_status: 'owned',
    integration_tenant_id: 'tenant-001',
    requesting_tenant_id: 'tenant-001',
    asset_tenant_id: 'tenant-001',
    approval_status: undefined,
    audit_logging_enabled: true,
    rollback_strategy_exists: true,
    asset_exists: true,
    ...overrides,
  };
}

// ─── 1. Deny-by-default: offensive actions ────────────────────────────────────

describe('Safety Gate — deny all offensive actions', () => {
  const OFFENSIVE_ACTIONS = [
    'hack_back',
    'exploit_attacker',
    'payload_delivery',
    'external_network_scan',
    'attacker_system_access',
    'counter_intrude',
    'offensive_recon',
    'ddos_attacker',
  ] as const;

  for (const action of OFFENSIVE_ACTIONS) {
    it(`denies action_class "${action}"`, () => {
      // These are not in ALLOWED_ACTION_CLASSES — gate must deny them.
      // @ts-expect-error intentionally testing unlisted class
      const result = runPolicyGate(allowCtx({ action_class: action }));
      expect(result.allowed).toBe(false);
      // PolicyGateResult has no policy_result field; allowed===false is the deny contract.
      expect(result.reason).toBeTruthy();
    });
  }
});

// ─── 2. Deny unregistered assets ─────────────────────────────────────────────

describe('Safety Gate — deny actions on unregistered assets', () => {
  it('denies contain_owned_asset when asset_exists=false', () => {
    const result = runPolicyGate(allowCtx({ action_class: 'contain_owned_asset', asset_exists: false }));
    expect(result.allowed).toBe(false);
    expect(result.denial_message).toBeTruthy();
  });

  it('denies revoke_owned_access when asset_exists=false', () => {
    const result = runPolicyGate(allowCtx({ action_class: 'revoke_owned_access', asset_exists: false }));
    expect(result.allowed).toBe(false);
  });

  it('denies preserve_evidence when asset_exists=false', () => {
    const result = runPolicyGate(allowCtx({ action_class: 'preserve_evidence', asset_exists: false }));
    expect(result.allowed).toBe(false);
  });
});

// ─── 3. Deny cross-tenant operations ─────────────────────────────────────────

describe('Safety Gate — deny cross-tenant operations', () => {
  it('denies when integration_tenant_id does not match requesting_tenant_id', () => {
    const result = runPolicyGate(allowCtx({
      action_class: 'contain_owned_asset',
      integration_tenant_id: 'tenant-999',
      requesting_tenant_id: 'tenant-001',
    }));
    expect(result.allowed).toBe(false);
  });

  it('denies when asset_tenant_id does not match requesting_tenant_id', () => {
    const result = runPolicyGate(allowCtx({
      action_class: 'contain_owned_asset',
      asset_tenant_id: 'tenant-999',
      requesting_tenant_id: 'tenant-001',
    }));
    expect(result.allowed).toBe(false);
  });

  it('denies external assets (monitored_external) regardless of action', () => {
    const result = runPolicyGate(allowCtx({
      action_class: 'contain_owned_asset',
      target_ownership_status: 'monitored_external',
    }));
    expect(result.allowed).toBe(false);
  });

  it('denies third_party assets (third_party) regardless of action', () => {
    const result = runPolicyGate(allowCtx({
      action_class: 'contain_owned_asset',
      target_ownership_status: 'third_party',
    }));
    expect(result.allowed).toBe(false);
  });
});

// ─── 4. Deny approval-gated actions without approval ─────────────────────────

describe('Safety Gate — deny approval-gated actions without approved record', () => {
  const APPROVAL_GATED = [
    'contain_owned_asset',
    'revoke_owned_access',
    'rotate_owned_secret',
  ] as const;

  for (const action of APPROVAL_GATED) {
    it(`denies "${action}" when approval_status=pending`, () => {
      const result = runPolicyGate(allowCtx({ action_class: action, approval_status: 'pending' }));
      expect(result.allowed).toBe(false);
    });

    it(`denies "${action}" when approval_status=rejected`, () => {
      const result = runPolicyGate(allowCtx({ action_class: action, approval_status: 'rejected' }));
      expect(result.allowed).toBe(false);
    });

    it(`denies "${action}" when approval_status=expired`, () => {
      const result = runPolicyGate(allowCtx({ action_class: action, approval_status: 'expired' }));
      expect(result.allowed).toBe(false);
    });

    it(`denies "${action}" when approval_status is missing (undefined)`, () => {
      const result = runPolicyGate(allowCtx({ action_class: action, approval_status: undefined }));
      expect(result.allowed).toBe(false);
    });

    it(`allows "${action}" when approval_status=approved and all other checks pass`, () => {
      const result = runPolicyGate(allowCtx({ action_class: action, approval_status: 'approved' }));
      expect(result.allowed).toBe(true);
    });
  }
});

// ─── 5. Allow defensive read actions without approval ────────────────────────

describe('Safety Gate — allow approved defensive read actions', () => {
  const READ_ACTIONS = ['detect', 'enrich', 'alert', 'notify', 'update_case', 'create_ticket'] as const;

  for (const action of READ_ACTIONS) {
    it(`allows "${action}" on owned asset`, () => {
      const result = runPolicyGate(allowCtx({ action_class: action }));
      expect(result.allowed).toBe(true);
      // PolicyGateResult has no policy_result field on the allow path — allowed===true is the contract.
      expect(result.reason).toContain('All policy checks passed');
    });
  }
});

// ─── 6. Denial message is the exact required string ──────────────────────────

describe('Safety Gate — denial message contract', () => {
  it('returns the canonical SENTRA_DENIAL_MESSAGE on asset-not-found denial', () => {
    const result = runPolicyGate(allowCtx({ asset_exists: false, action_class: 'contain_owned_asset' }));
    expect(result.allowed).toBe(false);
    expect(result.denial_message).toBe(SENTRA_DENIAL_MESSAGE);
  });
});

// ─── 7. ALLOWED_ACTION_CLASSES exhaustiveness ────────────────────────────────

describe('Safety Gate — ALLOWED_ACTION_CLASSES are all defensive', () => {
  it('all allowed action classes contain no offensive keywords', () => {
    const OFFENSIVE_KEYWORDS = ['hack', 'exploit', 'payload', 'attacker', 'retaliat', 'counter_intru', 'ddos'];
    for (const cls of ALLOWED_ACTION_CLASSES) {
      const lower = cls.toLowerCase();
      for (const kw of OFFENSIVE_KEYWORDS) {
        expect(lower).not.toContain(kw);
      }
    }
  });

  it('ALLOWED_ACTION_CLASSES has at least 10 defensive classes', () => {
    expect(ALLOWED_ACTION_CLASSES.length).toBeGreaterThanOrEqual(10);
  });
});

// ─── 8. Export runTestsAndReport for CI / node inline runner ─────────────────

export async function runTestsAndReport(): Promise<void> {
  console.log('[Sentra Safety Gate Tests] Use: pnpm --filter @workspace/sentra test');
}
