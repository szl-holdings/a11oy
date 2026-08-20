# SZL-Forge: One Product, Explicit Components

SZL-Forge should be presented as one governed product experience, not as one fictional checkpoint and not as a wall of card-only repositories.

The machine-readable contract is [`model_release/szl-forge-compound-product.json`](../model_release/szl-forge-compound-product.json). Its schema and fail-closed tests are:

- [`model_release/szl-forge-compound-product.schema.json`](../model_release/szl-forge-compound-product.schema.json)
- [`tests/test_szl_forge_compound_product.py`](../tests/test_szl_forge_compound_product.py)

## Canonical public shape

The public entrypoint is a single proposed Hugging Face Space, `SZLHOLDINGS/SZL-Forge`. It identifies the requested profile, exact model tag actually served, evidence set, citations, receipt, readiness, and every blocking condition. A canonical `SZLHOLDINGS/SZL-Forge-Collection` is created last and inventories the independently typed artifacts.

Only two current components are weight-bearing model profiles:

| Profile | Exact local tag | Weight relation | Current boundary |
|---|---|---|---|
| ReceiptAgent | `receiptagent:latest` | PEFT adapter plus exact Qwen2.5 base | Local exact-tag turn verified; remote adapter binding still conflicts |
| Khipu BrainNavigator | `khipu:latest` | PEFT adapter plus exact Qwen2.5 base | Local grounded exact-tag turn verified; remote adapter binding still conflicts |

Everything else remains outside weights:

- Khipu evidence memory is a versioned retrieval and graph plane;
- Ouroboros is the controller loop;
- Ayllu is bounded role orchestration, not eleven invented models;
- Invariant, GovSign, and ProvCtl are policy, signing, and provenance controls;
- the Lake, Lean/mathlib, Yupaq, and formulas are evidence, computation, and independent checking;
- the inference meter and OpenTelemetry are observability and receipt infrastructure.

That composition is stronger than forcing unrelated code, indexes, and rules into gradients: every plane can be versioned, tested, replaced, and independently refused.

## Current evidence

The retained loopback receipt at `attestations/forge-second-brain-live-2026-07-15.json` has SHA-256 `0cfc363216624561f8faa080908fef4757db8267c40dafe07526b1cc502c9d8a`. It verifies one grounded Khipu turn, one ReceiptAgent turn, both exact served tags, signed runtime envelopes, and a 9,464-handle Brain plane. It does not establish training completion, remote Hub artifact identity, production readiness, or benchmark quality. The 9,464 raw Brain rows remain outside gradients.

## Repository consolidation

The eight screenshot-named Hub repositories are migration inputs, not eight model checkpoints. The contract maps each to its correct semantic type and requires preservation before any deprecation:

| Current Hub identifier | Actual role | Consolidation destination |
|---|---|---|
| `a11oy-v19-substrate` | software and diligence mirror | SZL-Forge observability/product assets |
| `governed-inference-meter` | runtime telemetry software | receipt and observability plane |
| `szl-blocked` | quarantine/blocker ledger | private or rights-reviewed dataset |
| `szl-govsign` | signing and verification software | invariant/provenance policy plane |
| `szl-provctl` | provenance controls | invariant/provenance policy plane |
| `szl-invariants` | rules and test fixtures | dataset or software library |
| `szl-ouroboros` | orchestration software | Ouroboros controller |
| `szl-formulas` | formula data and compute tooling | formal-compute plane |

No source is deleted. Before a model card is deprecated, the workflow must perform live Hub readback, download and hash all files and LFS objects, scan for secrets/private data, create the correctly typed destination, verify unauthenticated readback, and add a canonical link to the old card.

## Promotion rule

The local runtime pass is necessary but not sufficient. Public promotion remains blocked until:

1. remote adapter, base, tokenizer, and LFS digests reconcile;
2. model and dataset licenses and derivative lineage pass review;
3. frozen role-specific held-out evaluations pass;
4. grounding, citation, abstention, security, rights, and contamination gates pass;
5. resource, restart, and recovery receipts pass;
6. a durable release-scoped signing identity and transparency entry exist;
7. the public Space, collection, and every member pass unauthenticated readback; and
8. a human signs the release decision.

The contract makes no promise of downloads, publicity, commercial success, wealth, or fame. It does make the product legible: one entrypoint, two honestly identified model profiles, explicit external planes, and evidence at every boundary.
