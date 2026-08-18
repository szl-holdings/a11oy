# SZLHOLDINGS universal frontend estate contract

## Purpose

This control plane normalizes the public Hugging Face presentation layer without converting presentation into evidence. It covers public model cards, dataset cards, eligible Space cards, and a bounded set of deterministic application shells.

## Canonical boundaries

The rollout may:

- preserve existing YAML frontmatter;
- insert or replace one idempotent managed card section;
- add mobile-safe CSS to static HTML, React, Gradio, and Streamlit shells when an exact source adapter succeeds;
- create Hugging Face pull requests from an exact observed parent revision;
- merge those pull requests only in the protected rollout job;
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

Adapters fail closed when source is ambiguous. Existing Gradio `css=` integrations and multiline Streamlit page configuration require source-native review instead of automated replacement.

## Transaction and evidence

For each eligible asset the controller:

1. resolves the exact current `main` SHA;
2. inventories repository files at that SHA;
3. records every preimage that would change;
4. generates deterministic card/application changes;
5. creates a Hugging Face pull request with `parent_commit` bound to the observed SHA;
6. optionally merges the pull request;
7. reads back the resulting `main` SHA;
8. writes a machine-readable report and rollback preimages.

A source-bound or unsupported asset remains a blocker in the estate report. The workflow keeps one deterministic GitHub issue open until every asset is either current or has been repaired at its canonical source.

## Release decision

The estate may be called complete only when the report contains:

```json
{
  "complete": true,
  "blocked_assets": [],
  "failed_assets": []
}
```

A partial card rollout may be useful, but it is not an estate-wide production-verification claim.
