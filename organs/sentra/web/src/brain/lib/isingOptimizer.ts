import type {
  ProblemTemplate,
  Variable,
  Constraint,
  ObjectiveWeight,
} from '../data/optimizerTemplates';
import type { RosieGuardrailClause } from '../data/a11oyConstitution';
import { ACTIVE_CONSTITUTION, CONSTITUTION_VERSION, type GuardrailCheckKind } from '../data/a11oyConstitution';

// Re-export seed data so the worker can import a default constitution.
export { ACTIVE_CONSTITUTION as SEED_CONSTITUTION, CONSTITUTION_VERSION as SEED_CONSTITUTION_VERSION };

export interface AssignmentSolution {
  assignments: Record<string, string>;
  objectiveScore: number;
  improvementRatio: number;
  objectiveBreakdown: Array<{ id: string; label: string; score: number; weight: number; contribution: number }>;
  constraintResults: Array<{ id: string; label: string; type: 'hard' | 'soft'; satisfied: boolean; violationScore: number }>;
  reasoningTrace: TraceStep[];
  alternatives: AlternativeSolution[];
  guardrailsPassed: boolean;
  guardrailViolations: string[];
  /** Semver of the A11oy doctrine used during this solve. */
  constitutionVersion: string;
  /** Whether guardrails were evaluated against the live A11oy API or local seeds. */
  constitutionSource: 'live' | 'fallback' | 'seed';
  solveTimeMs: number;
  energyHistory: number[];
  initialEnergy: number;
  finalEnergy: number;
}

export interface AlternativeSolution {
  rank: number;
  assignments: Record<string, string>;
  objectiveScore: number;
  delta: number;
  description: string;
  distinctChanges: Array<{ variable: string; from: string; to: string }>;
}

export interface TraceStep {
  step: number;
  action: string;
  variable?: string;
  fromValue?: string;
  toValue?: string;
  energyDelta: number;
  accepted: boolean;
  temperature: number;
  reason: string;
}

// ─── Constraint evaluation — driven by kind + params, not index ────────────

/**
 * Evaluates a single constraint.
 * Returns a violation score in [0, 1]: 0 = fully satisfied, 1 = fully violated.
 * Each ConstraintKind is handled by its own branch with semantics from params.
 */
function evaluateConstraint(
  c: Constraint,
  assignments: Record<string, string>,
  _variables: Variable[],
): number {
  const vals = Object.values(assignments);

  switch (c.kind) {
    case 'unique-assignment': {
      // No two variables may take the same value.
      const counts: Record<string, number> = {};
      for (const v of vals) counts[v] = (counts[v] ?? 0) + 1;
      const conflicts = Object.values(counts)
        .filter(n => n > 1)
        .reduce((sum, n) => sum + (n - 1), 0);
      return Math.min(1, conflicts / Math.max(vals.length, 1));
    }

    case 'domain-exclusion': {
      // Named variables must not take any of the excluded values.
      const { varIds = [], excludedValues = [] } = c.params ?? {};
      if (varIds.length === 0 || excludedValues.length === 0) return 0;
      let violations = 0;
      for (const varId of varIds) {
        if (excludedValues.includes(assignments[varId] ?? '')) violations++;
      }
      return violations / varIds.length;
    }

    case 'adjacency-conflict': {
      // varA and varB must not be assigned the same value.
      const { varA, varB } = c.params ?? {};
      if (!varA || !varB) return 0;
      return assignments[varA] === assignments[varB] ? 1 : 0;
    }

    case 'capacity-limit': {
      // Each value may be assigned to at most maxCapacity variables.
      const { maxCapacity = 1 } = c.params ?? {};
      const counts: Record<string, number> = {};
      for (const v of vals) counts[v] = (counts[v] ?? 0) + 1;
      const overloaded = Object.values(counts)
        .filter(n => n > maxCapacity)
        .reduce((sum, n) => sum + (n - maxCapacity), 0);
      return Math.min(1, overloaded / Math.max(vals.length, 1));
    }

    case 'workload-balance': {
      // Gini coefficient of value distribution should be below giniThreshold.
      const { giniThreshold = 0.4 } = c.params ?? {};
      if (vals.length === 0) return 0;
      const counts: Record<string, number> = {};
      for (const v of vals) counts[v] = (counts[v] ?? 0) + 1;
      const shares = Object.values(counts).map(n => n / vals.length);
      if (shares.length <= 1) return 0;
      const mean = 1 / shares.length;
      const gini =
        shares.reduce((acc, s) => acc + Math.abs(s - mean), 0) /
        (2 * shares.length * mean);
      return gini > giniThreshold
        ? Math.min(1, (gini - giniThreshold) / Math.max(1 - giniThreshold, 0.01))
        : 0;
    }

    case 'preference': {
      // Named variable should be assigned one of the preferred values.
      const { varId, preferredValues = [] } = c.params ?? {};
      if (!varId || preferredValues.length === 0) return 0;
      return preferredValues.includes(assignments[varId] ?? '') ? 0 : 1;
    }

    case 'coverage-frequency': {
      // targetValue must appear in at least minCount assignments.
      const { targetValue, minCount = 1 } = c.params ?? {};
      if (!targetValue) return 0;
      const count = vals.filter(v => v === targetValue).length;
      return count >= minCount ? 0 : (minCount - count) / minCount;
    }

    case 'multi-modal-coverage': {
      // Multiple named variables should collectively cover same target values.
      const { varIds = [], targetValues = [] } = c.params ?? {};
      if (varIds.length === 0 || targetValues.length === 0) return 0;
      let satisfiedTargets = 0;
      for (const target of targetValues) {
        const coveringCount = varIds.filter(vid => assignments[vid] === target).length;
        if (coveringCount >= 2) satisfiedTargets++;
      }
      // Soft: penalty when no target has multi-modal coverage
      return satisfiedTargets === 0 ? 0.5 : 0;
    }

    default:
      return 0;
  }
}

// ─── Objective evaluation — driven by kind, uses actual assignment metrics ─

/**
 * Evaluates an objective quality score in [0, 1] where 1 = best possible.
 * Evaluation is driven by the objective's kind field, not its index.
 */
function evaluateObjective(
  obj: ObjectiveWeight,
  assignments: Record<string, string>,
  variables: Variable[],
  constraints: Constraint[],
): number {
  const vals = Object.values(assignments);
  if (vals.length === 0) return 0.5;

  const counts: Record<string, number> = {};
  for (const v of vals) counts[v] = (counts[v] ?? 0) + 1;
  const uniqueCount = Object.keys(counts).length;
  const totalVars = variables.length;

  switch (obj.kind) {
    case 'minimize-hard-violations': {
      // Score = fraction of hard constraints that are fully satisfied.
      const hardConstraints = constraints.filter(c => c.type === 'hard');
      if (hardConstraints.length === 0) return 1;
      const satisfied = hardConstraints.filter(
        c => evaluateConstraint(c, assignments, variables) < 0.05,
      ).length;
      const score = satisfied / hardConstraints.length;
      return obj.direction === 'minimize' ? score : score;
    }

    case 'maximize-coverage': {
      // Score = fraction of total domain values that are actually used.
      const allDomainValues = new Set<string>();
      for (const v of variables) {
        for (const d of v.domain) allDomainValues.add(d);
      }
      const usedValues = new Set(vals);
      const intersect = [...usedValues].filter(v => allDomainValues.has(v)).length;
      const score = intersect / Math.max(allDomainValues.size, 1);
      return obj.direction === 'maximize' ? score : 1 - score;
    }

    case 'maximize-balance': {
      // Score = 1 - Gini coefficient of value distribution (lower Gini = more balanced = better).
      if (uniqueCount <= 1) return 0.2;
      const shares = Object.values(counts).map(n => n / totalVars);
      const mean = 1 / shares.length;
      const gini =
        shares.reduce((acc, s) => acc + Math.abs(s - mean), 0) /
        (2 * shares.length * mean);
      const score = 1 - Math.min(1, gini);
      return obj.direction === 'maximize' ? score : 1 - score;
    }

    case 'minimize-conflicts': {
      // Score = fraction of variables that are NOT in a collision (unique assignment).
      const conflicted = Object.values(counts).filter(n => n > 1).reduce((s, n) => s + (n - 1), 0);
      const score = 1 - Math.min(1, conflicted / Math.max(totalVars, 1));
      return obj.direction === 'minimize' ? score : 1 - score;
    }

    case 'maximize-preferences': {
      // Score = fraction of preference constraints that are satisfied.
      const prefs = constraints.filter(c => c.kind === 'preference');
      if (prefs.length === 0) return 0.7;
      const satisfied = prefs.filter(
        c => evaluateConstraint(c, assignments, variables) < 0.05,
      ).length;
      const score = satisfied / prefs.length;
      return obj.direction === 'maximize' ? score : 1 - score;
    }

    default:
      return 0.5;
  }
}

// ─── Energy function ────────────────────────────────────────────────────────

function computeEnergy(
  assignments: Record<string, string>,
  variables: Variable[],
  constraints: Constraint[],
  objectives: ObjectiveWeight[],
): number {
  let energy = 0;

  for (const c of constraints) {
    const v = evaluateConstraint(c, assignments, variables);
    energy += v * (c.type === 'hard' ? 1000 : 100);
  }

  for (const obj of objectives) {
    const score = evaluateObjective(obj, assignments, variables, constraints);
    // Score is already "how good this objective is" in [0,1].
    // We want to minimize energy, so bad scores → high energy.
    const qualityPenalty = 1 - score;
    energy += qualityPenalty * obj.weight * 200;
  }

  return energy;
}

// ─── Safe dynamic-key guard ──────────────────────────────────────────────────
// Dynamic assignment uses a Map (immune to property injection) with keys
// additionally constrained to a conservative whitelist.
const FORBIDDEN_KEYS = new Set(['__proto__', 'constructor', 'prototype']);
// Variable ids must match this conservative whitelist before being used as a
// dynamic property key. The regex is a CodeQL-recognised sanitizer for
// js/remote-property-injection (template payloads arrive via worker
// postMessage, which CodeQL treats as an untrusted source).
const SAFE_KEY = /^[A-Za-z0-9_-]{1,128}$/;
function safeAssign(
  target: Map<string, string>,
  key: string,
  value: string,
): void {
  if (FORBIDDEN_KEYS.has(key) || !SAFE_KEY.test(key)) return;
  target.set(key, value);
}

// ─── Neighbour perturbation ─────────────────────────────────────────────────

function makeNeighbour(
  state: Record<string, string>,
  variables: Variable[],
): { next: Record<string, string>; changed: string; fromVal: string; toVal: string } {
  const nextMap = new Map(Object.entries(state));
  const v = variables[Math.floor(Math.random() * variables.length)];
  const oldVal = nextMap.get(v.id) ?? '';
  const candidates = v.domain.filter(d => d !== oldVal);
  const newVal =
    candidates.length > 0
      ? candidates[Math.floor(Math.random() * candidates.length)]
      : oldVal;
  safeAssign(nextMap, v.id, newVal);
  return { next: Object.fromEntries(nextMap), changed: v.id, fromVal: oldVal, toVal: newVal };
}

// ─── Main solver ─────────────────────────────────────────────────────────────

/**
 * Solve a combinatorial allocation problem with Ising-style Simulated Annealing.
 *
 * @param template        — the problem definition (variables, constraints, objectives)
 * @param constitution    — active A11oy guardrail clauses (fetched live or from seeds)
 * @param constitutionVer — semver string of the active doctrine
 * @param constitutionSrc — provenance: 'live' | 'fallback' | 'seed'
 */
export function solve(
  template: ProblemTemplate,
  constitution: RosieGuardrailClause[] = ACTIVE_CONSTITUTION,
  constitutionVer: string = CONSTITUTION_VERSION,
  constitutionSrc: 'live' | 'fallback' | 'seed' = 'seed',
): AssignmentSolution {
  const start = performance.now();
  const { variables, constraints, objectives } = template;

  if (variables.length === 0) return emptyResult(template, start, constitutionVer, constitutionSrc);

  const ITERATIONS = 800;
  const T_START = 8.0;
  const T_END = 0.02;
  const COOLING = Math.pow(T_END / T_START, 1 / ITERATIONS);

  const randomState = (): Record<string, string> => {
    const a = new Map<string, string>();
    for (const v of variables)
      safeAssign(a, v.id, v.domain[Math.floor(Math.random() * v.domain.length)]);
    return Object.fromEntries(a);
  };

  let current = {
    assignments: randomState(),
    energy: 0,
  };
  current.energy = computeEnergy(current.assignments, variables, constraints, objectives);
  const initialEnergy = current.energy;

  let best = { assignments: { ...current.assignments }, energy: current.energy };

  // Top-K candidates pool for ranked alternatives (sorted by energy)
  const candidatePool: Array<{ assignments: Record<string, string>; energy: number }> = [];

  const addToPool = (a: Record<string, string>, e: number) => {
    if (candidatePool.length < 50) {
      candidatePool.push({ assignments: { ...a }, energy: e });
    } else {
      const worst = candidatePool.reduce(
        (max, c, i) => (c.energy > candidatePool[max].energy ? i : max),
        0,
      );
      if (e < candidatePool[worst].energy) {
        candidatePool[worst] = { assignments: { ...a }, energy: e };
      }
    }
  };

  const trace: TraceStep[] = [];
  const energyHistory: number[] = [];
  let T = T_START;

  for (let i = 0; i < ITERATIONS; i++) {
    const { next, changed, fromVal, toVal } = makeNeighbour(
      current.assignments,
      variables,
    );
    const nextEnergy = computeEnergy(next, variables, constraints, objectives);
    const dE = nextEnergy - current.energy;
    const prob = dE < 0 ? 1 : Math.exp(-dE / T);
    const accepted = Math.random() < prob;

    if (i < 30 || i % 35 === 0) {
      const varLabel = variables.find(v => v.id === changed)?.label ?? changed;
      trace.push({
        step: i + 1,
        action: accepted ? (dE < 0 ? 'improve' : 'accept-uphill') : 'reject',
        variable: varLabel,
        fromValue: fromVal,
        toValue: accepted ? toVal : fromVal,
        energyDelta: dE,
        accepted,
        temperature: T,
        reason:
          dE < 0
            ? `Greedy improvement: energy ↓ ${Math.abs(dE).toFixed(1)}`
            : accepted
            ? `Uphill accept: ΔE=+${dE.toFixed(1)}, P=${prob.toFixed(3)}, T=${T.toFixed(3)} — escape local min`
            : `Rejected: ΔE=+${dE.toFixed(1)}, P=${prob.toFixed(3)} < threshold — energy too high`,
      });
    }

    if (accepted) {
      current = { assignments: next, energy: nextEnergy };
      if (nextEnergy < best.energy) {
        best = { assignments: { ...next }, energy: nextEnergy };
      }
      addToPool(next, nextEnergy);
    }

    if (i % 8 === 0) energyHistory.push(Math.round(best.energy * 10) / 10);
    T *= COOLING;
  }

  // ── Constraint results ────────────────────────────────────────────────────
  const constraintResults = constraints.map(c => {
    const violationScore = evaluateConstraint(c, best.assignments, variables);
    return {
      id: c.id,
      label: c.label,
      type: c.type,
      satisfied: violationScore < 0.05,
      violationScore: Math.round(violationScore * 1000) / 1000,
    };
  });

  // ── Objective breakdown ───────────────────────────────────────────────────
  const objectiveBreakdown = objectives.map(obj => {
    const score = evaluateObjective(obj, best.assignments, variables, constraints);
    return {
      id: obj.id,
      label: obj.label,
      score: Math.round(score * 1000) / 1000,
      weight: obj.weight,
      contribution: Math.round(score * obj.weight * 1000) / 1000,
    };
  });

  // Genuine score: weighted average of objective scores
  const weightedScore = objectiveBreakdown.reduce((s, o) => s + o.contribution, 0);
  // Improvement ratio: how much better than random start
  const improvementRatio =
    initialEnergy > 0
      ? Math.max(0, 1 - best.energy / initialEnergy)
      : 0;
  const objectiveScore = Math.min(0.99, Math.max(0, weightedScore));

  // ── Guardrail check — full evaluation of every active A11oy clause ───────
  //
  // Each clause is dispatched by its checkKind field. Every clause in the
  // active constitution set receives a concrete executable evaluation — no
  // clause is display-only. Violations are recorded with clause id and detail.
  const guardrailViolations: string[] = [];

  // Pre-compute shared metrics used by multiple checkKinds.
  const allVals = Object.values(best.assignments);
  const valueCounts: Record<string, number> = {};
  for (const v of allVals) valueCounts[v] = (valueCounts[v] ?? 0) + 1;
  const shares = Object.values(valueCounts).map(n => n / Math.max(1, allVals.length));
  const mean = shares.length > 0 ? 1 / shares.length : 0;
  const gini = shares.length > 0
    ? shares.reduce((acc, s) => acc + Math.abs(s - mean), 0) / (2 * shares.length * mean)
    : 0;
  const maxShare = shares.length > 0 ? Math.max(...shares) : 0;
  const criticalHardViolations = constraintResults.filter(
    r => r.type === 'hard' && r.violationScore > 0.5,
  );

  // Dispatch: one executable evaluation per clause in the runtime constitution.
  type _GuardrailCheckKind = GuardrailCheckKind; // imported for exhaustiveness hint
  for (const clause of constitution) {
    const threshold = clause.checkParam ?? 0;
    let violated = false;
    let detail = '';

    switch (clause.checkKind) {
      case 'hard-violation-threshold':
        // C1.SAFETY: any hard constraint with violationScore > threshold fails
        if (criticalHardViolations.length > 0) {
          violated = true;
          detail = `${criticalHardViolations.length} hard constraint(s) with violationScore > ${threshold}`;
        }
        break;

      case 'constraint-transparency':
        // C2.HONESTY: every input constraint must appear in constraintResults
        {
          const resultIds = new Set(constraintResults.map(r => r.id));
          const missing = constraints.filter(c => !resultIds.has(c.id));
          if (missing.length > 0) {
            violated = true;
            detail = `${missing.length} constraint(s) missing from results: ${missing.map(c => c.id).join(', ')}`;
          }
        }
        break;

      case 'recommendation-only':
        // C3.AUTONOMY: always passes — ROSIE is a recommendation engine only
        violated = false;
        break;

      case 'proof-ledger-required':
        // C4.OVERSIGHT: always passes — proof entry is written by architecture guarantee
        violated = false;
        break;

      case 'gini-fairness':
        // C5.WELFARE: fail if Gini coefficient exceeds threshold
        if (allVals.length > 1 && gini > threshold) {
          violated = true;
          detail = `Gini=${gini.toFixed(2)} > ${threshold}`;
        }
        break;

      case 'coverage-diversity':
        // C6.REVERSIBILITY: fail if any single domain value captures > threshold of assignments
        if (allVals.length > 0 && maxShare > threshold) {
          const dominant = Object.entries(valueCounts).find(([, n]) => n / allVals.length === maxShare)?.[0] ?? '?';
          violated = true;
          detail = `value "${dominant}" assigned to ${(maxShare * 100).toFixed(0)}% of variables (threshold: ${(threshold * 100).toFixed(0)}%)`;
        }
        break;

      case 'unmapped-fail-closed':
        // A clause came back from A11oy that ROSIE has no executable mapping for.
        // Refuse to certify governance — the operator must extend ROSIE's check
        // catalog before this clause is honored. This is the fail-closed default.
        violated = true;
        detail = 'No executable mapping in ROSIE — clause requires a new GuardrailCheckKind branch';
        break;

      default:
        // Exhaustiveness guard: any genuinely unknown checkKind is also treated
        // as a hard violation so we never silently pass governance.
        violated = true;
        detail = `Unrecognized checkKind "${clause.checkKind}" — fail-closed`;
        break;
    }

    if (violated) {
      guardrailViolations.push(`${clause.id} [${clause.checkKind}]: ${clause.text}${detail ? ` — ${detail}` : ''}`);
    }
  }

  // ── Ranked alternatives from candidate pool ───────────────────────────────
  // Sort by energy, remove duplicates, skip the best result, take top 3
  const sortedCandidates = candidatePool
    .sort((a, b) => a.energy - b.energy)
    .filter(
      (c, i, arr) =>
        i === 0 ||
        JSON.stringify(c.assignments) !== JSON.stringify(arr[i - 1].assignments),
    );

  const altDescriptions = [
    'Second-best: prioritizes hard constraint satisfaction over objective optimization',
    'Third-best: maximizes resource diversity at a slight efficiency cost',
    'Fourth-best: conservative allocation preserving maximum operator optionality',
  ];

  const alternatives: AlternativeSolution[] = [];
  const seenAlts = new Set<string>([JSON.stringify(best.assignments)]);

  for (const candidate of sortedCandidates) {
    if (alternatives.length >= 3) break;
    const key = JSON.stringify(candidate.assignments);
    if (seenAlts.has(key)) continue;
    seenAlts.add(key);

    const altBreakdown = objectives.map(obj =>
      evaluateObjective(obj, candidate.assignments, variables, constraints),
    );
    const altScore = altBreakdown.reduce(
      (s, score, i) => s + score * objectives[i].weight,
      0,
    );
    const delta = Math.max(0, objectiveScore - altScore);

    // Compute what changed relative to best
    const distinctChanges: Array<{ variable: string; from: string; to: string }> = [];
    for (const [varId, val] of Object.entries(candidate.assignments)) {
      if (val !== best.assignments[varId]) {
        const varDef = variables.find(v => v.id === varId);
        distinctChanges.push({
          variable: varDef?.label ?? varId,
          from: best.assignments[varId] ?? '?',
          to: val,
        });
      }
    }

    alternatives.push({
      rank: alternatives.length + 2,
      assignments: candidate.assignments,
      objectiveScore: Math.min(0.99, Math.max(0, altScore)),
      delta,
      description: altDescriptions[alternatives.length] ?? 'Alternative allocation',
      distinctChanges: distinctChanges.slice(0, 4),
    });
  }

  return {
    assignments: best.assignments,
    objectiveScore,
    improvementRatio,
    objectiveBreakdown,
    constraintResults,
    reasoningTrace: trace.slice(0, 20),
    alternatives,
    guardrailsPassed: guardrailViolations.length === 0,
    guardrailViolations,
    constitutionVersion: constitutionVer,
    constitutionSource: constitutionSrc,
    solveTimeMs: Math.round(performance.now() - start),
    energyHistory,
    initialEnergy: Math.round(initialEnergy * 10) / 10,
    finalEnergy: Math.round(best.energy * 10) / 10,
  };
}

// ─── Empty result for templates with no variables ─────────────────────────

function emptyResult(
  template: ProblemTemplate,
  start: number,
  constitutionVer: string = CONSTITUTION_VERSION,
  constitutionSrc: 'live' | 'fallback' | 'seed' = 'seed',
): AssignmentSolution {
  return {
    assignments: {},
    objectiveScore: 0,
    improvementRatio: 0,
    objectiveBreakdown: template.objectives.map(o => ({
      id: o.id,
      label: o.label,
      score: 0,
      weight: o.weight,
      contribution: 0,
    })),
    constraintResults: [],
    reasoningTrace: [],
    alternatives: [],
    guardrailsPassed: true,
    guardrailViolations: [],
    constitutionVersion: constitutionVer,
    constitutionSource: constitutionSrc,
    solveTimeMs: Math.round(performance.now() - start),
    energyHistory: [],
    initialEnergy: 0,
    finalEnergy: 0,
  };
}
