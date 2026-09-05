# Keeper-policy parser current-main successor

- `workcell_id`: `A11OY-KEEP-POLICY-CURRENT-MAIN-20260905`
- `source_base`: `94e129d016a7e82e0b22f11c00ea877b5cc430f5`
- `supersedes_candidate`: `#1992`
- `state`: `OPEN_REPAIR`

## Objective

Port only the reviewed three-file keeper-policy parser repair onto current protected main. The superseded branch absorbed unrelated #1986/runtime/publisher history and therefore no longer represents a three-file governance delta.

## Allowed implementation paths

- `scripts/hf_keep_policy.py`
- `tests/test_hf_keep_policy_continuations.py`
- `.github/workflows/public-estate-contract.yml`

## Required semantics

Admit only the supported sibling metadata and bounded nested-list forms; reject unsupported scalar continuations, orphan lists, metadata before the first keeper, and duplicate ID/metadata fields. Preserve canonical keeper-policy bytes and all unrelated current-main runtime/provider behavior.

## Acceptance

Exactly the three implementation paths above plus this append-only proof anchor; eight focused parser regressions; existing public-estate topology/generated-consumer checks retained; fresh exact-head hosted matrix and independent review. No provider mutation, credential, DNS, runtime, or publication authority change.
