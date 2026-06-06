/**
 * @file packages/api/src/lib/store.ts
 * @description In-memory receipt + proposal store.
 *
 * Backs the stub while the real backend (RECEIPTS_BACKEND_URL → a11oy receipt
 * substrate + szl-receipts-server) is wired in. Receipts are appended to a
 * linear hash chain; proposals are tracked with their expiry and confirmation
 * state so /v1/execute/confirm can enforce expiry + idempotency.
 */

import { randomUUID } from 'node:crypto';
import type { Receipt, ExecuteProposal } from '../types/index.ts';
import { sha256Hex } from './receipt-substrate.ts';

export interface StoredProposal {
  receipt_id: string;
  proposal: ExecuteProposal;
  receipt: Receipt;
  confirmed: boolean;
  /** Idempotency key used at confirm time, once confirmed. */
  idempotency_key?: string;
  result?: Record<string, unknown>;
}

export class ReceiptStore {
  private receipts: { id: string; receipt: Receipt }[] = [];
  private byId = new Map<string, Receipt>();
  private proposals = new Map<string, StoredProposal>();
  private head: string | null = null;
  private index = 0;

  /** Current chain head hash (null = genesis). */
  get headHash(): string | null {
    return this.head;
  }

  /** Next chain index to assign. */
  get nextIndex(): number {
    return this.index;
  }

  /** Append an already-built receipt to the chain and index it. */
  append(receipt: Receipt): string {
    const id = randomUUID();
    this.receipts.push({ id, receipt });
    this.byId.set(id, receipt);
    // Advance the linear hash chain over the serialized receipt line.
    this.head = sha256Hex(JSON.stringify(receipt));
    this.index += 1;
    return id;
  }

  get(id: string): Receipt | undefined {
    return this.byId.get(id);
  }

  /** List receipts filtered by app (decoded from payload) and since-timestamp. */
  list(opts: { app?: string; since?: string; limit: number; offset: number }): {
    items: Receipt[];
    nextOffset: number | null;
  } {
    let rows = this.receipts.map((r) => r.receipt);
    if (opts.since) {
      const t = Date.parse(opts.since);
      rows = rows.filter((r) => Date.parse(r.chain.ts) >= t);
    }
    if (opts.app) {
      rows = rows.filter((r) => decodeApp(r) === opts.app);
    }
    const slice = rows.slice(opts.offset, opts.offset + opts.limit);
    const nextOffset = opts.offset + opts.limit < rows.length ? opts.offset + opts.limit : null;
    return { items: slice, nextOffset };
  }

  /** All receipts (for SSE replay). */
  all(): Receipt[] {
    return this.receipts.map((r) => r.receipt);
  }

  putProposal(p: StoredProposal): void {
    this.proposals.set(p.receipt_id, p);
  }

  getProposal(id: string): StoredProposal | undefined {
    return this.proposals.get(id);
  }
}

/** Decode the `app`/module field from a receipt body, best-effort. */
function decodeApp(r: Receipt): string | undefined {
  try {
    const body = JSON.parse(Buffer.from(r.payload, 'base64').toString('utf8')) as Record<string, unknown>;
    if (typeof body.app === 'string') return body.app;
    const target = body.target as { module?: string } | undefined;
    return target?.module;
  } catch {
    return undefined;
  }
}
