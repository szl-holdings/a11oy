// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. Jr. — SZL Holdings
// ORCID: 0009-0001-0110-4173
// Doctrine v7
/**
 * event-store.ts — In-memory append-only event receipt store.
 *
 * Each ingested event becomes a pendant under a running KhipuRoot. The store
 * maintains a prefix-hash chain over sequential receipt entries so that any
 * tampering with entry N invalidates entries N+1..k. This is the structural
 * binding that connects the HTTP event surface to the khipu receipt DAG.
 */

import { createHash } from 'node:crypto';
import {
  buildDecision,
  buildOrgan,
  buildRoot,
  verifySumInvariant,
  type KhipuRootReceipt,
} from '../khipu-receipt.ts';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Stored receipt entry for one ingested event. */
export interface EventReceiptEntry {
  readonly seq: number;
  readonly ts: string;              // ISO-8601
  readonly eventType: string;
  readonly source: string;
  readonly payloadHash: string;     // SHA-256 hex of canonical payload
  readonly traceparent?: string;
  readonly receipt: KhipuRootReceipt;
  readonly prevHash: string;        // hash of the previous entry (or 'genesis')
  readonly selfHash: string;        // hash over this entry (prefix-hash chain)
}

/** Shape returned from POST /v1/events */
export interface IngestResult {
  readonly receipt_seq: number;
  readonly root_hash: string;
  readonly accepted: true;
}

// ---------------------------------------------------------------------------
// Hash helpers
// ---------------------------------------------------------------------------

function sha256Hex(input: string): string {
  return createHash('sha256').update(input).digest('hex');
}

function entryHash(entry: Omit<EventReceiptEntry, 'selfHash'>): string {
  return sha256Hex(
    JSON.stringify({
      seq: entry.seq,
      ts: entry.ts,
      eventType: entry.eventType,
      source: entry.source,
      payloadHash: entry.payloadHash,
      prevHash: entry.prevHash,
      rootHash: entry.receipt.rootHash,
    }),
  );
}

// ---------------------------------------------------------------------------
// EventStore
// ---------------------------------------------------------------------------

/** Append-only, in-process event receipt store. Not persistent across restarts
 * (a production deployment would back this with a durable store). Thread-safety
 * is maintained via synchronous append (Node.js event loop is single-threaded). */
export class EventStore {
  private readonly entries: EventReceiptEntry[] = [];
  private headHash: string = 'genesis';

  /** Ingest one event and produce a khipu receipt entry.
   * Returns the resulting {@link IngestResult}. */
  ingest(
    eventType: string,
    source: string,
    payload: Record<string, unknown>,
    traceparent?: string,
  ): IngestResult {
    const seq = this.entries.length + 1;
    const ts = new Date().toISOString();

    // Build a single-decision, single-organ khipu root for this event.
    // The governance value is 1 per event (unit weight; callers may supply
    // a numeric `value` field in payload to override this default).
    const rawValue = typeof payload['value'] === 'number'
      ? Math.max(0, Math.round(payload['value']))
      : 1;

    const decision = buildDecision(
      `event:${source}:${seq}`,
      rawValue,
      { type: eventType, source, seq, ts, traceparent: traceparent ?? null },
    );
    const organ = buildOrgan(`organ:${source}`, [decision]);
    const receipt = buildRoot(`receipt:${seq}`, [organ]);

    // Verify the summation invariant holds (it always should by construction,
    // but we check explicitly to satisfy the Lean TH11 runtime obligation).
    const check = verifySumInvariant(receipt);
    if (!check.ok) {
      throw new Error(`khipu sum invariant violated on ingest: ${check.reason}`);
    }

    const payloadHash = sha256Hex(JSON.stringify(payload));
    const base: Omit<EventReceiptEntry, 'selfHash'> = {
      seq,
      ts,
      eventType,
      source,
      payloadHash,
      traceparent,
      receipt,
      prevHash: this.headHash,
    };
    const selfHash = entryHash(base);
    const entry: EventReceiptEntry = { ...base, selfHash };

    this.entries.push(entry);
    this.headHash = selfHash;

    return {
      receipt_seq: seq,
      root_hash: receipt.rootHash,
      accepted: true,
    };
  }

  /** Return the entry at 1-based seq, or undefined. */
  getBySeq(seq: number): EventReceiptEntry | undefined {
    return this.entries[seq - 1];
  }

  /** Current head seq (0 if empty). */
  get headSeq(): number {
    return this.entries.length;
  }

  /** Root hash of the most-recently ingested receipt, or 'genesis'. */
  get headRootHash(): string {
    const last = this.entries[this.entries.length - 1];
    return last ? last.receipt.rootHash : 'genesis';
  }
}

/** Singleton store for the server process. Tests may construct their own instance. */
export const globalEventStore = new EventStore();
