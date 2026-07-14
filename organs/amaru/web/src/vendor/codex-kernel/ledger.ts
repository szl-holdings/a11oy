// VENDORED FROM szl-holdings/platform@e87ad75ec8e280e2fe3a3e8f49c5c0b6c2eec4ea — packages/codex-kernel/src/ledger.ts
// DO NOT EDIT HERE. Edit in the monorepo, then run scripts/sync_from_monorepo.sh sync.
/**
 * Append-only proof ledger.
 *
 * In-memory store with JSONL serialization. Mirrors the payload's
 * `proof_ledger.jsonl` contract: every committed transition emits one entry,
 * and the ledger is never mutated in place.
 */

import { hashJson } from './hash.js';
import type { Hex, ProofLedgerEntry } from './types.js';

export class ProofLedger {
  private readonly entries: ProofLedgerEntry[] = [];
  private lastStateHash: Hex | null = null;

  append(entry: ProofLedgerEntry): void {
    if (this.lastStateHash !== null && entry.state_hash === this.lastStateHash) {
      // We never write the same state twice in a row; if a step proposed a
      // no-op the kernel halts with `convergence` instead of writing.
      throw new Error(
        `ledger.append: duplicate state_hash ${entry.state_hash} at step ${entry.step}`,
      );
    }
    this.entries.push(entry);
    this.lastStateHash = entry.state_hash;
  }

  size(): number {
    return this.entries.length;
  }

  toArray(): readonly ProofLedgerEntry[] {
    return this.entries;
  }

  toJsonl(): string {
    return this.entries.map((e) => JSON.stringify(e)).join('\n');
  }

  static fromJsonl(jsonl: string): ProofLedger {
    const ledger = new ProofLedger();
    for (const line of jsonl.split('\n')) {
      const trimmed = line.trim();
      if (!trimmed) continue;
      const entry = JSON.parse(trimmed) as ProofLedgerEntry;
      ledger.append(entry);
    }
    return ledger;
  }

  /**
   * Compute a digest of the entire ledger. Covers EVERY field of every entry
   * (step, ts, state_hash, delta_hash, receipt_id, policy_version,
   * approval_ref) so any post-hoc edit to governance metadata is detectable.
   */
  digest(): Hex {
    return hashJson(
      this.entries.map((e) => [
        e.step,
        e.ts,
        e.state_hash,
        e.delta_hash,
        e.receipt_id,
        e.policy_version,
        e.approval_ref,
      ]) as never,
    );
  }
}
