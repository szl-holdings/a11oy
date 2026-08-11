# A11oy Council / Alloy Council Kernel v0.5.0rc1

> Models propose. The kernel authorizes, verifies, settles, and preserves dissent.

The Alloy Council Kernel is a **proof-carrying autonomy kernel** for bounded agent action. It turns a proposed action into an exact authority envelope, a signed Fourfold decision, an empirical release decision, an idempotent reversible mutation, machine-checked postconditions, a signed receipt, and a portable evidence trail.

This is not a monolithic “council model.” The deterministic kernel remains the trusted control plane; models are replaceable specialists operating inside its contracts.

## What is implemented

- **Fourfold Constitution:** Authority, Sentinel, Verifier, and Value identities use signed blinded commit/reveal. The coordinator has no vote. Sentinel and Verifier vetoes are categorical. Correlated replicas fail closed. Signed opposition and counterevidence enter the Minority Truth Vault.
- **Autonomy Envelope:** exact principal, targets, capabilities, tools, risk, blast radius, budgets, epochs, pre/postconditions, idempotency, retry, rollback, expiry, and release obligations.
- **Capability plane:** monotonic attenuation, exact-target matching, grant expiry/revocation, and budget accounting.
- **State Bus:** content-addressed objects, append-only SQLite event chain, deterministic transitions, idempotency reservations, receipts, negative capabilities, outcomes, and evidence export.
- **Execution plane:** atomic UTF-8 file write/append/delete inside one explicit sandbox root. Traversal and symlinks are rejected. Failed postconditions trigger exact preimage restoration.
- **Proof plane:** Ed25519 DSSE-style signatures, self-verification, signed receipt chain, and a local Merkle transparency reference log with portable inclusion proofs.
- **Frontier release logic:** effective epistemic council size, bounded branch scoring, empirical ACT/ESCALATE/BLOCK gate, negative capability guard, delayed outcome contracts, and research quarantine.
- **Interop boundaries:** narrow MCP, A2A, OPA, Temporal, and SPIFFE adapters. None become the root of trust.
- **Operations:** deterministic canary, 24-scenario adversarial CouncilBench, 18 strict Draft 2020-12 JSON Schemas, read-mostly FastAPI service, accessible responsive operator console, and deterministic release verification tooling.

## Quick start

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[test,api]'

alloy-council canary \
  --workdir ./run/canary \
  --output ./evidence/COUNCIL_CANARY.json

alloy-council bench \
  --output ./evidence/COUNCIL_BENCH.json

alloy-council verify-ledger \
  --db ./run/canary/council.sqlite3 \
  --output ./evidence/LEDGER_VERIFICATION.json
```

Run the complete local gate:

```bash
make verify
```

Build a deterministic, manifest-bound source archive:

```bash
python tools/build_release.py . \
  --output ../SZL_COUNCIL_KERNEL_FRONTIER_SOURCE.zip \
  --report ../SOURCE_ARCHIVE_VERIFICATION.json
```

The tag-triggered release-candidate workflow repeats the wheel and source builds byte-for-byte, generates a CycloneDX SBOM, creates GitHub provenance and SBOM attestations, and uploads only verified artifacts. It does not publish to PyPI, merge a branch, deploy a service, or grant runtime autonomy.

## Execute a bounded local action

`run-local` is an actual sandbox mutation path, but its four specialist identities are deterministic test identities. That boundary is explicit and it never establishes production independence.

```bash
alloy-council run-local \
  --input examples/local_action_spec.json \
  --db ./run/local/council.sqlite3 \
  --sandbox ./run/local/sandbox \
  --signing-key ./run/local/receipt-ed25519.key \
  --allow-local-test-council \
  --output ./evidence/LOCAL_ACTION_RUN.json
```

The sample writes only `workspace/frontier.txt` beneath the configured sandbox. The receipt signer is persistent and mode-checked. The Fourfold specialists remain test-only.

## Serve the read-only console

```bash
alloy-council serve \
  --db ./run/canary/council.sqlite3 \
  --runtime-root ./run/api \
  --host 127.0.0.1 \
  --port 8765
```

Open `http://127.0.0.1:8765`. The console derives state from ledger evidence and has no authority to write `verified`.

Detailed case and evidence routes require `ALLOY_COUNCIL_READ_TOKEN`; mutation remains disabled unless `ALLOY_COUNCIL_ADMIN_TOKEN` is set. Tokens must contain at least 32 bytes. Even when enabled, the mutation endpoint runs only the packaged local sandbox canary.

## Decision pipeline

```text
signal
  → immutable case + cognitive epochs
  → evidence manifest
  → proof-carrying deliberation graph
  → signed Fourfold commit/reveal
  → epistemic diversity compiler
  → empirical ACT / ESCALATE / BLOCK gate
  → capability-bound idempotent action
  → postcondition verification
  → compensation on failure
  → signed receipt + local transparency inclusion
  → delayed outcome contract
  → governed learning candidate
```

## Kernel versus model

Build the kernel first. Train specialist models only after the system has rights-cleared traces, objective verifier outcomes, adversarial benchmarks, and delayed outcome settlements.

Suggested model family:

1. Governor/router.
2. Sentinel.
3. Verifier ensemble.
4. Value/outcome model.
5. State codec.
6. Drift sentinel.
7. Domain adapters.

Models may recommend policies, branches, or evidence. They cannot mint capabilities, mark their own work verified, override a veto, rewrite prior receipts, or promote themselves.

## Production activation boundary

The local release candidate proves source-level behavior and local cryptographic mechanics. It does **not** prove:

- four independently administered operators or organizations;
- production SPIFFE trust-domain separation;
- managed KMS/HSM key custody and rotation;
- public SCITT/RFC 9162 transparency service or independent monitor gossip;
- real provider/model independence;
- authenticated GitHub or Hugging Face publication;
- external deployment, live negative tests, or production read-back;
- formal statistical coverage for the empirical gate; or
- production A3/A4 autonomy.

Those gates are defined in [`docs/PRODUCTION_ACTIVATION.md`](docs/PRODUCTION_ACTIVATION.md). Until they pass, the truthful state is `LOCAL_KERNEL_AND_SANDBOX_EXECUTION_ONLY`.

## Repository map

```text
src/szl_council_kernel/
  fourfold.py            signed commit/reveal and settlement
  capability.py          attenuation, exact targets, budgets
  state_bus.py           content-addressed durable state
  executor.py            atomic reversible sandbox effects
  workflow.py            deterministic end-to-end kernel
  proof.py               Ed25519 DSSE-style statements
  merkle.py              local transparency inclusion proofs
  deliberation.py        typed graph and Minority Truth Vault
  diversity.py           correlation axes and N_eff
  gate.py                empirical act/escalate/block layer
  branches.py            bounded counterfactual branch market
  negative_capability.py known inability ledger
  outcome.py             delayed value settlement
  foundry.py             research quarantine and lineage
  adapters/              OPA, MCP, A2A, SPIFFE, Temporal boundaries
  schema_registry.py      18 strict public protocol schemas
  service.py + web/      read-only API and console
```

## Non-negotiable laws

1. No model self-authorizes.
2. No action without an exact target and bounded capability.
3. No mutating envelope without postconditions and rollback authority.
4. No majority override of a valid Sentinel or Verifier veto.
5. No diversity claim without measured correlation axes.
6. No hidden rewrite of dissent, events, or receipts.
7. No protocol storage of private chain-of-thought, credentials, or raw system prompts.
8. No learning promotion without rights, reproducibility, benchmark evidence, and Fourfold settlement.
9. No presentation-layer write to `verified`.
10. No production-autonomy claim without independent live evidence.
