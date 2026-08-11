# Lane 2 — Hugging Face Estate and Investor Front Door

## Mission

Audit and repair the complete `SZLHOLDINGS` Hugging Face estate and its GitHub-owned source surfaces so the organization is coherent, mobile-first, investor-readable, technically useful, and evidence-bound. Do not delete or retire assets merely because they are old. Do not patch Hugging Face manually when a canonical GitHub source and protected publisher exist.

## Scope

Cover every accessible:

- Space and runtime;
- model and model card;
- dataset and dataset card/viewer schema;
- collection and collection membership;
- kernel or kernel-manifest surface owned by the estate;
- organization front door and `SZLHOLDINGS/README` Space;
- GitHub source manifest, deployment manifest, and source/build/served identity evidence.

## Required lifecycle classification

Assign every asset exactly one state:

```text
ACTIVE
CANDIDATE
QUARANTINED
DEPRECATED
RETIRED
UNKNOWN
```

Record the reason and immutable revision. `UNKNOWN` is a blocker, not an acceptable final state.

## Required checks

1. Resolve current source-of-truth repository and exact commit for every mutable public surface.
2. Verify Space runtime stage, SDK, immutable revision, build status, broken links, missing files, and source/build/served parity.
3. Verify model cards for license, base-model lineage, task/pipeline metadata, file digests, quantization claims, evaluation receipts, rights/provenance, and explicit non-claims.
4. Verify dataset cards for license, schema/viewer health, provenance, source references, splits, PII/safety constraints, and collection membership.
5. Verify collections for broken, duplicated, stale, private, or missing entries.
6. Reconcile public counts from generated manifests rather than hand-edited prose.
7. Re-test the organization card and README Space at 320, 360, 390, 430, 768, 1024, and 1440 pixel widths under hostile host CSS.

## Investor-front-door contract

The first viewport must communicate, without hype:

- `SZL Holdings` builds governed operational intelligence;
- `Alloy` is the governed execution fabric;
- `Lyte` is the flagship command surface;
- domain products are separate application surfaces;
- evidence, runtime state, authorization, portfolio presence, and production readiness are distinct concepts.

The front door must provide clear mobile-accessible routes for Overview, Platform, Portfolio, Proof, and Investor content. All tabs and CTAs must remain visible and keyboard operable. No relative hero image, runtime CDN, external font, generic host-colliding selector, horizontal overflow, clipped tab, pathological whitespace, or unsupported operational/traction/regulatory claim is allowed.

## Publication rules

- Publish through the current protected GitHub workflow and managed Hugging Face authority.
- Never retrieve, print, rotate, or copy the Hugging Face token.
- Never overwrite a newer live source with an older package.
- Never publish an unmerged branch or PR head.
- Require exact merged-source binding, immutable Hub revision, `RUNNING` state, file readback, and live marker/browser verification before saying live.

## Acceptance criteria

```text
unclassified_assets == 0
broken_hf_references == 0
missing_required_cards == 0
undeclared_required_licenses == 0
modified_space_source_build_served_parity == PASS
organization_front_door_mobile_matrix == PASS
console_errors == 0
horizontal_overflow == 0
broken_requests == 0
public_count_drift == 0
completion_claims_without_receipts == 0
```

External quota, private authority, model rights, or hardware blockers must remain explicit and cannot be converted to green with copy changes.

## Deliverable

Create one or more signed+DCO PRs from current protected source repositories, avoiding cross-repository writer races. Run source validators, browser regressions, metadata/rights checks, and protected publication. Finish with exact PRs, merge SHAs, workflow runs, Hub revisions, deployment-manifest digest, responsive screenshots, asset lifecycle ledger, and residual external blockers.
