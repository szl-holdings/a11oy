// @szl-holdings/sparse-attention-kit — public surface.
//
// Five primitives re-expressed against Doctrine V6 (see
// docs/research/sparse-attention-synthesis-2026.md):
//
//   1. envelope                — sparse regime claim (MiniMax M2's "no free lunch")
//   2. contradiction-probe     — index↔sparse disagreement detector
//   3. two-level-commit        — NSA coarse/fine pair with Λ-floor gating
//   4. recorded-router         — MoBA witness ("record what was attended")
//   5. io-budget               — FlashAttention bandwidth-as-budget receipt
//
// No kernel ships here. This is the *envelope and receipt* layer that a kernel
// (NSA, MoBA, FlashAttention, or vendor-private) MUST be wrapped in to be
// admissible under our governed-autonomy stack.

export * from "./envelope.js";
export * from "./contradiction-probe.js";
export * from "./two-level-commit.js";
export * from "./recorded-router.js";
export * from "./io-budget.js";
export * from "./receipts.js";
