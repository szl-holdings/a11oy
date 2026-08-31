/**
 * Sentra brain — ROSIE continuous-evolution loop.
 *
 * The actual implementation now lives in `@szl-holdings/formulas` so the
 * api-server scheduled job and any sentra-brain worker can share the
 * exact same loop without duplicating code. This module is kept as a
 * thin re-export so existing brain callers and tests continue to work.
 *
 * Source: docs/thesis/v10-canonical.md §6.1, docs/audits/formulas.md §7.
 */

export {
  processSignal,
  runRosieLoop,
  type SentraSignalForRosie,
  type RosieLoopOptions,
  type RosieLoopResult,
} from '@szl-holdings/formulas';
