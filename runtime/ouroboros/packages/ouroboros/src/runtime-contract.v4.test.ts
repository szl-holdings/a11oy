import { describe, expect, it } from 'vitest';

import {
  CYCLE_ID_V4_ALIASES,
  DOMAIN_PACKS,
  INGESTION_CONTRACTS,
  INNOVATION_ENGINE_DEFAULT,
  INNOVATION_LOOPS,
  OUTPUT_PATHS,
  PROOF_ROUTES,
  ROUTE_ID_V4_ALIASES,
  TASK_TO_PACK_V4,
  V4_CYCLES,
  VALIDATOR_REGISTRY,
  resolveOutputPath,
  resolveV4ProofRouteId,
  summarizeValidators,
  validateIngestion,
  validateInnovationEngine,
  type DomainPackId,
  type InnovationEngineState,
  type InnovationLoopId,
  type ProofRouteIdV4,
  type RequiredOutput,
  type ValidatorId,
} from './index.js';

describe('v4 validator registry', () => {
  const expectedIds: readonly ValidatorId[] = [
    'VAL_BUDGET_ENFORCER',
    'VAL_NO_SILENT_MUTATION',
    'VAL_PROOF_REQUIRED',
    'VAL_RISK_ESCALATION',
    'VAL_APPROVAL_FOR_CRITICAL_ACTION',
    'VAL_SECURITY_PROOF_REQUIRED',
    'VAL_SOURCE_PRIORITY_REQUIRED',
    'VAL_MERGE_SAFETY',
    'VAL_CONSISTENCY_BEFORE_COMMIT',
  ];

  it('registry has exactly 9 entries (no silent additions or drops)', () => {
    expect(Object.keys(VALIDATOR_REGISTRY)).toHaveLength(9);
    expect(new Set(Object.keys(VALIDATOR_REGISTRY))).toEqual(new Set(expectedIds));
  });

  it('every registry entry has matching id, error severity, and non-empty rule', () => {
    for (const id of expectedIds) {
      const spec = VALIDATOR_REGISTRY[id];
      expect(spec.validatorId).toBe(id);
      expect(spec.severity).toBe('error');
      expect(spec.rule.length).toBeGreaterThan(10);
    }
  });

  it('summarizes results: any failed error-severity validator halts', () => {
    const summary = summarizeValidators([
      { validatorId: 'VAL_BUDGET_ENFORCER', passed: true },
      { validatorId: 'VAL_PROOF_REQUIRED', passed: false, note: 'missing proof' },
      { validatorId: 'VAL_RISK_ESCALATION', passed: true },
    ]);
    expect(summary.total).toBe(3);
    expect(summary.passed).toBe(2);
    expect(summary.failed).toHaveLength(1);
    expect(summary.failed[0].validatorId).toBe('VAL_PROOF_REQUIRED');
    expect(summary.halt).toBe(true);
  });

  it('all-passing summary does not halt', () => {
    const summary = summarizeValidators([
      { validatorId: 'VAL_BUDGET_ENFORCER', passed: true },
      { validatorId: 'VAL_NO_SILENT_MUTATION', passed: true },
    ]);
    expect(summary.halt).toBe(false);
    expect(summary.failed).toHaveLength(0);
  });
});

describe('v4 ingestion contracts (Sentra / Amaru)', () => {
  it('exposes exactly two targets: Sentra and Amaru', () => {
    expect(new Set(Object.keys(INGESTION_CONTRACTS))).toEqual(
      new Set(['Sentra', 'Amaru']),
    );
  });

  it('Sentra contract matches v4 JSON exactly', () => {
    const c = INGESTION_CONTRACTS.Sentra;
    expect(c.target).toBe('Sentra');
    expect(c.poweredBy).toBe('A11oy_core');
    expect(c.loopProfile).toBe('security_recursive_review');
    expect([...c.requiredValidators]).toEqual([
      'VAL_RISK_ESCALATION',
      'VAL_SECURITY_PROOF_REQUIRED',
      'VAL_APPROVAL_FOR_CRITICAL_ACTION',
    ]);
    expect([...c.requiredOutputs]).toEqual([
      'trace',
      'decision_receipt',
      'risk_summary',
      'evidence_pack',
    ]);
    expect([...c.ingestTypes]).toEqual([
      'alerts',
      'logs',
      'security_events',
      'threat_hypotheses',
      'attack_paths',
      'access_reviews',
    ]);
  });

  it('Amaru contract matches v4 JSON exactly', () => {
    const c = INGESTION_CONTRACTS.Amaru;
    expect(c.target).toBe('Amaru');
    expect(c.loopProfile).toBe('convergent_data_runtime');
    expect([...c.requiredValidators]).toEqual([
      'VAL_SOURCE_PRIORITY_REQUIRED',
      'VAL_MERGE_SAFETY',
      'VAL_CONSISTENCY_BEFORE_COMMIT',
    ]);
    expect([...c.requiredOutputs]).toEqual([
      'trace',
      'decision_receipt',
      'consistency_report',
      'delta_log',
    ]);
    expect([...c.ingestTypes]).toEqual([
      'records',
      'deltas',
      'conflicts',
      'schema_variants',
      'sync_jobs',
      'merge_candidates',
    ]);
  });

  it('every required validator on every contract is present in VALIDATOR_REGISTRY', () => {
    for (const c of Object.values(INGESTION_CONTRACTS)) {
      for (const v of c.requiredValidators) {
        expect(VALIDATOR_REGISTRY[v]).toBeDefined();
      }
    }
  });

  it('rejects unknown targets', () => {
    const errs = validateIngestion({
      target: 'Helios',
      ingestType: 'whatever',
      presentOutputs: new Set(),
      passedValidators: new Set(),
    });
    expect(errs).toContain('unknown_target');
  });

  it('passes when all validators and outputs are present', () => {
    const errs = validateIngestion({
      target: 'Sentra',
      ingestType: 'alerts',
      presentOutputs: new Set<RequiredOutput>([
        'trace',
        'decision_receipt',
        'risk_summary',
        'evidence_pack',
      ]),
      passedValidators: new Set<ValidatorId>([
        'VAL_RISK_ESCALATION',
        'VAL_SECURITY_PROOF_REQUIRED',
        'VAL_APPROVAL_FOR_CRITICAL_ACTION',
      ]),
    });
    expect(errs).toEqual([]);
  });

  it('flags missing required outputs and validators for Amaru', () => {
    const errs = validateIngestion({
      target: 'Amaru',
      ingestType: 'records',
      presentOutputs: new Set<RequiredOutput>(['trace']),
      passedValidators: new Set<ValidatorId>([]),
    });
    expect(errs).toContain('missing_required_output');
    expect(errs).toContain('missing_required_validator');
  });

  it('rejects unsupported ingest types', () => {
    const errs = validateIngestion({
      target: 'Sentra',
      ingestType: 'records',
      presentOutputs: new Set<RequiredOutput>([
        'trace',
        'decision_receipt',
        'risk_summary',
        'evidence_pack',
      ]),
      passedValidators: new Set<ValidatorId>([
        'VAL_RISK_ESCALATION',
        'VAL_SECURITY_PROOF_REQUIRED',
        'VAL_APPROVAL_FOR_CRITICAL_ACTION',
      ]),
    });
    expect(errs).toContain('unsupported_ingest_type');
  });
});

describe('v4 innovation engine', () => {
  const expectedLoops: readonly InnovationLoopId[] = [
    'runtime_feedback_loop',
    'golden_run_regression_loop',
    'receipt_quality_loop',
    'security_review_improvement_loop',
    'data_convergence_improvement_loop',
    'economic_efficiency_loop',
  ];

  it('registry has exactly 6 loops', () => {
    expect(Object.keys(INNOVATION_LOOPS)).toHaveLength(6);
    expect(new Set(Object.keys(INNOVATION_LOOPS))).toEqual(new Set(expectedLoops));
  });

  it('every loop has a source and an output', () => {
    for (const id of expectedLoops) {
      expect(INNOVATION_LOOPS[id].source).toBeDefined();
      expect(INNOVATION_LOOPS[id].output).toBeDefined();
      expect(INNOVATION_LOOPS[id].purpose.length).toBeGreaterThan(10);
    }
  });

  it('default state is enabled with operator feedback binding and trace distillation', () => {
    expect(INNOVATION_ENGINE_DEFAULT.enabled).toBe(true);
    expect(INNOVATION_ENGINE_DEFAULT.operatorFeedbackBinding).toBe(true);
    expect(INNOVATION_ENGINE_DEFAULT.traceDistillationReady).toBe(true);
    expect(INNOVATION_ENGINE_DEFAULT.loops).toHaveLength(6);
  });

  it('validateInnovationEngine returns missing loop ids', () => {
    const partial: InnovationEngineState = {
      enabled: true,
      operatorFeedbackBinding: true,
      traceDistillationReady: true,
      loops: [INNOVATION_LOOPS.runtime_feedback_loop],
    };
    const missing = validateInnovationEngine(partial);
    expect(missing).toContain('golden_run_regression_loop');
    expect(missing).toContain('economic_efficiency_loop');
    expect(missing).not.toContain('runtime_feedback_loop');
  });

  it('validateInnovationEngine on default state returns no missing loops', () => {
    expect(validateInnovationEngine(INNOVATION_ENGINE_DEFAULT)).toEqual([]);
  });
});

describe('v4 output paths', () => {
  it('exposes exactly 8 canonical paths', () => {
    expect(Object.keys(OUTPUT_PATHS)).toHaveLength(8);
  });

  it('every output path matches the v4 JSON exactly', () => {
    expect(OUTPUT_PATHS.traceJsonl).toBe('output/trace.jsonl');
    expect(OUTPUT_PATHS.decisionReceipt).toBe('output/decision_receipt.json');
    expect(OUTPUT_PATHS.proofLedgerJsonl).toBe('output/proof_ledger.jsonl');
    expect(OUTPUT_PATHS.finalStateJson).toBe('output/final_state.json');
    expect(OUTPUT_PATHS.runSummaryJson).toBe('output/run_summary.json');
    expect(OUTPUT_PATHS.goldenRunReportJson).toBe('output/golden_run_report.json');
    expect(OUTPUT_PATHS.sentraRiskSummaryJson).toBe('output/sentra_risk_summary.json');
    expect(OUTPUT_PATHS.amaruConsistencyReportJson).toBe(
      'output/amaru_consistency_report.json',
    );
  });

  it('resolveOutputPath returns canonical path for known key', () => {
    expect(resolveOutputPath('traceJsonl')).toBe('output/trace.jsonl');
  });
});

describe('v4 paris_cadence_cycle (canonical rename)', () => {
  it('V4_CYCLES contains exactly 4 cycles with paris_cadence_cycle as canonical', () => {
    expect(V4_CYCLES).toHaveLength(4);
    const ids = V4_CYCLES.map((c) => c.cycleId).sort();
    expect(ids).toEqual([
      'grolier_schedule_cycle',
      'madrid_almanac_cycle',
      'paris_cadence_cycle',
      'review_cycle',
    ]);
  });

  it('paris_cadence_cycle has interval 3 (unchanged from paris_long_cycle)', () => {
    const paris = V4_CYCLES.find((c) => c.cycleId === 'paris_cadence_cycle');
    expect(paris?.stepInterval).toBe(3);
  });

  it('alias map normalizes both v3 and v4 paris labels to v4 canonical', () => {
    expect(CYCLE_ID_V4_ALIASES['paris_cadence_cycle']).toBe('paris_cadence_cycle');
    expect(CYCLE_ID_V4_ALIASES['paris_long_cycle']).toBe('paris_cadence_cycle');
  });
});

describe('v4 proof-route short labels', () => {
  it('exposes exactly 4 v4 short labels', () => {
    expect(Object.keys(ROUTE_ID_V4_ALIASES)).toHaveLength(4);
    expect(new Set(Object.keys(ROUTE_ID_V4_ALIASES))).toEqual(
      new Set<ProofRouteIdV4>([
        'PRF_RESEARCH',
        'PRF_SECURITY',
        'PRF_DATA_SYNC',
        'PRF_OPERATIONAL',
      ]),
    );
  });

  it('every v4 alias resolves to a known canonical route', () => {
    for (const v3id of Object.values(ROUTE_ID_V4_ALIASES)) {
      expect(PROOF_ROUTES[v3id]).toBeDefined();
    }
  });

  it('resolveV4ProofRouteId resolves both v4 short labels and v3 canonical ids', () => {
    expect(resolveV4ProofRouteId('PRF_RESEARCH')).toBe('PRF_CLAIM_BOUND_RESEARCH');
    expect(resolveV4ProofRouteId('PRF_SECURITY')).toBe('PRF_SECURITY_ACTION');
    expect(resolveV4ProofRouteId('PRF_OPERATIONAL')).toBe('PRF_OPERATIONAL_ACTION');
    expect(resolveV4ProofRouteId('PRF_CLAIM_BOUND_RESEARCH')).toBe(
      'PRF_CLAIM_BOUND_RESEARCH',
    );
    expect(resolveV4ProofRouteId('PRF_NONEXISTENT')).toBeUndefined();
  });
});

describe('v4 domain packs (Sentra_pack / Amaru_pack)', () => {
  it('Sentra_pack and Amaru_pack are registered with evidenceRequired=true', () => {
    expect(DOMAIN_PACKS.Sentra_pack).toBeDefined();
    expect(DOMAIN_PACKS.Sentra_pack.evidenceRequired).toBe(true);
    expect(DOMAIN_PACKS.Amaru_pack).toBeDefined();
    expect(DOMAIN_PACKS.Amaru_pack.evidenceRequired).toBe(true);
  });

  it('TASK_TO_PACK_V4 routes security_review and data_sync to Sentra_pack/Amaru_pack', () => {
    expect(TASK_TO_PACK_V4.security_review).toBe('Sentra_pack');
    expect(TASK_TO_PACK_V4.data_sync).toBe('Amaru_pack');
    expect(TASK_TO_PACK_V4.research).toBe('research_ops');
    expect(TASK_TO_PACK_V4.finance).toBe('finance_ops');
    expect(TASK_TO_PACK_V4.property_ops).toBe('property_ops');
  });

  it('every v4 task type targets a registered pack', () => {
    for (const packId of Object.values(TASK_TO_PACK_V4)) {
      expect(DOMAIN_PACKS[packId as DomainPackId]).toBeDefined();
    }
  });
});
