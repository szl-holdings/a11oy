/**
 * @file packages/api/src/routes/formulas.ts
 * @description GET /v1/formulas/live — live formula moat status.
 *
 * Backs the Gradio "Live Formulas" tab. Reflects the status of the policy gates
 * in a11oy/packages/policy/src/gates/. The stub returns the known gate set with
 * Lean references; the real impl introspects the deployed gate registry.
 */

import { Hono } from 'hono';
import type { AppEnv } from '../lib/env.ts';
import type { LiveFormulas, Formula } from '../types/index.ts';

export const formulasRoute = new Hono<AppEnv>();

const GATES: Formula[] = [
  {
    id: 'A6',
    gate: 'hashChainIntegrity_gate',
    status: 'active',
    lean_ref: 'Lutar/Wheeler/DelayedChoiceClosure.lean',
  },
  {
    id: 'T3',
    gate: 'merkleDagBatch_gate',
    status: 'active',
    lean_ref: 'Lutar/PACBayes/CapabilityImprovementRate.lean',
  },
  {
    id: 'C1',
    gate: 'receiptChainConfluence_gate',
    status: 'active',
  },
];

formulasRoute.get('/live', (c) => {
  const body: LiveFormulas = {
    generated_at: new Date().toISOString(),
    formulas: GATES,
  };
  return c.json(body);
});
