/**
 * Amaru → A11oy fabric orchestration client.
 *
 * This was formerly a set of silent no-ops. It now emits REAL, tamper-evident
 * proofs: every proof is hash-chained to its predecessor with the same
 * FNV-1a-128 chain hash the codex-kernel uses (`@workspace/codex-kernel`),
 * persisted to a local append-only ledger (browser localStorage), and
 * best-effort anchored to the Amaru receipt substrate at
 * `/api/amaru/v1/receipts`. Network anchoring is fire-and-forget: a failure
 * never throws into the SPA, but success is never faked either.
 *
 * Honesty: the chain hash is non-cryptographic (see the kernel's hash.ts) —
 * sufficient for tamper-evident replay, NOT collision-resistant against a
 * motivated adversary. The digest proves the local chain is internally
 * consistent; the server receipt (when reachable) is the durable anchor.
 */

import { chainHash, hashJson, shortHash } from '@workspace/codex-kernel';

const GENESIS_HASH = '0'.repeat(32);
const LEDGER_KEY = 'amaru.fabric.proof-ledger.v1';
const RECEIPT_ENDPOINT = '/api/amaru/v1/receipts';

export interface FabricProofEntry {
  id: string;
  product: string;
  kind: string;
  summary: string;
  deepLink: string;
  payload: Record<string, unknown>;
  ts: string;
  /** proof_hash of the previous entry (GENESIS for the first). */
  prev_hash: string;
  /** chain hash over (prev_hash, payload-delta, entry-body). */
  proof_hash: string;
  /** true when the server anchor POST was not confirmed. */
  local_only: boolean;
}

function hasStorage(): boolean {
  return typeof globalThis !== 'undefined' && 'localStorage' in globalThis;
}

function loadLedger(): FabricProofEntry[] {
  if (!hasStorage()) return [];
  try {
    const raw = globalThis.localStorage.getItem(LEDGER_KEY);
    return raw ? (JSON.parse(raw) as FabricProofEntry[]) : [];
  } catch {
    return [];
  }
}

function saveLedger(entries: FabricProofEntry[]): void {
  if (!hasStorage()) return;
  try {
    globalThis.localStorage.setItem(LEDGER_KEY, JSON.stringify(entries));
  } catch {
    /* storage full / unavailable — the in-memory return value still stands */
  }
}

async function anchor(entry: FabricProofEntry): Promise<boolean> {
  if (typeof fetch !== 'function') return false;
  try {
    const res = await fetch(RECEIPT_ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify(entry),
    });
    return res.ok;
  } catch {
    return false;
  }
}

export async function registerWithA11oy(opts: {
  product: string;
  displayName: string;
  basePath: string;
  accentColor: string;
  capabilities: Array<{ id: string; label: string; governanceClass: string }>;
}): Promise<void> {
  // Best-effort registration handshake with the fabric. Non-blocking: the SPA
  // renders regardless of whether the receipt substrate is reachable.
  if (typeof fetch !== 'function') return;
  try {
    await fetch('/api/amaru/v1/fabric/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify(opts),
    });
  } catch {
    /* offline / substrate down — registration is advisory */
  }
}

export async function emitProof(opts: {
  product: string;
  kind: string;
  summary: string;
  deepLink: string;
  payload: Record<string, unknown>;
}): Promise<FabricProofEntry> {
  const ledger = loadLedger();
  const prev_hash =
    ledger.length > 0 ? ledger[ledger.length - 1].proof_hash : GENESIS_HASH;
  const ts = new Date().toISOString();
  const body = {
    product: opts.product,
    kind: opts.kind,
    summary: opts.summary,
    deepLink: opts.deepLink,
    payload: opts.payload,
    ts,
  };
  const proof_hash = chainHash(
    prev_hash,
    opts.payload as never,
    body as never,
  );
  const entry: FabricProofEntry = {
    id: proof_hash,
    ...body,
    prev_hash,
    proof_hash,
    local_only: true,
  };
  const anchored = await anchor(entry);
  entry.local_only = !anchored;
  saveLedger([...ledger, entry]);
  return entry;
}

export async function crossProductHandoff(opts: {
  fromProduct: string;
  toProduct: string;
  refId: string;
  reason: string;
  deepLink: string;
}): Promise<void> {
  // A handoff is itself a fabric event — emit it as a real chained proof so it
  // shows up in the ledger and the inference observatory feed.
  await emitProof({
    product: opts.fromProduct,
    kind: 'cross_product_handoff',
    summary: `${opts.fromProduct} → ${opts.toProduct}: ${opts.reason}`,
    deepLink: opts.deepLink,
    payload: {
      refId: opts.refId,
      toProduct: opts.toProduct,
      reason: opts.reason,
    },
  });
}

export async function listFabricProofs(opts?: {
  limit?: number;
}): Promise<FabricProofEntry[]> {
  const entries = loadLedger().slice().reverse();
  const limit = opts?.limit;
  const out = typeof limit === 'number' ? entries.slice(0, limit) : entries;
  return out;
}

/** Digest of the local proof chain — exported for verification affordances. */
export function fabricLedgerDigest(): string {
  const entries = loadLedger();
  return shortHash(
    hashJson(entries.map((e) => [e.ts, e.proof_hash, e.prev_hash]) as never),
  );
}
