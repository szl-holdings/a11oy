<!-- SPDX-License-Identifier: Apache-2.0 -->

# Vendored: `@workspace/codex-kernel`

This directory is a **single canonical, byte-for-byte vendored copy** of the real,
attested Codex-Kernel that lives in `szl-holdings/platform` at
`packages/codex-kernel/src/*` (`@workspace/codex-kernel@1.0.0`, Apache-2.0,
first-party org code).

It replaces the former divergent look-alike at `src/_stubs/codex-kernel`
(non-crypto `simpleHash`, no `ProofLedger`, stop reason capped at
`hard_fail_limit` — could never emit `convergence`). Amaru's Vite alias
`@workspace/codex-kernel` now resolves here.

- **Real API:** `runLoop` (iterator-driven `steps.next(state)`), `ProofLedger`
  (append-only, `.digest()`), `driftBounds`/`humanGate`/`evidenceProvenance`/
  `stateTransitionRule` validators, `replay`, FNV-1a-128 `chainHash`, the Dresden
  Venus reference generator, and the EntropyDepthAllocator.
- **Hash honesty:** `hash.ts` is a deterministic **non-cryptographic** FNV-1a-128
  mixing hash — sufficient for tamper-evident *replay* (EU AI Act Art. 12 logging),
  NOT collision-resistant against a motivated adversary. See its header comment.
- **Convergence honesty:** the loop halts on `convergence` when the step generator
  is exhausted with no hard-fail; this is an engineering stop condition. Λ =
  Conjecture 1 (advisory) — no claim of *proven* convergence.

## Upstream / attestation

- Source: https://github.com/szl-holdings/platform/tree/main/packages/codex-kernel
- Attestation (v1.0.0): https://github.com/szl-holdings/platform/releases/tag/v1.0.0-codex-kernel

To refresh: copy `platform/packages/codex-kernel/src/{index,types,hash,ledger,replay,validators,receipts,dresden-venus,depth-allocator}.ts`
here verbatim. Keep this the ONLY copy in a11oy — do not fork.
