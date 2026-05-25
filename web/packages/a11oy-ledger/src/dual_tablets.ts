/**
 * Heavenly Tablets — Merkle DAG Dual-Ledger (GRAFT 5)
 *
 * Source: 1 Enoch 81:1-2 ("Behold, the heavenly tablets of all the deeds
 *   of men ... till the most distant generations"); 1 Enoch 93:2;
 *   Jubilees 5:13. Nickelsburg (2001), 1 Enoch 1 (Hermeneia), pp.334-335.
 *
 * Two parallel Merkle DAGs (the "two tablets") record every governed
 * decision twice — once by the primary witness, once by the secondary —
 * and the ER-bridge (er_bridge.ts) verifies their root equality.
 */

export type TabletEntry = {
  /** Monotonic per-tablet sequence number. */
  seq: number;
  /** SHA-256 hex of the canonical JSON payload. */
  payloadHash: string;
  /** SHA-256 of (prevHash || payloadHash); genesis uses zero. */
  chainHash: string;
  /** ISO 8601 timestamp. */
  ts: string;
};

export type Tablet = {
  name: 'primary' | 'secondary';
  entries: TabletEntry[];
};

const ZERO_HASH = '0'.repeat(64);

async function sha256Hex(input: string): Promise<string> {
  // Use Web Crypto in the browser; Node ≥ 19 also exposes globalThis.crypto.
  const bytes = new TextEncoder().encode(input);
  const digest = await globalThis.crypto.subtle.digest('SHA-256', bytes);
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

export function createTablet(name: 'primary' | 'secondary'): Tablet {
  return { name, entries: [] };
}

export async function appendToTablet(tablet: Tablet, payload: unknown): Promise<TabletEntry> {
  const canonical = JSON.stringify(payload, Object.keys(payload as object).sort());
  const payloadHash = await sha256Hex(canonical);
  const prev = tablet.entries[tablet.entries.length - 1]?.chainHash ?? ZERO_HASH;
  const chainHash = await sha256Hex(prev + payloadHash);
  const entry: TabletEntry = {
    seq: tablet.entries.length,
    payloadHash,
    chainHash,
    ts: new Date().toISOString(),
  };
  tablet.entries.push(entry);
  return entry;
}

export function tabletRoot(tablet: Tablet): string {
  return tablet.entries[tablet.entries.length - 1]?.chainHash ?? ZERO_HASH;
}
