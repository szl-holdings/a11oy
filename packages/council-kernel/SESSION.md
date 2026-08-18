# Blinded Council sessions

`CouncilSession` binds one proposal to a fixed roster, fixed grants, and bounded commit and reveal windows.

## Commit phase

Only roster members may submit. A member may repeat the same commitment idempotently, but cannot replace it with another digest. Commitments after the deadline are denied.

## Reveal phase

The commit phase is explicitly sealed before any reveal is accepted. A reveal must:

- identify a fixed-roster member;
- have a prior commitment;
- match the committed member, assessment, and nonce;
- arrive before the reveal deadline.

A member may repeat the same reveal idempotently, but cannot replace its content.

## Decision phase

The session cannot compile an early decision while any fixed-roster member can still reveal. It may decide early only after the entire roster has revealed, or at/after the reveal deadline with the evidence actually received.

Missing roles, evidence, or independence are then handled by the deterministic kernel as `ESCALATE` or `BLOCK`; the session never manufactures a missing vote.

## Closure

After one decision, the session becomes `DECIDED`, then may be sealed `CLOSED`. Every transition is appended to the hash-chain ledger. The session snapshot binds roster, commitments, reveals, deadlines, proposal, phase, and decision identity.
