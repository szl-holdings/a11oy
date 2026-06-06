import { describe, expect, it } from 'vitest';
import {
  advanceAlmanac,
  DEFAULT_CYCLES,
  evaluateRiskTier,
  INITIAL_ALMANAC_STATE,
  PROOF_ROUTES,
  rebuildAlmanac,
  resolveProofRoute,
  RISK_TIERS,
  validateProofArtifacts,
} from './index.js';

describe('proof-route resolver', () => {
  it('routes system_design and informational claims to PRF_SYSTEM_CLAIMS', () => {
    expect(resolveProofRoute({ kind: 'claim', category: 'system_design' })?.routeId).toBe(
      'PRF_SYSTEM_CLAIMS',
    );
    expect(resolveProofRoute({ kind: 'claim', category: 'informational' })?.routeId).toBe(
      'PRF_SYSTEM_CLAIMS',
    );
  });

  it('routes security and threat_response actions to PRF_SECURITY_ACTIONS', () => {
    expect(resolveProofRoute({ kind: 'action', category: 'security' })?.routeId).toBe(
      'PRF_SECURITY_ACTIONS',
    );
    expect(resolveProofRoute({ kind: 'action', category: 'threat_response' })?.routeId).toBe(
      'PRF_SECURITY_ACTIONS',
    );
  });

  it('routes data_merge and data_sync actions to PRF_DATA_SYNC', () => {
    expect(resolveProofRoute({ kind: 'action', category: 'data_merge' })?.routeId).toBe(
      'PRF_DATA_SYNC',
    );
    expect(resolveProofRoute({ kind: 'action', category: 'data_sync' })?.routeId).toBe(
      'PRF_DATA_SYNC',
    );
  });

  it('exposes the canonical artifact requirements per route', () => {
    expect(PROOF_ROUTES.PRF_SYSTEM_CLAIMS.requiredArtifacts).toEqual([
      'source_binding',
      'trace_locator',
      'receipt',
    ]);
    expect(PROOF_ROUTES.PRF_SECURITY_ACTIONS.requiredArtifacts).toEqual([
      'validator_result',
      'risk_tier',
      'escalation_check',
      'receipt',
    ]);
    expect(PROOF_ROUTES.PRF_DATA_SYNC.requiredArtifacts).toEqual([
      'source_priority_record',
      'delta_log',
      'consistency_score',
      'receipt',
    ]);
  });

  it('returns the missing-artifact list when the receipt is incomplete', () => {
    const route = PROOF_ROUTES.PRF_SECURITY_ACTIONS;
    const present = new Set<'validator_result' | 'risk_tier' | 'receipt'>([
      'validator_result',
      'risk_tier',
      'receipt',
    ]);
    expect(validateProofArtifacts(route, present)).toEqual(['escalation_check']);
  });
});

describe('risk-tier escalation gate', () => {
  it('continues low/moderate tiers when no approval required', () => {
    expect(evaluateRiskTier({ tier: 'R1_low' }).gate).toBe('continue');
    expect(evaluateRiskTier({ tier: 'R2_moderate' }).gate).toBe('continue');
  });

  it('awaits approval for R3_high without granted approval', () => {
    expect(evaluateRiskTier({ tier: 'R3_high' }).gate).toBe('await_approval');
  });

  it('continues R3_high once approval is granted', () => {
    expect(
      evaluateRiskTier({ tier: 'R3_high', approvalGranted: true }).gate,
    ).toBe('continue');
  });

  it('always force-escalates R4_critical (even with approval flag)', () => {
    expect(
      evaluateRiskTier({ tier: 'R4_critical', approvalGranted: true }).gate,
    ).toBe('force_escalate');
  });

  it('replay_audit mode bypasses approval gates without lying about tier', () => {
    const decision = evaluateRiskTier({
      tier: 'R3_high',
      operatorMode: 'replay_audit',
    });
    expect(decision.gate).toBe('continue');
    expect(decision.tier).toBe('R3_high');
  });

  it('exposes immutable policy table aligned with the v2 contract', () => {
    expect(RISK_TIERS.R1_low.requiresManualApproval).toBe(false);
    expect(RISK_TIERS.R3_high.requiresManualApproval).toBe(true);
    expect(RISK_TIERS.R4_critical.forceEscalation).toBe(true);
  });
});

describe('contract tables are deeply immutable (replay-safe)', () => {
  it('PROOF_ROUTES nested arrays cannot be mutated at runtime', () => {
    expect(() => {
      // @ts-expect-error — runtime check that array mutation is rejected
      PROOF_ROUTES.PRF_DATA_SYNC.requiredArtifacts.push('receipt');
    }).toThrow();
    expect(() => {
      // @ts-expect-error — runtime check that field mutation is rejected
      PROOF_ROUTES.PRF_SECURITY_ACTIONS.appliesTo = 'tampered';
    }).toThrow();
  });

  it('RISK_TIERS policies cannot be mutated at runtime', () => {
    expect(() => {
      // @ts-expect-error — runtime check that field mutation is rejected
      RISK_TIERS.R4_critical.forceEscalation = false;
    }).toThrow();
    expect(() => {
      // @ts-expect-error — runtime check that field mutation is rejected
      RISK_TIERS.R3_high.requiresManualApproval = false;
    }).toThrow();
  });

  it('DEFAULT_CYCLES entries cannot be mutated at runtime', () => {
    expect(() => {
      // @ts-expect-error — runtime check that field mutation is rejected
      DEFAULT_CYCLES[0].stepInterval = 99;
    }).toThrow();
  });
});

describe('almanac cycle advancer', () => {
  it('advances madrid every step, paris every 3 steps, grolier every 2 steps', () => {
    const after = rebuildAlmanac(6);
    expect(after.state.madrid_almanac_cycle).toBe(6);
    expect(after.state.paris_long_cycle).toBe(2);
    expect(after.state.grolier_schedule_cycle).toBe(3);
  });

  it('emits one event per cycle that ticks at a given step', () => {
    const r = advanceAlmanac(INITIAL_ALMANAC_STATE, 0, DEFAULT_CYCLES);
    const ids = r.events.map((e) => e.cycleId).sort();
    expect(ids).toEqual(['madrid_almanac_cycle']);
    const r2 = advanceAlmanac(r.state, 1, DEFAULT_CYCLES);
    expect(r2.events.map((e) => e.cycleId).sort()).toEqual([
      'grolier_schedule_cycle',
      'madrid_almanac_cycle',
    ]);
  });

  it('is deterministic — same inputs produce same state and events', () => {
    const a = rebuildAlmanac(10);
    const b = rebuildAlmanac(10);
    expect(a.state).toEqual(b.state);
    expect(a.events).toEqual(b.events);
  });
});
