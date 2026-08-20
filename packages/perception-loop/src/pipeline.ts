/**
 * Worker-friendly multi-head perception pipeline.
 *
 * The pipeline is intentionally adapter-shaped: the core has no DOM,
 * no model-loading code, and no WebGPU dependency. Concrete adapters
 * (TF.js, ONNX-Web, native bridges) implement `DetectorAdapter` and the
 * pipeline orchestrates them under a per-frame `budgetMs` cap.
 *
 * Re-expressed from Human.js's per-tick budget logic (see
 * docs/research/perception-bio-synthesis-2026.md §1, "Per-frame budget").
 */

import type { Detection, HeadName, PerceptionEnvelope } from './envelope.js';
import { summariseDetections } from './envelope.js';
import { computeLiveness, type FrameSignal } from './liveness.js';

export interface Frame {
  /** Stable hash of the frame contents. */
  readonly frameHash: string;
  /** Frame timestamp (millis since epoch). */
  readonly tMs: number;
  /** Adapter-opaque payload (`ImageData`, tensor handle, etc.). */
  readonly payload: unknown;
}

export interface DetectorAdapter {
  readonly head: HeadName;
  /** Approximate cost in millis. The pipeline skips heads whose cost
   * exceeds the remaining budget. */
  readonly costMs: number;
  detect(frame: Frame): Promise<readonly Detection[]>;
  /** Optional liveness signal contribution. */
  livenessSignal?(frame: Frame): FrameSignal | null;
}

export interface DetectOptions {
  readonly budgetMs: number;
  readonly consumerArtifact: string;
  /** Subset of heads to run (default: every adapter). */
  readonly heads?: readonly HeadName[];
  /** Recent frame signals used for liveness aggregation. */
  readonly recentSignals?: readonly FrameSignal[];
}

const HEADS_INIT: Record<HeadName, readonly Detection[]> = {
  face: [],
  body: [],
  hand: [],
  gesture: [],
  iris: [],
  emotion: [],
  object: [],
  person: [],
};

export async function detect(
  frame: Frame,
  adapters: readonly DetectorAdapter[],
  options: DetectOptions,
): Promise<PerceptionEnvelope> {
  const startMs = nowMs();
  const requested = new Set<HeadName>(options.heads ?? adapters.map((a) => a.head));
  const ran: HeadName[] = [];
  const skipped: HeadName[] = [];
  const results: Record<HeadName, Detection[]> = {
    face: [], body: [], hand: [], gesture: [], iris: [], emotion: [], object: [], person: [],
  };
  const signals: FrameSignal[] = [...(options.recentSignals ?? [])];

  for (const adapter of adapters) {
    if (!requested.has(adapter.head)) {
      skipped.push(adapter.head);
      continue;
    }
    const elapsed = nowMs() - startMs;
    if (elapsed + adapter.costMs > options.budgetMs) {
      skipped.push(adapter.head);
      continue;
    }
    const detections = await adapter.detect(frame);
    results[adapter.head] = [...detections];
    ran.push(adapter.head);
    const sig = adapter.livenessSignal?.(frame);
    if (sig) signals.push(sig);
  }

  const liveness = computeLiveness(signals);
  const base: Omit<PerceptionEnvelope, 'detectionsSummary'> = {
    frameHash: frame.frameHash,
    ranHeads: ran,
    skippedHeads: skipped,
    face: results.face,
    body: results.body,
    hand: results.hand,
    gesture: results.gesture,
    object: results.object,
    person: results.person,
    liveness,
    budgetMs: nowMs() - startMs,
    consumerArtifact: options.consumerArtifact,
  };

  return { ...base, detectionsSummary: summariseDetections(base) };
}

/** Wall-clock now in millis; thin wrapper for tests. */
export function nowMs(): number {
  return typeof performance !== 'undefined' && typeof performance.now === 'function'
    ? performance.now()
    : Date.now();
}

// Suppress "unused import" if a consumer tree-shakes liveness; the
// re-export below keeps the binding live.
export const _HEADS_INIT = HEADS_INIT;
