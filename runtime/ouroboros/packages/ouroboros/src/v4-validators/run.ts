/**
 * v4 validator runner.
 *
 * `runValidators` is the entry point: given a runtime context and an
 * optional subset of validator IDs, it invokes each validator function
 * in deterministic registry order and returns the aggregate summary
 * via `summarizeValidators` (defined in validator-registry.ts).
 *
 * Two convenience overloads:
 *   - `runValidators(ctx)`             → runs all 9 validators
 *   - `runValidators(ctx, ['A','B'])`  → runs only the named subset (e.g. Sentra/Amaru profile)
 *
 * Determinism: the iteration order is the registry insertion order, which
 * is fixed and tested by `runtime-contract.v4.test.ts`. Same input →
 * same output, replayable.
 */

import {
  VALIDATOR_REGISTRY,
  summarizeValidators,
  type ValidatorId,
  type ValidatorResult,
  type ValidatorSummary,
} from '../validator-registry.js';

import { VALIDATOR_FNS } from './validators.js';
import type { RuntimeContext } from './types.js';

const ALL_IDS: readonly ValidatorId[] = Object.freeze(
  Object.keys(VALIDATOR_REGISTRY) as ValidatorId[],
);

export interface RunValidatorsResult {
  readonly results: readonly ValidatorResult[];
  readonly summary: ValidatorSummary;
}

export function runValidators(
  ctx: RuntimeContext,
  ids?: readonly ValidatorId[],
): RunValidatorsResult {
  const target = ids && ids.length > 0 ? ids : ALL_IDS;
  const results: ValidatorResult[] = [];
  for (const id of target) {
    const fn = VALIDATOR_FNS[id];
    if (!fn) {
      // Defensive: if a registry entry has no implementation, surface it
      // as a failed result rather than silently skipping.
      results.push(
        Object.freeze({
          validatorId: id,
          passed: false,
          note: 'no implementation registered for this validator id',
        }) as ValidatorResult,
      );
      continue;
    }
    results.push(fn(ctx));
  }
  return Object.freeze({
    results: Object.freeze([...results]),
    summary: summarizeValidators(results),
  });
}

export { ALL_IDS as V4_VALIDATOR_IDS };
