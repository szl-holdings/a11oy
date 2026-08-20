/**
 * Perception envelope — uniform per-frame structured result across detector heads.
 *
 * Re-expressed from Human.js's single-pipeline-multi-head architecture (see
 * docs/research/perception-bio-synthesis-2026.md §1). The envelope is the
 * source-of-truth for receipt class `perception.envelope.v1`. Absence of a
 * detection in a head that ran ≠ absence of a head that ran at all — the
 * `ranHeads` / `skippedHeads` split makes that distinction observable.
 */

export type HeadName =
  | 'face'
  | 'body'
  | 'hand'
  | 'gesture'
  | 'iris'
  | 'emotion'
  | 'object'
  | 'person';

/** Normalised bounding box `[x, y, w, h]` in image-relative coords (each ∈ [0, 1]). */
export type NormalisedBox = readonly [number, number, number, number];

export interface Keypoint {
  /** Semantic name (e.g. `'left-eye'`); pipeline-defined namespace. */
  readonly name: string;
  /** Image-relative `[x, y]`. */
  readonly position: readonly [number, number];
  /** Per-keypoint confidence ∈ [0, 1]. */
  readonly score: number;
}

export interface Detection {
  /** Per-detection confidence ∈ [0, 1]. */
  readonly score: number;
  /** Normalised box (image-relative). */
  readonly box: NormalisedBox;
  /** Optional keypoints (head-dependent). */
  readonly keypoints?: readonly Keypoint[];
  /** Detector head's model version (e.g. `'blazeface@1.0.4'`). */
  readonly modelVersion: string;
  /** Optional class label (e.g. emotion name). */
  readonly label?: string;
}

export interface LivenessSummary {
  /** Aggregate liveness confidence ∈ [0, 1]. Higher = more real. */
  readonly livenessConfidence: number;
  /** Human-readable reasons for the score (e.g. `'blink-detected'`). */
  readonly livenessReasons: readonly string[];
  /** Window of frames considered (millis). */
  readonly windowMs: number;
}

export interface DetectionsSummary {
  readonly counts: Readonly<Record<HeadName, number>>;
}

export interface PerceptionEnvelope {
  /** Stable hash of the frame this envelope was computed from. */
  readonly frameHash: string;
  /** Heads that actually executed on this frame. */
  readonly ranHeads: readonly HeadName[];
  /** Heads that were intentionally skipped (budget, opt-out). */
  readonly skippedHeads: readonly HeadName[];
  readonly face: readonly Detection[];
  readonly body: readonly Detection[];
  readonly hand: readonly Detection[];
  readonly gesture: readonly Detection[];
  readonly object: readonly Detection[];
  readonly person: readonly Detection[];
  readonly liveness: LivenessSummary;
  readonly detectionsSummary: DetectionsSummary;
  /** Wall-clock budget consumed for this envelope (millis). */
  readonly budgetMs: number;
  /** Artifact that consumed the envelope (for receipt provenance). */
  readonly consumerArtifact: string;
}

export function summariseDetections(envelope: Omit<PerceptionEnvelope, 'detectionsSummary'>): DetectionsSummary {
  return {
    counts: {
      face: envelope.face.length,
      body: envelope.body.length,
      hand: envelope.hand.length,
      gesture: envelope.gesture.length,
      iris: 0,
      emotion: 0,
      object: envelope.object.length,
      person: envelope.person.length,
    },
  };
}
