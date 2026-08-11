# Architecture

## Trusted computing base

The trusted computing base is deliberately smaller than the model stack:

1. canonical encoding and digests;
2. exact schema and epoch bindings;
3. capability and budget authorization;
4. Fourfold signature/commitment verification;
5. deterministic settlement and release state transitions;
6. idempotency reservation;
7. atomic executor and postcondition verifier;
8. receipt signer, event chain, and transparency verifier.

Model responses, retrieved text, MCP/A2A messages, policy recommendations, and UI state are untrusted inputs until admitted by those controls.

## Planes

### Constitution

Four roles cover different failure axes:

- Authority: legal/organizational permission.
- Sentinel: abuse, security, and unacceptable harm.
- Verifier: objective proof and postcondition sufficiency.
- Value: expected outcome and opportunity cost.

Commitments seal before reveals. A key cannot occupy multiple roles. Identity declarations are measured across eight correlation axes. A valid veto is not a weighted vote.

### Authority

The Autonomy Envelope and Capability Grant jointly authorize action. Authorization is an intersection, never a union:

```text
allowed = grant ∩ envelope ∩ policy ∩ current epoch ∩ current budget
```

Child grants must be provably narrower than their parent.

### State

The State Bus stores canonical protocol records and their digests. Every event binds its payload digest, predecessor hash, sequence, case, event type, and timestamp. Object and event verification is offline-capable.

### Effect

The reference executor supports one low-risk data plane: atomic operations beneath a configured sandbox directory. It captures the preimage, writes through a temporary file, fsyncs, verifies postconditions, and restores the preimage if verification fails.

Provider-specific production effectors must preserve the same contract: reservation, exact target, request digest, provider idempotency/reconciliation, independent read-back, and compensation evidence.

### Proof

Receipts are separate from chain integrity. A receipt is labeled signed only after Ed25519 self-verification. The local Merkle log proves inclusion mechanics but is not represented as independent public transparency.

### Projection

OpenTelemetry and A11oy receive redacted read-only projections. They see IDs, digests, reason codes, status, budget, and evidence counts—not raw prompts, private reasoning, credentials, or unrestricted evidence.

## Cognitive epoch binding

A run binds exact model, tokenizer, prompt/template, tool, policy, evidence, retrieval, and state schema epochs. A changed epoch creates a new decision context; it does not silently inherit prior verification.

## Portability levels

- P0 transcript-only: informational, not authoritative.
- P1 structured state: claims, evidence, actions, status.
- P2 replayable state: deterministic events and external-call receipts.
- P3 portable state: model-independent ABI and migrations.
- P4 independently verifiable state: signatures, transparency, witness, and postcondition proofs.

The local implementation reaches P2 and demonstrates local P4 mechanics. Production P4 remains gated on external identities, custody, monitors, and read-back.
