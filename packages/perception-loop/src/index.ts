/**
 * @szl-holdings/perception-loop
 *
 * Operator-loop perception envelope. Sibling to seeing-eye (agent vision);
 * this package serves operator/reviewer/scene-actor presence on the
 * Doctrine V6 evidence-first pillar.
 *
 * See docs/research/perception-bio-synthesis-2026.md §1.
 */

export type {
  PerceptionEnvelope,
  Detection,
  Keypoint,
  HeadName,
  LivenessSummary,
  DetectionsSummary,
  NormalisedBox,
} from './envelope.js';
export { summariseDetections } from './envelope.js';

export { computeLiveness } from './liveness.js';
export type { FrameSignal, LivenessOptions } from './liveness.js';

export { detect, nowMs } from './pipeline.js';
export type { Frame, DetectorAdapter, DetectOptions } from './pipeline.js';

export const PERCEPTION_LOOP_VERSION = '0.1.0' as const;
export const PERCEPTION_ENVELOPE_RECEIPT_CLASS = 'perception.envelope.v1' as const;
