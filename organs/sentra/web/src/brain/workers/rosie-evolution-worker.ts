/**
 * Sentra brain — ROSIE evolution worker.
 *
 * Glue module that ties the drift detector to `runRosieLoop`. Designed
 * to be runnable from either:
 *   - The sentra brain page (browser): a small `setInterval` host can
 *     call `runRosieEvolutionTick` whenever the page is mounted so
 *     proposals flow even while operators are watching.
 *   - The api-server scheduled job (Node): the job calls the same tick
 *     with an in-process `fetchImpl` that targets the local express
 *     router directly, no HTTP hop required.
 *
 * The function is deliberately small — all decision logic lives in
 * `lib/formulas/src/evolution.ts` (the canonical primitive) and all
 * drift accumulation lives in `drift-detector.ts`.
 *
 * Source: docs/thesis/v10-canonical.md §6.1, docs/audits/formulas.md §7.
 */

import {
  runRosieLoop,
  type RosieLoopOptions,
  type RosieLoopResult,
  type SentraSignalForRosie,
} from '@szl-holdings/formulas';
import { driftDetector, type DriftDetector } from '../lib/drift-detector';

export interface RosieEvolutionTickOptions extends RosieLoopOptions {
  /** Override the detector — defaults to the shared module-level one. */
  detector?: DriftDetector;
  /** Pre-baked signals (used when the detector lives in another process). */
  signals?: readonly SentraSignalForRosie[];
}

export interface RosieEvolutionTickResult {
  drained: number;
  proposals: number;
  noops: number;
  results: RosieLoopResult[];
}

export async function runRosieEvolutionTick(
  options: RosieEvolutionTickOptions = {},
): Promise<RosieEvolutionTickResult> {
  const detector = options.detector ?? driftDetector;
  const signals = options.signals ?? detector.drainSignals();
  const results = await runRosieLoop(signals, options);
  let proposals = 0;
  let noops = 0;
  for (const r of results) {
    if (r.decision.kind === 'tuning') proposals += 1;
    else noops += 1;
  }
  return { drained: signals.length, proposals, noops, results };
}
