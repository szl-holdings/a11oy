/**
 * ROSIE Solver Web Worker
 *
 * Runs the Ising-style simulated annealing solver off the main thread so
 * the UI stays responsive during the 800-iteration solve.
 *
 * Message protocol (main → worker):
 *   {
 *     type: 'solve';
 *     payload: ProblemTemplate;
 *     constitution: RosieGuardrailClause[];   // active A11oy clauses
 *     constitutionVersion: string;
 *     constitutionSource: 'live' | 'fallback' | 'seed';
 *   }
 *
 * Message protocol (worker → main):
 *   { type: 'result';  value: AssignmentSolution }
 *   { type: 'error';   message: string }
 */

import { solve, SEED_CONSTITUTION, SEED_CONSTITUTION_VERSION } from '../lib/isingOptimizer';
import type { RosieGuardrailClause } from '../data/a11oyConstitution';
import type { ProblemTemplate } from '../data/optimizerTemplates';

interface SolveMessage {
  type: 'solve';
  payload: ProblemTemplate;
  constitution?: RosieGuardrailClause[];
  constitutionVersion?: string;
  constitutionSource?: 'live' | 'fallback' | 'seed';
}

self.addEventListener('message', (e: MessageEvent<SolveMessage>) => {
  if (e.data.type !== 'solve') return;

  try {
    const {
      payload,
      constitution = SEED_CONSTITUTION,
      constitutionVersion = SEED_CONSTITUTION_VERSION,
      constitutionSource = 'seed',
    } = e.data;

    const result = solve(payload, constitution, constitutionVersion, constitutionSource);
    self.postMessage({ type: 'result', value: result });
  } catch (err) {
    self.postMessage({ type: 'error', message: String(err) });
  }
});
