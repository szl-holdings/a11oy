/**
 * art-domain.ts — ArtDomain branded type
 * Organ: sentra (LIVER / TOXIN FILTER)
 * Canonical home: sentra/web/src/lib/dual-use/art-domain.ts
 * Author: Stephen P. Lutar Jr., SZL Holdings
 *
 * Structural fix for the adjacent finding documented by Hampichiq
 * in sentra#103 (sandbox_remediation/SUMMARY.md §"Adjacent finding"):
 *
 *   "CORE_WATCHER_ARTS entries store artDomain in lowercase-canonical form,
 *    but nothing in the type system enforces this. A future maintainer adding
 *    an art with artDomain: 'Root_Cutting' (mixed case) would break all existing
 *    callers using the lowercase form."
 *
 * This module introduces a branded type so the TypeScript compiler rejects
 * plain `string` where `ArtDomain` is required, and a runtime constructor
 * that enforces lowercase snake_case at the point of registration — not
 * silently at comparison time.
 *
 * Doctrine v11 strict. Watunakuy active.
 * © 2026 SZL Holdings, Inc. — Apache-2.0
 */

// ─── Branded type ─────────────────────────────────────────────────────────────

/**
 * ArtDomain is a `string` that has been validated (or explicitly trusted) to
 * be a lowercase snake_case identifier: /^[a-z][a-z0-9_]*$/
 *
 * The `__brand` field is a phantom — it does not exist at runtime. It exists
 * only so that TypeScript distinguishes `ArtDomain` from plain `string`.
 */
export type ArtDomain = string & { readonly __brand: "ArtDomain" };

// ─── Constructor object ────────────────────────────────────────────────────────

/**
 * ArtDomain — value-object constructor.
 *
 * Two entry points:
 *  - `ArtDomain.of(raw)` — trims whitespace only, then validates that the
 *    result is already a lowercase snake_case identifier.  Throws `Error` on
 *    any input that contains uppercase letters, leading digits, or characters
 *    outside [a-z0-9_].  Use when ingesting external or user-supplied strings.
 *  - `ArtDomain.fromTrusted(raw)` — bypasses validation; for hydrating values
 *    already guaranteed correct by a validated registry (e.g. hard-coded
 *    lowercase literals in CORE_WATCHER_ARTS).
 */
export const ArtDomain = {
  /**
   * Trim leading/trailing whitespace from `raw`, then validate that the result
   * matches `/^[a-z][a-z0-9_]*$/`.
   *
   * - `"  root_cutting  "` is accepted (whitespace stripped before check).
   * - `"Root_Cutting"` throws — the check fires on the trimmed value, and
   *   uppercase letters are not in the allowed set.  The caller must explicitly
   *   lowercase before calling `of()` if they intend to normalise; the
   *   constructor does not silently do it for them so that mixed-case
   *   registrations fail loudly rather than pass unnoticed.
   * - `""` (empty, or whitespace-only) throws — empty string fails the regex.
   * - `"rootcutting!"` throws — `!` is not in [a-z0-9_].
   *
   * Throwing at registration time (not silently at comparison time) is the
   * invariant Hampichiq identified as missing.
   */
  of(raw: string): ArtDomain {
    const trimmed = raw.trim();
    if (!/^[a-z][a-z0-9_]*$/.test(trimmed)) {
      throw new Error(
        `Invalid artDomain: "${raw}" (must be lowercase snake_case identifier matching /^[a-z][a-z0-9_]*$/)`,
      );
    }
    return trimmed as ArtDomain;
  },

  /**
   * Cast `raw` to `ArtDomain` without any validation.
   * Use ONLY when reading from a registry that was already validated on write
   * (e.g. `CORE_WATCHER_ARTS` entries that are hard-coded lowercase literals).
   *
   * Callers are responsible for ensuring `raw` satisfies the invariant.
   */
  fromTrusted(raw: string): ArtDomain {
    return raw as ArtDomain;
  },
} as const;
