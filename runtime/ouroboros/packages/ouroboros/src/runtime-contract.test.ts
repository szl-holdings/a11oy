import { describe, expect, it } from 'vitest';
import {
  advanceAlmanac,
  buildEvidencePack,
  DEFAULT_CYCLES,
  DEFAULT_DENY_PROVIDER,
  dispatchDomainPack,
  DOMAIN_PACKS,
  evaluateRiskTier,
  INITIAL_ALMANAC_STATE,
  isAutoExecutionAllowed,
  makeAutoGrantProvider,
  OPERATIONAL_MODES,
  PROOF_ROUTES,
  rebuildAlmanac,
  requestApproval,
  resolveProofRoute,
  RISK_TIERS,
  V3_CYCLES,
  validateEvidencePack,
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
    // review_cycle stays at 0 under DEFAULT_CYCLES (v2 behavior)
    expect(after.state.review_cycle).toBe(0);
  });

  it('v3 cycles add review_cycle on a 2-step interval', () => {
    const after = rebuildAlmanac(6, V3_CYCLES);
    expect(after.state.review_cycle).toBe(3);
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

describe('v3 proof route id aliases', () => {
  it('PRF_SECURITY_ACTION (v3) requires the v3-exact artifact set, not the v2 one', () => {
    expect(PROOF_ROUTES.PRF_SECURITY_ACTION.requiredArtifacts).toEqual([
      'validator_result',
      'escalation_check',
      'receipt',
      'approval_if_required',
    ]);
    // v2 contract is still served separately for v2 receipts.
    expect(PROOF_ROUTES.PRF_SECURITY_ACTIONS.requiredArtifacts).toEqual([
      'validator_result',
      'risk_tier',
      'escalation_check',
      'receipt',
    ]);
  });

  it('PRF_DATA_CONVERGENCE (v3) shares the contract of PRF_DATA_SYNC (v2)', () => {
    expect(PROOF_ROUTES.PRF_DATA_CONVERGENCE.requiredArtifacts).toEqual(
      PROOF_ROUTES.PRF_DATA_SYNC.requiredArtifacts,
    );
  });
});

describe('v3 proof routes', () => {
  it('exposes PRF_CLAIM_BOUND_RESEARCH with v3 contract artifacts', () => {
    expect(PROOF_ROUTES.PRF_CLAIM_BOUND_RESEARCH.requiredArtifacts).toEqual([
      'source_binding',
      'locator',
      'trace_reference',
      'receipt',
    ]);
  });

  it('exposes PRF_OPERATIONAL_ACTION with validator+risk_tier+receipt', () => {
    expect(PROOF_ROUTES.PRF_OPERATIONAL_ACTION.requiredArtifacts).toEqual([
      'validator_result',
      'risk_tier',
      'receipt',
    ]);
  });

  it('routes research_claim and thesis_assertion to PRF_CLAIM_BOUND_RESEARCH', () => {
    expect(resolveProofRoute({ kind: 'claim', category: 'research_claim' })?.routeId).toBe(
      'PRF_CLAIM_BOUND_RESEARCH',
    );
    expect(resolveProofRoute({ kind: 'claim', category: 'thesis_assertion' })?.routeId).toBe(
      'PRF_CLAIM_BOUND_RESEARCH',
    );
  });

  it('routes operational_action and client_action to PRF_OPERATIONAL_ACTION', () => {
    expect(resolveProofRoute({ kind: 'action', category: 'operational_action' })?.routeId).toBe(
      'PRF_OPERATIONAL_ACTION',
    );
    expect(resolveProofRoute({ kind: 'action', category: 'client_action' })?.routeId).toBe(
      'PRF_OPERATIONAL_ACTION',
    );
  });
});

describe('domain-pack dispatcher', () => {
  it('routes by canonical task type', () => {
    expect(dispatchDomainPack({ taskType: 'agent_orchestration' }).pack.packId).toBe(
      'A11oy_core',
    );
    expect(dispatchDomainPack({ taskType: 'data_sync' }).pack.packId).toBe('data_sync_ops');
    expect(dispatchDomainPack({ taskType: 'security_ops' }).pack.packId).toBe('security_ops');
    expect(dispatchDomainPack({ taskType: 'medical_review' }).pack.packId).toBe(
      'medical_review',
    );
  });

  it('honors a forced pack override', () => {
    const decision = dispatchDomainPack({
      taskType: 'agent_orchestration',
      forcedPack: 'finance_ops',
    });
    expect(decision.pack.packId).toBe('finance_ops');
    expect(decision.source).toBe('forced');
  });

  it('flags requiresOverride when the requested tier exceeds the pack ceiling', () => {
    const decision = dispatchDomainPack({
      taskType: 'medical_review',
      riskTier: 'R3_high',
    });
    expect(decision.requiresOverride).toBe(true);
  });

  it('does not flag when the tier is within the pack ceiling', () => {
    const decision = dispatchDomainPack({
      taskType: 'agent_orchestration',
      riskTier: 'R2_moderate',
    });
    expect(decision.requiresOverride).toBe(false);
  });

  it('exports the full pack registry (v3 base + v4 Sentra/Amaru = 12 packs)', () => {
    expect(Object.keys(DOMAIN_PACKS)).toHaveLength(12);
  });
});

describe('operator approval gate', () => {
  it('default-deny provider denies any tier', async () => {
    const r = await requestApproval(
      { receiptId: 'rcpt-1', tier: 'R3_high', summary: 'wire transfer' },
      DEFAULT_DENY_PROVIDER,
    );
    expect(r.decision).toBe('denied');
    expect(r.approverId).toBe('system_auto_deny');
  });

  it('auto-grant test provider grants and records the approver', async () => {
    const r = await requestApproval(
      { receiptId: 'rcpt-2', tier: 'R3_high', summary: 'doc release' },
      makeAutoGrantProvider('alice@szl-holdings'),
    );
    expect(r.decision).toBe('granted');
    expect(r.approverId).toBe('alice@szl-holdings');
  });
});

describe('evidence pack contract', () => {
  it('builds a deeply-frozen evidence pack', () => {
    const p = buildEvidencePack({
      evidencePackId: 'ep-1',
      sourceIds: ['src-a', 'src-b'],
      locators: ['s3://bucket/key'],
      proofRouteId: 'PRF_CLAIM_BOUND_RESEARCH',
      receiptId: 'rcpt-1',
      traceId: 'trace-1',
      riskTier: 'R2_moderate',
    });
    expect(() => {
      // @ts-expect-error — runtime check
      p.sourceIds.push('src-c');
    }).toThrow();
  });

  it('flags missing-provenance fields', () => {
    const p = buildEvidencePack({
      evidencePackId: 'ep-1',
      sourceIds: [],
      locators: [],
      proofRouteId: 'PRF_OPERATIONAL_ACTION',
      receiptId: '',
      traceId: '',
      riskTier: 'R3_high',
    });
    expect(validateEvidencePack(p).sort()).toEqual([
      'missing_locators',
      'missing_receipt_id',
      'missing_sources',
      'missing_trace_id',
    ]);
  });

  it('flags a missing evidence pack id', () => {
    const p = buildEvidencePack({
      evidencePackId: '',
      sourceIds: ['src-a'],
      locators: ['s3://bucket/key'],
      proofRouteId: 'PRF_CLAIM_BOUND_RESEARCH',
      receiptId: 'rcpt-1',
      traceId: 'trace-1',
      riskTier: 'R2_moderate',
    });
    expect(validateEvidencePack(p)).toContain('missing_evidence_pack_id');
  });

  it('flags an unknown proof_route_id at runtime', () => {
    const p = buildEvidencePack({
      evidencePackId: 'ep-1',
      sourceIds: ['src-a'],
      locators: ['s3://bucket/key'],
      // simulate an untyped caller that smuggles in a bad route id
      proofRouteId: 'PRF_NOT_REAL' as never,
      receiptId: 'rcpt-1',
      traceId: 'trace-1',
      riskTier: 'R2_moderate',
    });
    expect(validateEvidencePack(p)).toContain('invalid_proof_route_id');
  });

  it('rejects prototype-chain keys (no `in`-operator bypass for route_id or risk_tier)', () => {
    for (const proto of ['toString', 'constructor', '__proto__', 'hasOwnProperty']) {
      const p1 = buildEvidencePack({
        evidencePackId: 'ep-1',
        sourceIds: ['src-a'],
        locators: ['s3://bucket/key'],
        proofRouteId: proto as never,
        receiptId: 'rcpt-1',
        traceId: 'trace-1',
        riskTier: 'R2_moderate',
      });
      expect(validateEvidencePack(p1)).toContain('invalid_proof_route_id');

      const p2 = buildEvidencePack({
        evidencePackId: 'ep-1',
        sourceIds: ['src-a'],
        locators: ['s3://bucket/key'],
        proofRouteId: 'PRF_OPERATIONAL_ACTION',
        receiptId: 'rcpt-1',
        traceId: 'trace-1',
        riskTier: proto as never,
      });
      expect(validateEvidencePack(p2)).toContain('invalid_risk_tier');
    }
  });

  it('flags an unknown risk_tier at runtime', () => {
    const p = buildEvidencePack({
      evidencePackId: 'ep-1',
      sourceIds: ['src-a'],
      locators: ['s3://bucket/key'],
      proofRouteId: 'PRF_CLAIM_BOUND_RESEARCH',
      receiptId: 'rcpt-1',
      traceId: 'trace-1',
      riskTier: 'R5_apocalyptic' as never,
    });
    expect(validateEvidencePack(p)).toContain('invalid_risk_tier');
  });
});

describe('operational modes', () => {
  it('advisory and replay_audit forbid execution', () => {
    expect(OPERATIONAL_MODES.advisory.executionAllowed).toBe(false);
    expect(OPERATIONAL_MODES.replay_audit.executionAllowed).toBe(false);
  });

  it('approval_gated only auto-executes R1', () => {
    expect(isAutoExecutionAllowed('approval_gated', 'R1_low')).toBe(true);
    expect(isAutoExecutionAllowed('approval_gated', 'R2_moderate')).toBe(false);
    expect(isAutoExecutionAllowed('approval_gated', 'R3_high')).toBe(false);
  });

  it('semi_autonomous auto-executes R1 and R2 only', () => {
    expect(isAutoExecutionAllowed('semi_autonomous', 'R1_low')).toBe(true);
    expect(isAutoExecutionAllowed('semi_autonomous', 'R2_moderate')).toBe(true);
    expect(isAutoExecutionAllowed('semi_autonomous', 'R3_high')).toBe(false);
    expect(isAutoExecutionAllowed('semi_autonomous', 'R4_critical')).toBe(false);
  });

  it('distillation_capture flags trace capture', () => {
    expect(OPERATIONAL_MODES.distillation_capture.captureDistillationTraces).toBe(true);
    expect(OPERATIONAL_MODES.approval_gated.captureDistillationTraces).toBe(false);
  });
});
