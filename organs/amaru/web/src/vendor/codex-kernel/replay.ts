// VENDORED FROM szl-holdings/platform@c11291e09702c86f3f8995fffcae6167155c7240 — packages/codex-kernel/src/replay.ts
// DO NOT EDIT HERE. Edit in the monorepo, then run scripts/sync_from_monorepo.sh sync.
/**
 * Replay verifier — reconstructs final_state from initial_state + trace
 * and asserts hash-chain integrity.
 *
 * This is the EU AI Act Article 12 replay contract expressed as code:
 * given the immutable trace, an auditor can rebuild the state and verify
 * every transition.
 */

import { canonicalize, chainHash } from './hash.js';
import type { Hex, Json, TraceEvent } from './types.js';

export interface ReplayReport {
  ok: boolean;
  steps_replayed: number;
  failed_step: number | null;
  failure_reason: string | null;
  final_state_hash: Hex | null;
  expected_final_state_hash: Hex | null;
}

const ZERO_HASH: Hex = '0'.repeat(32);

function applyDelta<S extends Json>(prev: S, delta: Json): S {
  if (
    prev === null ||
    typeof prev !== 'object' ||
    Array.isArray(prev) ||
    delta === null ||
    typeof delta !== 'object' ||
    Array.isArray(delta)
  ) {
    return delta as S;
  }
  const out: Record<string, Json> = { ...(prev as Record<string, Json>) };
  for (const k of Object.keys(delta as Record<string, Json>)) {
    const next = (delta as Record<string, Json>)[k];
    const cur = out[k];
    if (
      cur !== null &&
      typeof cur === 'object' &&
      !Array.isArray(cur) &&
      next !== null &&
      typeof next === 'object' &&
      !Array.isArray(next)
    ) {
      out[k] = applyDelta(cur, next) as Json;
    } else {
      out[k] = next;
    }
  }
  return out as S;
}

export function replay<S extends Json>(
  initial_state: S,
  trace: ReadonlyArray<TraceEvent>,
  expected_final_state_hash?: Hex,
): ReplayReport {
  let state: S = initial_state;
  let prev_hash: Hex = chainHash(ZERO_HASH, null, state as Json);
  let steps_replayed = 0;

  for (const event of trace) {
    // A halted-step event has state_next_hash === state_prev_hash and a stop_reason.
    // We still verify the prev hash matches our chain.
    if (event.state_prev_hash !== prev_hash) {
      return {
        ok: false,
        steps_replayed,
        failed_step: event.step,
        failure_reason: `prev_hash mismatch at step ${event.step}: expected ${prev_hash}, got ${event.state_prev_hash}`,
        final_state_hash: prev_hash,
        expected_final_state_hash: expected_final_state_hash ?? null,
      };
    }
    if (event.stop_reason !== null) {
      // Terminal event — chain ends here with no commit. Any subsequent
      // events would mean the trace was tampered with (appended-after-stop).
      const idx = trace.indexOf(event);
      if (idx !== trace.length - 1) {
        return {
          ok: false,
          steps_replayed,
          failed_step: event.step,
          failure_reason: `events found after terminal stop_reason at step ${event.step} (trace tampered: appended-after-stop)`,
          final_state_hash: prev_hash,
          expected_final_state_hash: expected_final_state_hash ?? null,
        };
      }
      return {
        ok: expected_final_state_hash ? prev_hash === expected_final_state_hash : true,
        steps_replayed,
        failed_step: null,
        failure_reason: null,
        final_state_hash: prev_hash,
        expected_final_state_hash: expected_final_state_hash ?? null,
      };
    }
    // Apply the proposed delta.
    const next_state = applyDelta(state, event.proposed_delta);
    const computed_next = chainHash(prev_hash, event.proposed_delta, next_state as Json);
    if (computed_next !== event.state_next_hash) {
      return {
        ok: false,
        steps_replayed,
        failed_step: event.step,
        failure_reason: `next_hash mismatch at step ${event.step}: expected ${event.state_next_hash}, got ${computed_next}`,
        final_state_hash: prev_hash,
        expected_final_state_hash: expected_final_state_hash ?? null,
      };
    }
    if (canonicalize(next_state as Json) === canonicalize(state as Json)) {
      // Replay shouldn't see no-op commits in committed entries; the kernel
      // emits no-ops only as terminal events with a stop_reason.
      return {
        ok: false,
        steps_replayed,
        failed_step: event.step,
        failure_reason: `no-op commit at step ${event.step}`,
        final_state_hash: prev_hash,
        expected_final_state_hash: expected_final_state_hash ?? null,
      };
    }
    state = next_state;
    prev_hash = computed_next;
    steps_replayed += 1;
  }

  return {
    ok: expected_final_state_hash ? prev_hash === expected_final_state_hash : true,
    steps_replayed,
    failed_step: null,
    failure_reason: null,
    final_state_hash: prev_hash,
    expected_final_state_hash: expected_final_state_hash ?? null,
  };
}

/** Convenience: parse a JSONL trace string. */
export function parseTraceJsonl(jsonl: string): TraceEvent[] {
  const out: TraceEvent[] = [];
  for (const line of jsonl.split('\n')) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    out.push(JSON.parse(trimmed) as TraceEvent);
  }
  return out;
}

export function serializeTraceJsonl(trace: ReadonlyArray<TraceEvent>): string {
  return trace.map((e) => JSON.stringify(e)).join('\n');
}
