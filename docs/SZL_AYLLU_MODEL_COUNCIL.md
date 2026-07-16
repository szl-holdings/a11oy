# Ayllu as the council around SZL-Forge

Ayllu is contractually bound to `SZL-Forge-1.5B` as a governed runtime council.
The eleven names are task roles and system-prompt contracts routed through one
A11oy controller. They are not eleven separately trained models. Profile-aware
local routing now expects `receiptagent:latest` for ReceiptAgent,
`khipu:latest` for BrainNavigator, and the explicit shared `szl1:latest` fallback
for Operator, Sentinel, and Anatomy. A configured or observed tag is not proof that
the corresponding release artifact loaded.

Every turn binds independent runtime facts:

1. persona and intended Forge profile;
2. the expected tag, actual routed model, and available exact-tag attestation for
   that turn;
3. the allowlisted proposal surfaces and Yupaq compute operations;
4. binding and turn-output digests included in the ask or council receipt; and
5. for grounded turns, the evidence-set and grounding digests used by the
   controller.

The state is `PROFILE_AWARE_LOCAL_ROUTING_ARTIFACT_BINDING_PARTIAL`. Exact local
tags were observed for ReceiptAgent and BrainNavigator, and independently checked
local DSSE turn envelopes verified. Their release artifact identities remain
unbound or in conflict, however. Promotion to a pinned state still requires a
model-load receipt binding the base revision, adapter SHA-256, local weight/blob
identity, served identity, immutable published artifact identities, reconciliation
of those identities, and clean reload evaluation.

## Authority boundary

The model may propose. It may not execute an external action, approve its own
proposal, sign evidence, or certify its own correctness. The current Ayllu loop has
zero effectors and `tool_dispatch=false`.

The runtime may wrap a turn in a signed receipt; that does not give the model signing
authority. The locally verified July 15 receipts used a process-boot-ephemeral key
served at `/api/a11oy/cosign.pub`. They prove the scoped local envelopes only and are
not organization-identity signatures or transparency-log records.

Ask and council responses are returned only to the caller and are not
automatically copied into the public lounge. Stateful Yupaq job and receipt routes
require a bearer whose SHA-256 is configured in the approved secret store; the
raw bearer is never stored in release metadata.

Yupaq can draft only operations listed by the computation plane. A human or an
independent authorized controller must submit the typed request to the compute API;
the compute plane validates the schema and preserves the engine's own honesty state.

## Khipu Second Brain boundary

The Second Brain is a compound governed system: the BrainNavigator profile proposes
retrieval navigation, the controller keeps raw evidence content outside the model,
and grounded turns receive bounded handles and synthetic metadata. The answer policy
is cited evidence or abstention; the model cannot write canonical memory or certify
its own grounding.

A measured local seed index contained 29 files, 290 chunks, 629 graph nodes, and 670
edges and rehydrated from SQLite after restart. It is not the canonical 9,464-node
Brain inventory, and the local measurement does not imply that the full inventory is
present in the compound model or deployed publicly.

`szl_brain_training_admission.py` now implements and tests the bounded row-level
admission gate. The canonical raw inventory has not passed that gate: zero rows are
admitted to gradients and no training run was started. Retrieval remains distinct
from training, and indexed nodes remain distinct from model parameters.

The gate now accepts only Ed25519-signed evidence from purpose-scoped
issuer/tool/key authorities. Source identity, author/rightsholder permission,
privacy/PII, review, and contamination claims bind the exact row content and
immutable source revision. The review signer must be bound to the declared reviewer.
Training admission is disabled by default; an explicit switch, frozen evaluation
hash set, root-signed policy bundle, exact policy-pinned cross-run split-ledger head,
and distinct artifact-signing key prevent contamination, replay, split migration,
and unsigned release output. Mutable key replacement and stale ledger envelopes fail
closed. Evaluation admission also requires the rooted policy and signed terminal
manifest; an unrooted run remains inspection-only quarantine. Quarantine records redact
content, raw node identifiers, source locations, evidence paths, and personal identities
instead of copying sensitive evidence into a denial artifact.

## Public surfaces

- `GET /api/a11oy/v1/ayllu/model-binding`
- `GET /api/a11oy/v1/ayllu/second-brain`
- `GET /api/a11oy/v1/ayllu/roster`
- `POST /api/a11oy/v1/ayllu/ask`
- `GET /api/a11oy/v1/ayllu/council/manifest`
- `POST /api/a11oy/v1/ayllu/council`
- `GET /api/a11oy/v1/compute/capabilities`
- `GET /api/a11oy/code/rag/status`
- `POST /api/a11oy/code/rag/query`
- `GET /api/a11oy/cosign.pub`

Canonical release metadata lives in `model_release/szl-ayllu-binding.json` and
`model_release/szl-khipu-second-brain.json`. These repository and local-runtime
statements do not establish that a public domain, Space, or production deployment
is running the same build.
