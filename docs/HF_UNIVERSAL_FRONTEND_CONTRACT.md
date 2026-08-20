# SZLHOLDINGS universal frontend estate contract

## Purpose

This control plane normalizes the public Hugging Face presentation layer without converting presentation into evidence. It may update supported model and dataset cards through revision-bound Hub pull requests. Spaces are classified from immutable source-map evidence and are never written directly by this controller.

## Control-plane separation

Automatic pull-request, protected-main, and scheduled execution is read-only and limited to controller qualification. `hf-sync.yml` remains the sole automatic canonical Hugging Face writer.

Estate planning and provider mutation live in a separate `workflow_dispatch`-only workflow:

- `operation=plan` inventories the public estate and produces immutable evidence without requiring provider credentials or changing any provider resource;
- `operation=execute` requires explicit owner dispatch plus the managed organization token and may create and merge only revision-bound Hugging Face pull requests for supported assets.

Both operations inventory only anonymously visible repositories and require an explicit public visibility flag before admission. They are restricted to `refs/heads/main`: the workflow checks that the dispatched SHA, checked-out SHA, and current protected-main SHA agree after checkout. Execution checks again before every provider create/merge and before every deterministic issue write. A stale or non-main dispatch fails closed. Python dependencies are installed only from committed hash-locked requirement files.

## Canonical boundaries

The owner-dispatched rollout may:

- preserve existing YAML frontmatter;
- insert or replace one idempotent managed card section;
- create Hugging Face pull requests from an exact observed parent revision;
- merge those pull requests only inside the manually dispatched execution job;
- archive every changed preimage and resulting revision;
- verify every changed path byte-for-byte at the immutable resulting revision before labeling the merge verified.

The rollout must never:

- edit model weights, tokenizer artifacts, dataset rows, dataset schemas, or dataset splits;
- change repository visibility, hardware, persistent storage, secrets, variables, allocation, or billing state;
- delete repositories or application files;
- write any Space directly on the Hub, including a Space whose source authority is missing, stale, inferred, divergent, or unavailable;
- claim model quality, training provenance, cryptographic signing, runtime parity, or production readiness from a card or reachable URL;
- hardcode organization-wide asset totals into public cards.

## Source authority

The only accepted Space authority input is `docs/huggingface-space-source-map-v1.json` with schema `szl.hf-space-source-map/v1`. The controller validates its organization, read-only boundary, unique Space identities, revision-bound README evidence, immutable Hugging Face revisions, mapping states, and canonical GitHub revisions. Exact or inferred canonical revisions must match one candidate and the workflow evidence revision. The map must cover the complete anonymous public Space inventory with exact identities and revisions before any model or dataset mutation is admitted.

- `EXACT` is source-bound and read-only. The controller independently compares the revision-bound README hash and canonical adapter bytes without a provider token. An exact, already-repaired Space may end in `SOURCE_BOUND_VERIFIED`; any byte drift remains `SOURCE_BOUND_REPAIR_REQUIRED` and must be repaired in the recorded canonical repository at a newly reviewed revision.
- `INFERRED` requires owner review and remains non-writable.
- `DIVERGENT` and `UNAVAILABLE` remain blocked.
- a missing entry or a Hugging Face revision that differs from the map is blocked as missing or stale evidence.

No state in source-map v1 grants direct Space Hub-write authority. A future Hub-native path would require an explicit reviewed schema state; absence of source evidence is never treated as permission.

## Responsive contract

Source-native application repairs may reuse the framework-local stylesheet adapters, which enforce:

- a viewport contract for static HTML;
- 44-pixel minimum interactive targets;
- auto-fitting card grids and one-column mobile actions;
- safe wrapping for hashes, revisions, receipts, and evidence identifiers;
- visible keyboard focus;
- reduced-motion behavior;
- zero horizontal overflow caused by technical identifiers;
- no runtime CDN dependency.

The Hub controller does not apply these adapters to Spaces. Python adapters preserve shebangs, encoding declarations, module docstrings, and `__future__` imports and parse generated source before use. Existing Gradio `css=` integrations, multiline Streamlit page configuration, and all ambiguous source mappings require source-native review.

## Transaction and evidence

Before processing any mutable asset, the controller validates the complete public Space inventory and computes every Space decision through anonymous revision-bound reads. Model and dataset writes remain disabled unless every Space is terminally `SOURCE_BOUND_VERIFIED`.

For each eligible mutable asset the controller:

1. resolves the exact current `main` SHA;
2. inventories repository files at that SHA;
3. records every preimage that would change;
4. generates deterministic card/application changes;
5. creates a Hugging Face pull request with `parent_commit` bound to the observed SHA;
6. merges the pull request only during explicit owner execution;
7. requires a new immutable `main` SHA and reads every changed path back at that revision;
8. writes a machine-readable report and rollback preimages.

An unrepaired source-bound, unmapped, stale, or unsupported asset remains a blocker in the estate report. Duplicate deterministic issues are an error rather than an arbitrary first-match update. Issue synchronization occurs only after immutable rollout evidence uploads successfully, then rechecks exact current main before each issue write. The manual execution job keeps the unique issue open until every mutable asset is current and every Space is verified at its exact source-bound revision.

## Release decision

The estate may be called complete only when an owner-dispatched execution report contains:

```json
{
  "complete": true,
  "blocked_assets": [],
  "failed_assets": []
}
```

The report is completion-eligible only for `operation=execute` with merge enabled. Every model and dataset must end in `CURRENT` or `MERGED_VERIFIED`, while every Space must end in read-only `SOURCE_BOUND_VERIFIED` with an exact mapping, canonical source revision, zero changes, and zero blockers. A source merge, successful plan, pending pull request, partial card rollout, readback mismatch, or reachable URL is not an estate-wide production-verification claim.
