# SZLHOLDINGS universal frontend estate contract

## Purpose

This control plane normalizes the public Hugging Face presentation layer without converting presentation into evidence. It covers public model cards, dataset cards, eligible Space cards, and a bounded set of deterministic application shells.

## Control-plane separation

Automatic pull-request, protected-main, and scheduled execution is read-only and limited to controller qualification. `hf-sync.yml` remains the sole automatic canonical Hugging Face writer.

Estate planning and provider mutation live in a separate `workflow_dispatch`-only workflow:

- `operation=plan` inventories the public estate and produces immutable evidence without requiring provider credentials or changing any provider resource;
- `operation=execute` requires explicit owner dispatch from exact current protected `main` plus the managed organization token and may create and merge only revision-bound Hugging Face pull requests for supported assets.

Both operations derive their inventory anonymously and require an explicit public visibility flag before an asset is admitted. The managed token is used only after that public inventory is frozen, so private repositories cannot enter mutation evidence or blocker reports.

## Canonical boundaries

The owner-dispatched rollout may:

- preserve existing YAML frontmatter;
- insert or replace one idempotent managed card section;
- add mobile-safe CSS to static HTML, React, Gradio, and Streamlit shells when an exact source adapter succeeds;
- create Hugging Face pull requests from an exact observed parent revision;
- merge those pull requests only inside the manually dispatched execution job;
- archive every changed preimage and resulting revision.

The rollout must never:

- edit model weights, tokenizer artifacts, dataset rows, dataset schemas, or dataset splits;
- change repository visibility, hardware, persistent storage, secrets, variables, allocation, or billing state;
- delete repositories or application files;
- overwrite a GitHub-source-bound Space directly on the Hub;
- claim model quality, training provenance, cryptographic signing, runtime parity, or production readiness from a card or reachable URL;
- hardcode organization-wide asset totals into public cards.

## Source authority

`SZLHOLDINGS/README` and `SZLHOLDINGS/a11oy` are protected GitHub-derived Spaces. Any Space whose `deployment.json` identifies external source provenance is also audit-only. Those applications must be changed in the repository that owns their canonical source and then promoted through their existing deployment workflow.

A protected Space reaches the non-blocking `SOURCE_BOUND_VERIFIED` state only when its public deployment manifest and served build readback expose the same immutable source revision, while the public Hugging Face repository and running runtime expose the same immutable Space revision. Missing or divergent evidence remains blocked. Other source-bound Spaces remain blocked until an equally explicit public readback contract is configured.

## Responsive contract

Supported application shells receive one framework-local stylesheet that enforces:

- a viewport contract for static HTML;
- 44-pixel minimum interactive targets;
- auto-fitting card grids and one-column mobile actions;
- safe wrapping for hashes, revisions, receipts, and evidence identifiers;
- visible keyboard focus;
- reduced-motion behavior;
- zero horizontal overflow caused by technical identifiers;
- no runtime CDN dependency.

Adapters fail closed when source is ambiguous. Python adapters preserve shebangs, encoding declarations, module docstrings, and `__future__` imports before inserting their ordinary `pathlib` import, then parse the generated source before proposing it. Existing Gradio `css=` integrations and multiline Streamlit page configuration require source-native review instead of automated replacement.

## Transaction and evidence

For each eligible asset the controller:

1. resolves the exact current `main` SHA;
2. inventories repository files at that SHA;
3. records every preimage that would change;
4. generates deterministic card/application changes;
5. creates a Hugging Face pull request with `parent_commit` bound to the observed SHA;
6. optionally merges the pull request during explicit owner execution;
7. reads back the resulting `main` SHA;
8. writes a machine-readable report and rollback preimages.

An unsupported or unverified source-bound asset remains a blocker in the estate report. The manual execution job keeps one deterministic GitHub issue open until every asset is in a terminal verified state: `CURRENT`, `MERGED` with a distinct immutable provider readback, or `SOURCE_BOUND_VERIFIED`. Issue synchronization requires successful immutable evidence upload and a second exact-current-main check.

## Release decision

The estate may be called complete only when an owner-dispatched execution report contains:

```json
{
  "complete": true,
  "blocked_assets": [],
  "failed_assets": []
}
```

A source merge, successful plan, created-but-unmerged provider pull request, partial card rollout, or reachable URL is not an estate-wide production-verification claim. `complete: true` additionally requires explicit execute-and-merge mode and at least one inventoried asset; it can never be produced by a planning run.
