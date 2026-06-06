/**
 * @file packages/api/src/lib/canonical-json.ts
 * @description Re-export of the canonical-JSON serializer used across SZL.
 *
 * Canonical form = RFC 8785-style: NFC-normalized strings, recursively
 * key-sorted objects, undefined dropped, non-finite numbers rejected. This is
 * the same implementation a11oy's receipt-substrate uses (canonicalJson) — the
 * receipt body MUST be byte-identical across emit and verify or the DSSE PAE
 * (and therefore the signature) will not match. See PhD Crypto verdict A4.
 *
 * Vendored here (rather than imported from the unpublished
 * @szl-holdings/a11oy-receipt-substrate) so the API builds standalone; keep in
 * sync with the substrate's canonicalJson.
 */

function normaliseStrings(value: unknown): unknown {
  if (typeof value === 'string') return value.normalize('NFC');
  if (Array.isArray(value)) return value.map(normaliseStrings);
  if (value && typeof value === 'object') {
    const result: Record<string, unknown> = {};
    for (const [key, child] of Object.entries(value as Record<string, unknown>)) {
      result[key.normalize('NFC')] = normaliseStrings(child);
    }
    return result;
  }
  return value;
}

function canonicalValue(value: unknown): unknown {
  if (value === null) return null;
  if (typeof value === 'string' || typeof value === 'boolean') return value;
  if (typeof value === 'number') {
    if (!Number.isFinite(value)) throw new Error('canonicalJson: non-finite numbers are not supported');
    return value;
  }
  if (Array.isArray(value)) return value.map(canonicalValue);
  if (typeof value === 'object') {
    const obj = value as Record<string, unknown>;
    const sorted: Record<string, unknown> = {};
    for (const key of Object.keys(obj).sort()) {
      const child = obj[key];
      if (typeof child === 'undefined') continue;
      if (typeof child === 'function' || typeof child === 'symbol') {
        throw new Error(`canonicalJson: unsupported value at key '${key}'`);
      }
      sorted[key] = canonicalValue(child);
    }
    return sorted;
  }
  throw new Error('canonicalJson: unsupported root value');
}

/** Serialize a value to canonical JSON (deterministic, key-sorted, NFC). */
export function canonicalJson(value: unknown): string {
  return JSON.stringify(canonicalValue(normaliseStrings(value)));
}

/** Canonical JSON as UTF-8 bytes — the RAW body fed to the DSSE PAE. */
export function canonicalJsonBytes(value: unknown): Uint8Array {
  return new TextEncoder().encode(canonicalJson(value));
}
