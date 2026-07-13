# SZL-Forge sovereign model family

SZL-Forge is one pinned Qwen2.5-derived base with five governed adapter profiles.
None is currently a promoted, independently qualified release: ReceiptAgent has a
hardened training path, while the other four still require admitted curricula and
frozen evaluation. It is not an independently pretrained foundation model, and it
must not be marketed as one.

| Profile | Product surface | Weight status | Primary job |
|---|---|---|---|
| ReceiptAgent | A11oy governance | Not trained; hardened path ready | Evidence-bound unsigned drafts and abstention |
| BrainNavigator | Brain / Khipu | Planned | Graph retrieval, contradiction, and evidence paths |
| Operator | a-11-oy.com / a11oy.net | Planned | Governed API and tool routing |
| Sentinel | Killinchu + Immune | Planned | Defensive triage and proposal-only remediation |
| Anatomy | Body / Anatomy v5-v6 | Planned | Dependency and digital-twin reasoning |

Holographic is the shared three-dimensional interface, not a sixth adapter. It
visualizes the state and receipts of every profile while remaining replaceable
and independently testable.

Yupaq is the shared governed computation plane, also not an adapter. It gives
Operator and BrainNavigator a strict way to request Quant, numerical,
Lean/mathlib, formula, Lambda, Brain, and Lake operations without teaching the
model to impersonate those engines. See `docs/SZL_YUPAQ_COMPUTE_PLANE.md`.

## How all 9,464 Brain nodes participate

All current raw nodes can be indexed, retrieved, contradicted, freshness
scored, and used in evaluation. None is silently copied into gradients. A
separate admission pipeline must convert eligible evidence into
content-addressed graph-navigation exercises with rights, provenance,
deduplication, contamination analysis, and immutable train/eval assignments.

This keeps Khipu continuously useful while its trainable tranche grows.

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
