/**
 * Liveness state machine — turns a sliding window of frame signals into
 * a calibrated `livenessConfidence` with explicit reasons.
 *
 * Re-expressed from Human.js's iris/blink/head-pose deltas (see
 * docs/research/perception-bio-synthesis-2026.md §1). The state machine
 * is deliberately simple so it composes with the receipt schema and is
 * cheap to run on-device. The formula is mirrored in
 * `@szl-holdings/lambda-math` as `gazeStability` for the receipt-side
 * monotone-confidence check.
 */

import type { LivenessSummary } from './envelope.js';

export interface FrameSignal {
  /** Timestamp (millis since epoch). */
  readonly tMs: number;
  /** Iris motion magnitude (image-relative pixels per ms). */
  readonly irisMotion: number;
  /** Eye-aperture ratio (0 = fully closed, 1 = fully open). */
  readonly eyeAperture: number;
  /** Head-pose delta vs. last frame (radians). */
  readonly headPoseDelta: number;
}

export interface LivenessOptions {
  /** Sliding window in millis (default: 2000ms). */
  readonly windowMs?: number;
  /** Min blink count required for a positive blink reason. */
  readonly minBlinks?: number;
  /** Eye-aperture threshold below which the eye is "closed". */
  readonly blinkAperture?: number;
  /** Min iris-motion variance for a positive saccade reason. */
  readonly minIrisVariance?: number;
  /** Min head-pose delta sum for a positive head-motion reason. */
  readonly minHeadPoseDelta?: number;
}

const DEFAULTS: Required<LivenessOptions> = {
  windowMs: 2000,
  minBlinks: 1,
  blinkAperture: 0.2,
  minIrisVariance: 0.001,
  minHeadPoseDelta: 0.05,
};

/**
 * Compute liveness over the most recent `windowMs` of frame signals.
 *
 * Confidence is the count of satisfied liveness criteria divided by the
 * total number of criteria (3): blink, iris motion, head pose. Monotone
 * non-decreasing in each criterion — adding a satisfied signal can only
 * raise the confidence, never lower it. This is the property mirrored in
 * `gazeStability` and used in `peak.classification.v1` cutoff arguments.
 */
export function computeLiveness(
  signals: readonly FrameSignal[],
  options: LivenessOptions = {},
): LivenessSummary {
  const opts = { ...DEFAULTS, ...options };

  if (signals.length === 0) {
    return { livenessConfidence: 0, livenessReasons: [], windowMs: opts.windowMs };
  }

  const lastT = signals[signals.length - 1]!.tMs;
  const windowStart = lastT - opts.windowMs;
  const window = signals.filter((s) => s.tMs >= windowStart);

  // Blink detection: eye aperture dips below threshold then recovers.
  let blinks = 0;
  let inBlink = false;
  for (const s of window) {
    if (s.eyeAperture < opts.blinkAperture && !inBlink) {
      inBlink = true;
    } else if (s.eyeAperture >= opts.blinkAperture && inBlink) {
      inBlink = false;
      blinks++;
    }
  }

  // Iris motion variance.
  const mean = window.reduce((acc, s) => acc + s.irisMotion, 0) / window.length;
  const variance = window.reduce((acc, s) => acc + (s.irisMotion - mean) ** 2, 0) / window.length;

  // Head-pose delta sum.
  const headDelta = window.reduce((acc, s) => acc + Math.abs(s.headPoseDelta), 0);

  const reasons: string[] = [];
  let satisfied = 0;
  if (blinks >= opts.minBlinks) {
    satisfied++;
    reasons.push(`blinks=${blinks}`);
  }
  if (variance >= opts.minIrisVariance) {
    satisfied++;
    reasons.push(`iris-variance=${variance.toExponential(2)}`);
  }
  if (headDelta >= opts.minHeadPoseDelta) {
    satisfied++;
    reasons.push(`head-pose-delta=${headDelta.toFixed(3)}`);
  }

  return {
    livenessConfidence: satisfied / 3,
    livenessReasons: reasons,
    windowMs: opts.windowMs,
  };
}
