# SZL-Forge sovereign model family

SZL-Forge is a release design built around one pinned Qwen2.5-derived base and five
governed adapter profiles. None is currently a promoted, independently qualified
release. ReceiptAgent and BrainNavigator have exact local runtime tags and signed
local turn receipts, but their published weight identities are not cryptographically
reconciled to the declared release artifacts. Operator, Sentinel, and Anatomy still
require admitted curricula and frozen evaluation; their current `szl1:latest` route
is an explicit shared fallback, not evidence of profile-specific weights. SZL-Forge
is not an independently pretrained foundation model and must not be marketed as one.

| Profile | Product surface | Weight status | Primary job |
|---|---|---|---|
| ReceiptAgent | A11oy governance | `receiptagent:latest` observed locally; signed local turn verified; release-artifact digest conflict; not promoted | Evidence-bound drafts and abstentions carried by an external signed runtime receipt; the model is not the signer |
| BrainNavigator | Brain / Khipu | `khipu:latest` observed locally; signed grounded turn verified; release-artifact digest conflict; not promoted | Graph retrieval, contradiction, and evidence paths |
| Operator | a-11-oy.com / a11oy.net | Planned adapter; `szl1:latest` is a shared fallback only | Governed API and tool routing |
| Sentinel | Killinchu + Immune | Planned adapter; `szl1:latest` is a shared fallback only | Defensive triage and proposal-only remediation |
| Anatomy | Body / Anatomy v5-v6 | Planned adapter; `szl1:latest` is a shared fallback only | Dependency and digital-twin reasoning |

Holographic is the shared three-dimensional interface, not a sixth adapter. It
visualizes the state and receipts of every profile while remaining replaceable
and independently testable.

Yupaq is the shared governed computation plane, also not an adapter. It gives
Operator and BrainNavigator a strict way to request Quant, numerical,
Lean/mathlib, formula, Lambda, Brain, and Lake operations without teaching the
model to impersonate those engines. See `docs/SZL_YUPAQ_COMPUTE_PLANE.md`.

Khipu Second Brain is a compound model surface, not a claim that an index is a
weight artifact. It combines the BrainNavigator runtime profile, persistent hybrid
evidence memory, a handles-only controller, cited-evidence-or-abstain behavior, and
external signed turn receipts. A measured local seed build contained 29 files, 290
chunks, 629 graph nodes, and 670 edges and was rehydrated from SQLite after restart.
That seed index is distinct from the canonical 9,464-node Brain inventory. Its local
state is experimental and artifact-unbound; it does not establish that the full
canonical inventory is indexed, that a public deployment runs this build, or that
the navigator weights are a promoted release. The runtime boundary is exposed at
`GET /api/a11oy/v1/ayllu/second-brain` and versioned in
`model_release/szl-khipu-second-brain.json`.

## How all 9,464 Brain nodes participate

The canonical inventory records 9,464 raw nodes that may participate in the Brain's
retrieval and evaluation workflows. This inventory count must not be confused with
the smaller, separately receipted local Second Brain seed index. No raw node is
silently copied into gradients.

The fail-closed admission engine in `szl_brain_training_admission.py` is now
implemented and covered by focused regression tests. It evaluates bounded,
caller-supplied candidate rows against content hashes, pinned source evidence,
rights and license evidence, freshness, deterministic deduplication, contamination,
and immutable train/eval assignment. Those tests establish gate behavior on test
fixtures; they do not establish admission of the canonical Brain corpus. The current
9,464 raw rows remain quarantined, zero rows are admitted to gradients, and no
training run was started.

Training admission is no longer allowed to trust a candidate's own JSON assertions.
Every source, rights, and contamination statement must be Ed25519-signed by an
allowlisted issuer/tool/key triple and must bind the exact content, source URI, and
immutable revision. TRAIN additionally requires a frozen protected-evaluation hash
set and a signed deterministic prior-run split ledger. Cross-run row reuse or split
migration fails closed. These controls make a future gradient tranche possible; they
do not manufacture rights for the present 9,464 harvested metadata rows.

This keeps Khipu continuously useful while its trainable tranche grows.

The measured local turn summary is recorded in
`attestations/forge-second-brain-local-2026-07-15.json`. Its DSSE verification key
was process-boot-ephemeral, so the record proves only the scoped local run. It is not
an organization-identity signature, a transparency-log entry, or evidence of the
current state of a later process boot.

## How APIs and free inference participate

External inference is a council, not an oracle. Provider outputs may propose
synthetic exercises, critique a draft, or act as evaluation comparators. They
become training rows only when the provider terms permit reuse and the exact
provider, model, terms snapshot, prompt, output, rights basis, admission, and
split are recorded. Private evidence and secrets never leave the sovereign
boundary.

Runtime APIs stay outside weights. Operator and the other profiles propose
tool calls; A11oy validates arguments, checks policy and approval, executes the
tool, observes the result, and emits the signed receipt.

## Compute allocation

The CPU mesh performs ingestion, parsing, deduplication, redaction, schema
validation, hashing, graph building, admission, and evaluation. The laptop GPU
is reserved for bounded QLoRA, clean reload inference, and measured evaluation.
OpenTelemetry ties each stage to code, data, base, adapter, hardware, thermal,
latency, and failure receipts.

Ouroboros, the Codex worker roles, the invariant gate, Lambda, the formula
registry, Lean/mathlib, Lake, OTel, Immune, and execution approval remain
outside weights. The adapter may learn to propose their typed contracts only
from admitted project-authored rows. This separation is the system's safety and
commercial boundary, not a limitation to hide.

The family registry is `model_release/szl-forge-family.json`. Its states are
release gates, not marketing labels.

## Ayllu council binding

Ayllu is the governed council around the family, not an eleventh adapter and not
eleven separate models. Every persona turn receives a profile-intent contract while
the actual model remains the one named by the runtime router and per-turn receipt.
Yupaq and the other roles may draft allowlisted compute proposals; direct tool
dispatch, execution, approval, signing, and self-certification remain disabled.

The runtime binding is exposed at
`GET /api/a11oy/v1/ayllu/model-binding` and versioned in
`model_release/szl-ayllu-binding.json`.
