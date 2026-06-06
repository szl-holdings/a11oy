/**
 * Cross-step consistency scoring.
 *
 * Generic helpers for computing agreement between intermediate and final loop
 * outputs. Caller may also pass a domain-specific scorer to runLoop().
 */

/**
 * Numeric consistency: 1 - (|a - b| / max(|a|, |b|, eps)). Returns 0 if either
 * side is undefined.
 */
export function numericConsistency(
  a: number | undefined,
  b: number | undefined,
): number {
  if (a === undefined || b === undefined) return 0;
  if (!Number.isFinite(a) || !Number.isFinite(b)) return 0;
  if (a === b) return 1;
  const denom = Math.max(Math.abs(a), Math.abs(b), 1e-9);
  const sim = 1 - Math.abs(a - b) / denom;
  return Math.max(0, Math.min(1, sim));
}

/**
 * Cosine similarity for arrays of numbers, mapped to [0, 1].
 */
export function vectorConsistency(
  a: number[] | undefined,
  b: number[] | undefined,
): number {
  if (!a || !b || a.length === 0 || a.length !== b.length) return 0;
  let dot = 0;
  let na = 0;
  let nb = 0;
  for (let i = 0; i < a.length; i++) {
    dot += a[i]! * b[i]!;
    na += a[i]! * a[i]!;
    nb += b[i]! * b[i]!;
  }
  if (na === 0 || nb === 0) return 0;
  const cos = dot / (Math.sqrt(na) * Math.sqrt(nb));
  return Math.max(0, Math.min(1, (cos + 1) / 2));
}

/**
 * String consistency via normalized longest-common-subsequence length.
 * Useful for plan-text or threat-narrative comparisons.
 */
export function stringConsistency(
  a: string | undefined,
  b: string | undefined,
): number {
  if (a === undefined || b === undefined) return 0;
  if (a === b) return 1;
  if (a.length === 0 || b.length === 0) return 0;
  const m = a.length;
  const n = b.length;
  // O(m*n) DP — capped to avoid pathological inputs.
  if (m * n > 200_000) {
    // Fast path for very long strings: token-overlap Jaccard.
    const ta = new Set(a.split(/\s+/).filter(Boolean));
    const tb = new Set(b.split(/\s+/).filter(Boolean));
    if (ta.size === 0 && tb.size === 0) return 1;
    let inter = 0;
    for (const t of ta) if (tb.has(t)) inter++;
    const uni = ta.size + tb.size - inter;
    return uni === 0 ? 0 : inter / uni;
  }
  const dp: number[] = new Array(n + 1).fill(0);
  for (let i = 1; i <= m; i++) {
    let prev = 0;
    for (let j = 1; j <= n; j++) {
      const tmp = dp[j]!;
      if (a[i - 1] === b[j - 1]) dp[j] = prev + 1;
      else dp[j] = Math.max(dp[j]!, dp[j - 1]!);
      prev = tmp;
    }
  }
  const lcs = dp[n]!;
  return (2 * lcs) / (m + n);
}

/**
 * Set consistency via Jaccard similarity. Useful for sets of entity IDs,
 * tools, or attack vectors.
 */
export function setConsistency<T>(
  a: ReadonlySet<T> | T[] | undefined,
  b: ReadonlySet<T> | T[] | undefined,
): number {
  if (!a || !b) return 0;
  const sa = a instanceof Set ? a : new Set(a);
  const sb = b instanceof Set ? b : new Set(b);
  if (sa.size === 0 && sb.size === 0) return 1;
  let inter = 0;
  for (const v of sa) if (sb.has(v)) inter++;
  const uni = sa.size + sb.size - inter;
  return uni === 0 ? 0 : inter / uni;
}
