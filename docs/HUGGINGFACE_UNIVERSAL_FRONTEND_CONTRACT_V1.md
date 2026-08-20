# Hugging Face Universal Frontend Contract v1

## Purpose

This contract governs the public `SZLHOLDINGS` Hugging Face estate from the organization card through every Space, model card, dataset card, kernel/verifier surface, collection, and public evidence link.

The contract is a release gate, not a visual mood board. A polished surface may not imply runtime readiness, source alignment, signing, model quality, or production status without the corresponding evidence.

## Canonical hierarchy

1. `SZLHOLDINGS/README` is the organization front door.
2. `SZLHOLDINGS/a11oy` is the canonical governed-inference application front door.
3. Models, datasets, kernels, and collections link to their canonical Hub resources rather than copying estate-wide counts.
4. Each Space retains one source repository, one deployment writer, one immutable served revision, and one rollback path.
5. Duplicate demo front doors are consolidated into product planes or explicitly labeled archives.

## Universal viewport contract

Every rendered application and organization-card surface must pass at 360, 390, 768, 1024, and 1440 CSS pixels.

Required invariants:

- `<meta name="viewport" content="width=device-width, initial-scale=1">` or an equivalent safe viewport declaration.
- No document-level horizontal overflow.
- Fluid type and spacing; fixed desktop-only widths are prohibited.
- Flex and grid children that contain hashes, revisions, URLs, or evidence identifiers use `min-width: 0`.
- Long technical identifiers use safe wrapping such as `overflow-wrap: anywhere`.
- Interactive targets are at least 44 by 44 CSS pixels.
- Primary actions stack or remain fully visible at narrow widths.
- Tables provide a mobile card, scroll, or disclosure fallback.
- Keyboard focus is visible and logical.
- Color is never the sole status signal.
- `prefers-reduced-motion` disables nonessential animation.
- Three-dimensional and canvas views expose a two-dimensional fallback and never fabricate live data.

## Card metadata contract

### Organization card and Spaces

- `title`, `emoji`, `sdk`, `app_file`, and a concise `short_description` are explicit.
- `short_description` is no more than 60 characters.
- The card identifies the canonical source repository and immutable deployment revision when available.
- Runtime state, source alignment, signer state, and readiness are separate fields.
- Hardcoded organization-wide asset totals are prohibited on product pages; link to the canonical Hub inventory instead.

### Models and kernels

- License, intended use, excluded use, source revision, artifact digest, evaluation boundary, and runtime status are explicit.
- A repository or model card may not claim trained, production-ready, signed, verified, or state-of-the-art without admissible evidence.
- Kernel/verifier assets distinguish proof status from software packaging and runtime deployment.

### Datasets

- License, source/provenance, schema, collection method, update cadence, limitations, and personally identifiable information policy are explicit.
- Synthetic, sampled, modeled, and measured records are labeled separately.

### Collections

- Each collection has one purpose and a bounded membership policy.
- Overlapping launchpad, proof, archive, and product collections are consolidated rather than multiplied.

## Evidence vocabulary

Allowed public states include:

- `OBSERVED`
- `MEASURED`
- `VERIFIED`
- `HASH-LINKED`
- `SIGNED`
- `UNSIGNED`
- `SIMULATED`
- `MODELED`
- `EXPERIMENTAL`
- `DIVERGENT`
- `UNAVAILABLE`
- `BLOCKED`

`SIGNED` is permitted only when a persistent signer is active and signature verification passes. Hash-chain integrity is not a cryptographic signature. Reachability is not source/runtime alignment. A high advisory score is not an authorization decision.

## Source and deployment binding

A frontend promotion is complete only when all applicable values agree:

```text
protected source SHA
+ build input SHA
+ Hub repository revision
+ served runtime revision
+ public build-info revision
+ readiness verdict revision
+ rollback reference
```

If any value is absent or divergent, the surface remains explicitly unverified.

## Rollout order

1. Refresh the public estate manifest.
2. Generate the remediation queue from observed evidence.
3. Repair the organization card and one flagship canary.
4. Verify all five viewport classes and source/runtime parity.
5. Promote framework-native adapters for Static, Gradio, Streamlit, React, and Docker Spaces.
6. Repair model and dataset cards without altering weights or data.
7. Consolidate collections only after replacement memberships are reviewed.
8. Close each queue item only after immutable live readback.

## Mutation boundary

Frontend modernization does not, by itself, authorize changes to model weights, datasets, secrets, hardware, storage, visibility, signer keys, branch protection, or training state.
