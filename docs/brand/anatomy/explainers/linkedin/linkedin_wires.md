# LinkedIn post — anatomy_wires.pdf (BLOOD + IMMUNE)

---

How does an AI agent prove, byte for byte, that it didn't lie to you?

**BLOOD — the circulatory wiring.**

One bus carries everything. It is called YAWAR and it is 20 lines of Python. Twenty. Every organ writes through one ceremonial gate (RUWAY), the only authorized writer. The brain hangs off the bus by a single tether. It reads snapshots. It never writes.

A receipt is exactly this:

`packet → json.dumps(sort_keys=True) → sha256 → hexdigest → append`

From 20 SLOC you get five guarantees, each one a line you can read:

- **Append-only.** No method exists to delete or mutate prior receipts. It is the absence of code.
- **Stable serialization.** sort_keys=True + default=str → deterministic bytes.
- **Cryptographic link.** sha256.hexdigest() → 64-char hex.
- **Inline immune check.** sentra_inspect runs BEFORE compute. Rejected packets raise PermissionError and never reach the ledger.
- **Frozen snapshots.** snapshot() deep-copies via json round-trip. Readers cannot mutate the source.

Honest scope: byte-identical re-runs only when packet values are timestamp-free. Kernels with _iso_now() are intra-run deterministic only, documented in their result file.

**IMMUNE — two layers in series, no override.**

SENTRA. White blood cell. 18 SLOC. Inline in Yawar.append. Six threat signatures + 1MB DoS guard:

`["DROP TABLE", "rm -rf", "<script", "eval(", "subprocess", "../../etc"]`

True clears all six. False raises PermissionError and the receipt never enters the ledger. No partial state.

HUKLLA. Deadman. 660 SLOC. Ten deterministic tripwires checked BEFORE and AFTER every cycle:

- T01 MORAL_GROUNDING < 0.95 — hard fail
- T02 MEASURABILITY_HONESTY < 0.95 — hard fail
- T03 EVAL_AWARENESS flag
- T04 DECEPTION_KEYWORDS
- T05 UNAUTHORIZED_WRITE
- T06 SPAWN_OUTSIDE_SANDBOX
- T07 UNAUTHORIZED_NETWORK
- T08 SELF_CODE_MODIFY
- T09 CONFLICTING_DIRECTIVES
- T10 REVERSAL_DIRECTIVE — STOP/undo/revert, immediate halt

Autonomy is gated by tier. SCRATCHPAD runs free. REVIEW needs approval every K cycles. PRODUCTION needs per-cycle approval. HUKLLA reads the tier and enforces it.

38 lines of bus + immune code. 660 lines of tripwire ledger. One hard rule: the brain never writes. Honest scope: SENTRA is a doctrine prefilter, not a complete threat model. Layer a WAF, secrets scanner, and dependency audit upstream.

Receipts available on request.

— Stephen P. Lutar · SZL Holdings · ORCID 0009-0001-0110-4173

#AIsafety #AIagents #CryptographicAudit #DeterministicAI #ResponsibleAI
