# Hugging Face Space Source Map v1

## Purpose

A frontend failure may be repaired only in the application’s canonical source repository and promoted through its existing deployment writer. This map removes name-guessing and competing-writer risk from the SZLHOLDINGS Space remediation program.

## Evidence classes

- `EXACT` — explicit ownership declarations in the public Space README/card agree on one `szl-holdings/*` repository, and the GitHub API resolves that same repository identity.
- `INFERRED` — no ownership declaration is present, but exactly one normalized Space-name repository exists. This remains inferred evidence and requires owner review before write operations.
- `DIVERGENT` — ownership declarations conflict, contain unsupported or ambiguous source metadata, name an out-of-organization source, or fail to resolve to the declared repository identity; or multiple normalized name matches exist.
- `UNAVAILABLE` — no public source mapping can be established.

`EXACT` identifies a canonical source repository for owner-reviewed source changes and promotion through that repository's protected writer. It does not authorize a direct Hugging Face mutation. `INFERRED` may be used for investigation only, while `DIVERGENT` and `UNAVAILABLE` remain blocked pending explicit ownership evidence.

## Ownership declarations

General GitHub links are retained as reference evidence. Dependency links, badges, examples, quotations, and links to the estate command center do not establish application ownership.

The mapper accepts plain or quoted scalar source metadata at the top level of the card, or in a single-level `szl` block mapping. Root keys must be unindented, unquoted names. Supported field names are `source_repo`, `source_repository`, `source_url`, `github`, `github_repo`, `github_repository`, `repository`, and `repo_url`. A value must be an `owner/repository` identifier or a GitHub repository URL. Repository URLs may identify a source subtree. LF and CRLF cards are supported.

For example, the application's canonical GitHub source can carry this card metadata and promote it through its existing writer:

```yaml
szl:
  source_repo: szl-holdings/example-space
```

The mapper also recognizes a small set of explicit prose declarations at the start of a paragraph or list item:

- `Canonical source: <repository>`
- `Source repository: <repository>`
- `GitHub source of record: <repository>`
- `The canonical source is <repository>`
- `This Space is published from <repository>`

The repository can be a URL, Markdown link, or code-formatted identifier, including a wrapped continuation line. The source-of-record form also accepts the prefix `public repository` or `public Apache-2.0 repository`. A later sentence describing dependencies does not change the declared owner. Repeated declarations must agree after case and `.git` normalization.

Duplicate source keys, YAML merge keys, aliases, block or collection source values, conflicting declarations, and malformed or unsupported source mappings remain `DIVERGENT`. An invalid declaration never falls back to a normalized-name match. Fenced code, indented code, block quotations, HTML comments, and HTML code or quotation blocks are excluded from prose ownership evidence. Unsupported prose remains reference material unless it uses one of the recognized declaration prefixes, in which case an invalid repository value blocks the mapping.

## Captured state

For each public Space, the map records:

- Hugging Face repository and runtime revisions
- README bytes fetched from the exact recorded Hugging Face repository revision through an immutable `/raw/<sha>` or `/resolve/<sha>` URL
- runtime stage and SDK
- public README hash and front-matter keys
- general SZL Holdings GitHub repository references, separately from declared source repositories
- recognized source declarations and any declaration-validation errors
- verified or inferred source-repository candidates
- canonical source-repository default branch, exact branch-head revision, visibility, and archival state
- deployment-workflow filename candidates under `.github/workflows` at that exact GitHub revision

The managed card does not contain the Hugging Face commit that contains the card: embedding that value would create a non-converging self-reference. Instead, each exact mapping binds the Hub revision to the README hash and canonical GitHub revision. The rollout report supplements that record with exact readback hashes for every required managed card and framework-adapter path.

A single workflow filename candidate is not proof of single-writer authority. It is labeled only as a candidate until workflow contents, target resource, and protected promotion behavior are reviewed.

Candidate records in a `DIVERGENT` mapping retain repository identity only. Mutable branch, visibility, and archival fields are omitted, and workflow discovery remains blocked until exactly one canonical repository has been established.

## Complete, bounded observation

The observer follows the Hugging Face Space listing's `Link` cursor pagination with the original author, `limit=100`, and `full=true` scope. Every requested page must remain on `https://huggingface.co/api/spaces`. Redirects, changed query filters, duplicate query fields, unsupported or malformed links, repeated pages or repository IDs, and empty nonterminal pages fail the observation.

The bounds are 20 pages, 2,000 repositories, 4 MiB per response, and 16 KiB per Link header. README and GitHub evidence responses are also bounded to 4 MiB. Every record must identify the requested organization, explicitly report public visibility, and include an immutable 40-character repository revision. Exceeding a bound or receiving malformed evidence fails the run; the observer does not emit a successful partial census. The scope is the public Space listing returned by the API.

The tracked JSON is a reviewed evidence snapshot. Its full-byte comparison and `--check` drift failure remain in force. Changing the resolver does not refresh that snapshot, substitute fresh timestamps for evidence, or close the tracking issue. Any new snapshot requires a separate review of the newly observed mappings and revisions.

## Mutation boundary

The map performs public/read-only Hugging Face and GitHub API calls. It does not create branches, pull requests, releases, deployments, Hub commits, model updates, dataset updates, collection changes, secrets, hardware allocations, storage mounts, or visibility changes.

## Use in the remediation pipeline

1. The estate-wide browser census identifies a blocked Space.
2. This map resolves the canonical source repository.
3. The universal frontend adapter is installed in that repository.
4. Existing CI, protected merge, and the canonical Hub writer promote the repair.
5. The browser census proves all five viewport classes and immutable runtime identity.
6. The asset closes only after the source map, deployment evidence, and live readback agree.
