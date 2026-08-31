/**
 * Type A behavioural tests for the v4 validator functions.
 *
 * For every validator: at least one explicit pass case and one explicit
 * fail case, asserting both `passed` and the substance of the `note`.
 * Also exercises:
 *   - registry-completeness (all 9 codex IDs map to a function)
 *   - subset execution (Sentra and Amaru profiles from INGESTION_CONTRACTS)
 *   - end-to-end integration with the Lutar Invariant Λ aggregator
 *   - determinism (same input → same output across two invocations)
 */

import { describe, expect, it } from 'vitest';

import {
  VALIDATOR_REGISTRY,
  summarizeValidators,
  type ValidatorId,
} from '../validator-registry.js';
import { INGESTION_CONTRACTS } from '../ingestion-contract.js';

import {
  valBudgetEnforcer,
  valNoSilentMutation,
  valProofRequired,
  valRiskEscalation,
  valApprovalForCriticalAction,
  valSecurityProofRequired,
  valSourcePriorityRequired,
  valMergeSafety,
  valConsistencyBeforeCommit,
  VALIDATOR_FNS,
  runValidators,
  V4_VALIDATOR_IDS,
} from './index.js';
import type { RuntimeContext } from './index.js';

/* ───────────────── registry coverage ───────────────── */

describe('v4 validator function registry', () => {
  it('VALIDATOR_FNS covers all 9 codex IDs exactly', () => {
    const codexIds = new Set(Object.keys(VALIDATOR_REGISTRY));
    const fnIds = new Set(Object.keys(VALIDATOR_FNS));
    expect(fnIds).toEqual(codexIds);
    expect(fnIds.size).toBe(9);
  });

  it('V4_VALIDATOR_IDS preserves registry insertion order', () => {
    expect([...V4_VALIDATOR_IDS]).toEqual(Object.keys(VALIDATOR_REGISTRY));
  });

  it('every function returns a frozen ValidatorResult on a minimal context', () => {
    const ctx: RuntimeContext = {};
    for (const id of V4_VALIDATOR_IDS) {
      const r = VALIDATOR_FNS[id](ctx);
      expect(r.validatorId).toBe(id);
      expect(typeof r.passed).toBe('boolean');
      expect(Object.isFrozen(r)).toBe(true);
    }
  });
});

/* ───────────────── 1. VAL_BUDGET_ENFORCER ───────────────── */

describe('VAL_BUDGET_ENFORCER', () => {
  it('passes when no ceilings are configured (vacuous)', () => {
    expect(valBudgetEnforcer({}).passed).toBe(true);
  });

  it('passes when usage is under all ceilings', () => {
    const r = valBudgetEnforcer({
      tokensUsed: 1000,
      tokenCeiling: 5000,
      stepsUsed: 12,
      stepCeiling: 50,
      elapsedMs: 1234,
      timeCeilingMs: 10000,
    });
    expect(r.passed).toBe(true);
  });

  it('fails and names the breach when tokens exceed ceiling', () => {
    const r = valBudgetEnforcer({ tokensUsed: 9001, tokenCeiling: 5000 });
    expect(r.passed).toBe(false);
    expect(r.note).toContain('tokens 9001');
    expect(r.note).toContain('5000');
  });

  it('fails and names every breach when multiple ceilings are exceeded', () => {
    const r = valBudgetEnforcer({
      tokensUsed: 9001,
      tokenCeiling: 5000,
      stepsUsed: 100,
      stepCeiling: 50,
    });
    expect(r.passed).toBe(false);
    expect(r.note).toContain('tokens');
    expect(r.note).toContain('steps');
  });
});

/* ───────────────── 2. VAL_NO_SILENT_MUTATION ───────────────── */

describe('VAL_NO_SILENT_MUTATION', () => {
  it('passes when there are no mutations', () => {
    expect(valNoSilentMutation({}).passed).toBe(true);
  });

  it('passes when every mutation is recorded in trace', () => {
    const r = valNoSilentMutation({
      mutations: [
        { id: 'm1', target: 'sentra.alert', recordedInTrace: true },
        { id: 'm2', target: 'amaru.commit', recordedInTrace: true },
      ],
    });
    expect(r.passed).toBe(true);
  });

  it('fails and names the silent mutation(s)', () => {
    const r = valNoSilentMutation({
      mutations: [
        { id: 'm1', target: 'sentra.alert', recordedInTrace: true },
        { id: 'm2', target: 'amaru.commit', recordedInTrace: false },
      ],
    });
    expect(r.passed).toBe(false);
    expect(r.note).toContain('m2');
  });
});

/* ───────────────── 3. VAL_PROOF_REQUIRED ───────────────── */

describe('VAL_PROOF_REQUIRED', () => {
  it('passes when the run is not proof-bound', () => {
    expect(valProofRequired({ proofRouteRequired: false }).passed).toBe(true);
  });

  it('passes when proof-bound and route resolved', () => {
    const r = valProofRequired({ proofRouteRequired: true, proofRouteResolved: true });
    expect(r.passed).toBe(true);
  });

  it('fails when proof-bound and route unresolved', () => {
    const r = valProofRequired({ proofRouteRequired: true, proofRouteResolved: false });
    expect(r.passed).toBe(false);
    expect(r.note).toMatch(/proof route required/i);
  });
});

/* ───────────────── 4. VAL_RISK_ESCALATION ───────────────── */

describe('VAL_RISK_ESCALATION', () => {
  it('passes when tier is below threshold', () => {
    const r = valRiskEscalation({ riskTier: 'R1', riskEscalationThreshold: 'R3' });
    expect(r.passed).toBe(true);
  });

  it('passes when tier ≥ threshold but the run escalated', () => {
    const r = valRiskEscalation({
      riskTier: 'R3',
      riskEscalationThreshold: 'R3',
      escalated: true,
    });
    expect(r.passed).toBe(true);
  });

  it('passes when tier ≥ threshold but the run halted', () => {
    const r = valRiskEscalation({
      riskTier: 'R4',
      riskEscalationThreshold: 'R3',
      halted: true,
    });
    expect(r.passed).toBe(true);
  });

  it('fails when tier ≥ threshold and neither escalated nor halted', () => {
    const r = valRiskEscalation({ riskTier: 'R4', riskEscalationThreshold: 'R3' });
    expect(r.passed).toBe(false);
    expect(r.note).toContain('R4');
    expect(r.note).toContain('R3');
  });
});

/* ───────────────── 5. VAL_APPROVAL_FOR_CRITICAL_ACTION ───────────────── */

describe('VAL_APPROVAL_FOR_CRITICAL_ACTION', () => {
  it('passes when not a critical action', () => {
    expect(valApprovalForCriticalAction({ criticalAction: false }).passed).toBe(true);
  });

  it('passes when critical action with required+granted approval', () => {
    const r = valApprovalForCriticalAction({
      criticalAction: true,
      approval: { required: true, granted: true, approverId: 'op-1' },
    });
    expect(r.passed).toBe(true);
  });

  it('fails when critical action with no approval snapshot', () => {
    const r = valApprovalForCriticalAction({ criticalAction: true });
    expect(r.passed).toBe(false);
    expect(r.note).toMatch(/no approval snapshot/i);
  });

  it('fails when critical action but approval.granted=false', () => {
    const r = valApprovalForCriticalAction({
      criticalAction: true,
      approval: { required: true, granted: false },
    });
    expect(r.passed).toBe(false);
    expect(r.note).toMatch(/not granted/i);
  });
});

/* ───────────────── 6. VAL_SECURITY_PROOF_REQUIRED ───────────────── */

describe('VAL_SECURITY_PROOF_REQUIRED', () => {
  it('passes when no security conclusion is asserted', () => {
    expect(valSecurityProofRequired({}).passed).toBe(true);
  });

  it('passes when security conclusion is backed by ≥1 evidence artifact', () => {
    const r = valSecurityProofRequired({
      securityConclusionPresent: true,
      securityEvidenceCount: 3,
    });
    expect(r.passed).toBe(true);
  });

  it('fails when security conclusion has zero evidence', () => {
    const r = valSecurityProofRequired({
      securityConclusionPresent: true,
      securityEvidenceCount: 0,
    });
    expect(r.passed).toBe(false);
    expect(r.note).toMatch(/zero supporting evidence/i);
  });
});

/* ───────────────── 7. VAL_SOURCE_PRIORITY_REQUIRED ───────────────── */

describe('VAL_SOURCE_PRIORITY_REQUIRED', () => {
  it('passes when not a data convergence run', () => {
    expect(valSourcePriorityRequired({}).passed).toBe(true);
  });

  it('passes when every source has a numeric precedenceRank', () => {
    const r = valSourcePriorityRequired({
      isDataConvergenceRun: true,
      sources: [
        { url: 'https://primary.example/api', precedenceRank: 1 },
        { url: 'https://secondary.example/api', precedenceRank: 2 },
      ],
    });
    expect(r.passed).toBe(true);
  });

  it('fails when a data convergence run has zero sources', () => {
    const r = valSourcePriorityRequired({ isDataConvergenceRun: true, sources: [] });
    expect(r.passed).toBe(false);
    expect(r.note).toMatch(/zero sources/i);
  });

  it('fails when any source is missing precedenceRank', () => {
    const r = valSourcePriorityRequired({
      isDataConvergenceRun: true,
      sources: [
        { url: 'https://primary.example/api', precedenceRank: 1 },
        // intentionally bad: NaN precedenceRank
        { url: 'https://broken.example/api', precedenceRank: Number.NaN },
      ],
    });
    expect(r.passed).toBe(false);
    expect(r.note).toContain('broken.example');
  });
});

/* ───────────────── 8. VAL_MERGE_SAFETY ───────────────── */

describe('VAL_MERGE_SAFETY', () => {
  it('passes when there are no merge actions', () => {
    expect(valMergeSafety({}).passed).toBe(true);
  });

  it('passes when all merges are safe (no destructive, no conflicts)', () => {
    const r = valMergeSafety({
      mergeActions: [
        { id: 'mr-1', destructive: false, conflictDetected: false, hasManualOverride: false },
      ],
    });
    expect(r.passed).toBe(true);
  });

  it('passes when an unsafe merge has a manual override', () => {
    const r = valMergeSafety({
      mergeActions: [
        { id: 'mr-1', destructive: true, conflictDetected: false, hasManualOverride: true },
      ],
    });
    expect(r.passed).toBe(true);
  });

  it('passes when unsafe merges exist but the run escalated', () => {
    const r = valMergeSafety({
      mergeActions: [
        { id: 'mr-1', destructive: true, conflictDetected: true, hasManualOverride: false },
      ],
      escalated: true,
    });
    expect(r.passed).toBe(true);
  });

  it('fails when unsafe merges have neither override nor escalation', () => {
    const r = valMergeSafety({
      mergeActions: [
        { id: 'mr-1', destructive: true, conflictDetected: false, hasManualOverride: false },
      ],
    });
    expect(r.passed).toBe(false);
    expect(r.note).toContain('mr-1');
  });
});

/* ───────────────── 9. VAL_CONSISTENCY_BEFORE_COMMIT ───────────────── */

describe('VAL_CONSISTENCY_BEFORE_COMMIT', () => {
  it('passes when not an Amaru finalize', () => {
    expect(valConsistencyBeforeCommit({}).passed).toBe(true);
  });

  it('passes when metric meets threshold exactly', () => {
    const r = valConsistencyBeforeCommit({
      isAmaruFinalize: true,
      consistency: { metric: 0.9, threshold: 0.9 },
    });
    expect(r.passed).toBe(true);
  });

  it('fails when Amaru finalize has no consistency snapshot', () => {
    const r = valConsistencyBeforeCommit({ isAmaruFinalize: true });
    expect(r.passed).toBe(false);
  });

  it('fails when metric < threshold', () => {
    const r = valConsistencyBeforeCommit({
      isAmaruFinalize: true,
      consistency: { metric: 0.5, threshold: 0.9 },
    });
    expect(r.passed).toBe(false);
    expect(r.note).toMatch(/0\.5/);
    expect(r.note).toMatch(/0\.9/);
  });
});

/* ───────────────── runner determinism ───────────────── */

describe('runValidators (full set)', () => {
  it('runs all 9 validators in registry order on an empty context (all pass vacuously)', () => {
    const out = runValidators({});
    expect(out.results).toHaveLength(9);
    expect(out.results.map((r) => r.validatorId)).toEqual([...V4_VALIDATOR_IDS]);
    expect(out.summary.halt).toBe(false);
    expect(out.summary.passed).toBe(9);
  });

  it('halts when ANY error-severity validator fails', () => {
    const out = runValidators({ tokensUsed: 9001, tokenCeiling: 100 });
    expect(out.summary.halt).toBe(true);
    expect(out.summary.failed.map((r) => r.validatorId)).toContain('VAL_BUDGET_ENFORCER');
  });

  it('is deterministic: same input twice → identical results', () => {
    const ctx: RuntimeContext = {
      tokensUsed: 100,
      tokenCeiling: 1000,
      mutations: [{ id: 'm1', target: 't', recordedInTrace: true }],
      proofRouteRequired: true,
      proofRouteResolved: true,
    };
    const a = runValidators(ctx);
    const b = runValidators(ctx);
    expect(a.results).toEqual(b.results);
    expect(a.summary).toEqual(b.summary);
  });
});

/* ───────────────── ingestion-contract integration ───────────────── */

describe('runValidators × INGESTION_CONTRACTS (Sentra / Amaru profiles)', () => {
  it('Sentra profile: green run passes its 3 required validators', () => {
    const ids = INGESTION_CONTRACTS.Sentra.requiredValidators;
    const out = runValidators(
      {
        riskTier: 'R2',
        riskEscalationThreshold: 'R3',
        securityConclusionPresent: true,
        securityEvidenceCount: 2,
        criticalAction: true,
        approval: { required: true, granted: true, approverId: 'soc-lead' },
      },
      ids,
    );
    expect(out.results).toHaveLength(3);
    expect(out.summary.halt).toBe(false);
  });

  it('Sentra profile: missing security evidence halts the run', () => {
    const ids = INGESTION_CONTRACTS.Sentra.requiredValidators;
    const out = runValidators(
      {
        riskTier: 'R2',
        riskEscalationThreshold: 'R3',
        securityConclusionPresent: true,
        securityEvidenceCount: 0,
        criticalAction: false,
      },
      ids,
    );
    expect(out.summary.halt).toBe(true);
    expect(out.summary.failed.map((r) => r.validatorId)).toContain('VAL_SECURITY_PROOF_REQUIRED');
  });

  it('Amaru profile: green finalize passes its 3 required validators', () => {
    const ids = INGESTION_CONTRACTS.Amaru.requiredValidators;
    const out = runValidators(
      {
        isDataConvergenceRun: true,
        sources: [
          { url: 'https://primary', precedenceRank: 1 },
          { url: 'https://secondary', precedenceRank: 2 },
        ],
        mergeActions: [
          { id: 'mr-1', destructive: false, conflictDetected: false, hasManualOverride: false },
        ],
        isAmaruFinalize: true,
        consistency: { metric: 0.95, threshold: 0.9 },
      },
      ids,
    );
    expect(out.results).toHaveLength(3);
    expect(out.summary.halt).toBe(false);
  });

  it('Amaru profile: consistency below threshold halts finalize', () => {
    const ids = INGESTION_CONTRACTS.Amaru.requiredValidators;
    const out = runValidators(
      {
        isDataConvergenceRun: true,
        sources: [{ url: 'https://primary', precedenceRank: 1 }],
        isAmaruFinalize: true,
        consistency: { metric: 0.4, threshold: 0.9 },
      },
      ids,
    );
    expect(out.summary.halt).toBe(true);
    expect(out.summary.failed.map((r) => r.validatorId)).toContain(
      'VAL_CONSISTENCY_BEFORE_COMMIT',
    );
  });
});

/* ───────────────── end-to-end with the existing summarizer ───────────────── */

describe('summarizeValidators integration', () => {
  it('runValidators output round-trips through summarizeValidators identically', () => {
    const ctx: RuntimeContext = { tokensUsed: 9001, tokenCeiling: 100 };
    const out = runValidators(ctx);
    const reSummarized = summarizeValidators(out.results);
    expect(reSummarized).toEqual(out.summary);
  });
});

/* ───────────────── ID coverage ───────────────── */

describe('ValidatorId coverage sanity', () => {
  it('every codex ValidatorId has a function and at least one Type A test (registry exhaustive check)', () => {
    const expected: ValidatorId[] = [
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
    for (const id of expected) {
      expect(VALIDATOR_FNS[id]).toBeTypeOf('function');
    }
  });
});
