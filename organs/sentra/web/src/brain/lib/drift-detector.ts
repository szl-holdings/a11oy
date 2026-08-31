/**
 * Sentra brain — drift detector re-export.
 *
 * The implementation now lives in `@szl-holdings/formulas` so the
 * api-server scheduled job and the sentra brain page can share the
 * exact same buffer semantics. This module is kept as a thin re-export
 * so existing brain callers and tests continue to work.
 */

export {
  createDriftDetector,
  driftDetector,
  DEFAULT_DRIFT_THRESHOLDS,
  type DriftDetector,
  type DriftObservation,
  type DriftThresholds,
} from '@szl-holdings/formulas';
