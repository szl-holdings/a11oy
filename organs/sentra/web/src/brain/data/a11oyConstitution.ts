// doctrine-scanner-exempt: legacy live-product surface; rename tracked as separate engineering debt — see scripts/check-doctrine-v6.mjs header.
/**
 * A11oy Constitution Adapter for ROSIE
 *
 * Derives ROSIE's guardrail clauses and playbooks directly from A11oy's
 * exported seed constants in artifacts/a11oy/src/data/mythosDoctrine.ts:
 *   - CODE_BEHAVIOR_DIMS / CODE_BEHAVIOR_LABELS  — governance dimensions
 *   - RH_WATCHDOG_RULES                          — reward-hacking watchdog rules
 *   - ConstitutionClause, DOCTRINE_VERSION        — schema and version
 *
 * The six clauses below map A11oy's CODE_BEHAVIOR_DIMS to optimizer-executable
 * guardrail checks, grounding ROSIE's governance in A11oy's actual exported
 * data rather than ROSIE-local prose.
 *
 * At runtime, useA11oyConstitution() attempts to load the active constitution
 * from A11oy's doctrine API (/a11oy/api/doctrine/constitution/active) and
 * uses these A11oy-derived seeds as the documented fallback.
 */

import type { ConstitutionClause } from '../../../../a11oy/src/data/mythosDoctrine';
import {
  DOCTRINE_VERSION,
  CODE_BEHAVIOR_LABELS,
  RH_WATCHDOG_RULES,
} from '../../../../a11oy/src/data/mythosDoctrine';

export { DOCTRINE_VERSION as CONSTITUTION_VERSION };

/**
 * The kind of executable check used to evaluate this clause in the solver.
 * Each CheckKind maps to a concrete evaluation branch in isingOptimizer.ts.
 */
export type GuardrailCheckKind =
  | 'hard-violation-threshold'  // fail if any hard constraint violationScore > 0.5
  | 'constraint-transparency'   // fail if constraintResults doesn't include all constraints
  | 'recommendation-only'       // always passes — ROSIE never auto-executes decisions
  | 'proof-ledger-required'     // always passes — proof entry guaranteed by architecture
  | 'gini-fairness'             // fail if Gini coefficient of assignments > 0.6
  | 'coverage-diversity'        // fail if any single value takes > 70% of assignments
  | 'unmapped-fail-closed';     // sentinel for clauses returned by A11oy that ROSIE has
                                // no executable mapping for — ALWAYS fails so the brain
                                // never silently passes governance for unknown rules.

export interface RosieGuardrailClause extends ConstitutionClause {
  binding: 'inviolable' | 'strong' | 'default';
  /** Human-readable optimizer implication. */
  optimizerImplication: string;
  /**
   * Maps to an executable evaluation branch in isingOptimizer.ts.
   * Every clause must have a corresponding concrete check — no clause is display-only.
   */
  checkKind: GuardrailCheckKind;
  /** Optional threshold parameter for numeric checks. */
  checkParam?: number;
}

/**
 * ROSIE's seeded A11oy constitution clauses.
 *
 * Each clause is grounded in an A11oy exported constant:
 *   C1 ← CODE_BEHAVIOR_LABELS.rewardHackingResistance + RH_WATCHDOG_RULES (all 8)
 *   C2 ← CODE_BEHAVIOR_LABELS.specAdherence (spec must be fully observable)
 *   C3 ← CODE_BEHAVIOR_LABELS.oversightFriendliness (human retains final authority)
 *   C4 ← CODE_BEHAVIOR_LABELS.sandboxRespect (auditable boundary enforcement)
 *   C5 ← CODE_BEHAVIOR_LABELS.selfModRestraint (fairness / welfare)
 *   C6 ← CODE_BEHAVIOR_LABELS.reversibility (preserve operator optionality)
 */
export const ACTIVE_CONSTITUTION: RosieGuardrailClause[] = [
  {
    id: 'C1.SAFETY',
    category: 'safety',
    text: `${CODE_BEHAVIOR_LABELS.rewardHackingResistance}: allocation must resist proxy-metric exploitation and reward-hacking. `
      + `Covers A11oy watchdog rules ${RH_WATCHDOG_RULES.map(r => r.id).join(', ')}.`,
    binding: 'inviolable',
    optimizerImplication: 'Any hard constraint with violationScore > 0.5 triggers a C1 guardrail block.',
    checkKind: 'hard-violation-threshold',
    checkParam: 0.5,
  },
  {
    id: 'C2.HONESTY',
    category: 'honesty',
    text: `${CODE_BEHAVIOR_LABELS.specAdherence}: ROSIE must surface every constraint considered — including `
      + 'those that were binding at the optimum — with full violation scores.',
    binding: 'inviolable',
    optimizerImplication: 'Solve must include every input constraint in constraintResults; missing constraints trigger C2 failure.',
    checkKind: 'constraint-transparency',
  },
  {
    id: 'C3.AUTONOMY',
    category: 'autonomy',
    text: `${CODE_BEHAVIOR_LABELS.oversightFriendliness}: human operators retain final authority over all allocation `
      + 'decisions. ROSIE produces recommendations only — execution requires explicit operator confirmation.',
    binding: 'strong',
    optimizerImplication: 'Always passes: ROSIE is a recommendation engine; it never auto-executes decisions.',
    checkKind: 'recommendation-only',
  },
  {
    id: 'C4.OVERSIGHT',
    category: 'oversight',
    text: `${CODE_BEHAVIOR_LABELS.sandboxRespect}: all optimization runs must produce an auditable proof-ledger entry `
      + 'with a SHA-256 inputs hash and the active constitution version.',
    binding: 'strong',
    optimizerImplication: 'Always passes: architecture guarantees proof entry is written before result is returned.',
    checkKind: 'proof-ledger-required',
  },
  {
    id: 'C5.WELFARE',
    category: 'welfare',
    text: `${CODE_BEHAVIOR_LABELS.selfModRestraint}: optimization must not systematically disadvantage any resource `
      + 'class. Fairness is measured by Gini coefficient of the final assignment distribution.',
    binding: 'default',
    optimizerImplication: 'Triggers when Gini coefficient of assignment value frequencies exceeds 0.6.',
    checkKind: 'gini-fairness',
    checkParam: 0.6,
  },
  {
    id: 'C6.REVERSIBILITY',
    category: 'safety',
    text: `${CODE_BEHAVIOR_LABELS.reversibility}: preferred solutions are those that preserve the most operator `
      + 'optionality. Solutions must not over-commit the majority of variables to a single domain value.',
    binding: 'strong',
    optimizerImplication: 'Triggers when any single domain value is assigned to more than 70% of variables.',
    checkKind: 'coverage-diversity',
    checkParam: 0.7,
  },
];

/**
 * ROSIE playbooks — derived from A11oy's RH_WATCHDOG_RULES and CODE_BEHAVIOR_DIMS.
 * Each playbook references the A11oy rule or dimension that triggers it.
 */
export const ACTIVE_PLAYBOOKS = [
  {
    id: 'PB-RISK-GATE',
    name: 'Risk Gate',
    trigger: `A11oy ${RH_WATCHDOG_RULES[0].id} (${RH_WATCHDOG_RULES[0].name}): proxy-metric score > 0.3 or hard constraint block`,
    action: 'Escalate to operator; block auto-presentation of result.',
  },
  {
    id: 'PB-FAIRNESS-ALERT',
    name: 'Fairness Alert',
    trigger: 'C5.WELFARE: Gini coefficient > 0.6 in optimal solution',
    action: 'Surface fairness warning; present alternative with highest equity score.',
  },
  {
    id: 'PB-CONSTRAINT-CONFLICT',
    name: 'Constraint Conflict',
    trigger: `A11oy ${RH_WATCHDOG_RULES[6].id} (${RH_WATCHDOG_RULES[6].name}): two or more hard constraints simultaneously unsatisfiable`,
    action: 'Surface conflict report; ask operator to relax one constraint.',
  },
  {
    id: 'PB-REVERSIBILITY-ALERT',
    name: 'Reversibility Alert',
    trigger: `C6.REVERSIBILITY: any domain value captures > 70% of assignments`,
    action: 'Flag concentration risk; recommend alternative with greater coverage diversity.',
  },
];
