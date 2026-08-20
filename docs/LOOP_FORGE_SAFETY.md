# Loop Forge safety boundary

Status: **active prototype / MODELED runtime**

Loop Forge is promoted into the first three holographic surface entries because
it demonstrates a central safety pattern: the proposer and the referee are
separate, recursion is bounded, and a failed invariant stops a branch instead of
rewarding it.

## Enforced structure

- The proposer cannot name or mutate the kernel referee.
- The referee evaluates bounded candidate branches against explicit invariants.
- Only referee-accepted branches enter the archive.
- Recursion depth and diff size are capped.
- Lambda uniqueness remains **Conjecture 1**, open, machine-checked false, and
  rendered gray.
- Receipts are signed only when a real signer is present; otherwise they remain
  honestly unsigned.

This structure is designed to reduce reward hacking by preventing the component
being optimized from also assigning its own acceptance score. It does not prove
that every reward-hacking strategy is impossible.

## Honest runtime limits

- The workspace readout and reward signals are **MODELED**.
- The runtime does not inspect neural activations and does not imply
  consciousness.
- Commit `c7c0ba17` identifies the cited Lean authority, but the Lean kernel is
  not executed in the hosted surface.
- A Python invariant check is not a substitute for running the cited formal
  proof toolchain.
- A kernel-accepted proof horizon is a governed throughput signal, not a
  universal safety score.

## Operator interpretation

A green branch means only that the branch passed the implemented referee checks
for that modeled cycle. It does not establish correctness beyond those checks.
An invariant breach must remain rejected, visible, and receipted; the surface
must not convert a denial into a warning to preserve throughput.
