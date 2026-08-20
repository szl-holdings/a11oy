# Solo Estate Read-Only Inventory

## Purpose

This lane gives the solo operator a current, fail-closed inventory of repository
security, open issues, and the `SZLHOLDINGS` Hugging Face estate. It produces
evidence only. It has no provider mutation authority.

The inventory is separate from all remediation and deployment controllers.
In particular, `.github/workflows/hf-sync.yml` remains the only automatic
writer for the canonical Hugging Face Space. This workflow cannot create or
edit cards, request reviews, label or edit issues, dismiss alerts, change
visibility or hardware, or delete resources.

## Read-only authority

The workflow permissions are limited to GitHub reads:

- repository contents;
- issues;
- security events.

The controller exposes only an HTTP `GET` helper for GitHub. Its Hugging Face
client calls are limited to identity, list, repository-file download, and Space
runtime readback. The policy contains an empty Hugging Face mutation-method
allowlist and explicit false values for every former issue, review, card, alert,
visibility, hardware, and deletion write path.

The only outputs written by the controller are files in the local report
directory. GitHub Actions uploads that directory as a 90-day evidence artifact.
README downloads use a per-read temporary cache that is removed before the
provider result is returned, so private card contents do not persist in the
runner's user-level Hugging Face cache.

## Exact-source boundary

Every live run checks out the event SHA, requires a clean tracked worktree, and
reads the protected `main` ref from GitHub both before and after provider
collection. The inventory is blocked unless both reads and both local checks
remain bound to the same 40-character Git SHA. A run that races with a newer
main commit or a local tracked-file edit therefore fails closed instead of
presenting a stale report as current.

The report records:

- exact local and protected revisions;
- policy digest;
- run time;
- provider readback states;
- an empty `provider_mutations_performed` list;
- a SHA-256 digest of the canonical JSON report.

## GitHub security inventory

The controller reads open Dependabot, code-scanning, and secret-scanning alerts,
plus repository security advisories. It also checks source presence for
Dependabot, CodeQL, secret scanning, the security policy, and CODEOWNERS. It
reads the Metadata-authorized effective rules for `main`, including rules
inherited from organization rulesets, and requires at least one named status
check plus at least one approving review. The effective-rules endpoint does not
expose bypass actors, so bypass and administrator enforcement are recorded as
`UNAVAILABLE` / `NOT_INFERRED` rather than guessed.

The following are terminal:

- every observed secret-scanning alert;
- open critical or high severity security findings;
- missing repository controls;
- absent status checks or pull-request review protection;
- permission denial, provider failure, or pagination exhaustion.

Provider error bodies are discarded. Normalized evidence contains identifiers,
severity, state, safe summary fields, and provider links, but never a secret
value.

## Open-issue inventory

Open issues are read and deterministically classified as P0, P1, or P2 with
security, Hugging Face, and deployment domains. Existing labels are observed;
no recommended or applied label set is emitted. No issue or review mutation API
is present.

A P0 observation is terminal for the inventory result. The issue remains open
for its owning workstream; this controller does not attempt closure.

## Hugging Face inventory

A dedicated `HF_INVENTORY_READ_TOKEN` secret is required because an anonymous
listing cannot establish the private organization estate. It is injected only
into the inventory step. The controller reads the token identity, requires the
reported access-token role to be exactly `read`, and requires an observed
`SZLHOLDINGS` organization relationship. Missing credentials, write or
fine-grained token roles, identity denial, or an unbound identity remains
blocked. There is no fallback to the deployment token used by `hf-sync.yml`.

For accessible models, datasets, Spaces, and collections it observes:

- repository identifier, privacy flag, and immutable SHA;
- README presence and exact-SHA readback;
- card frontmatter, required sections, and narrow-screen risks;
- declared model or dataset license metadata without inferring a license;
- model pipeline or task metadata;
- Space SDK and current runtime stage;
- collection title and membership;
- kernel classification from policy-bound identifiers and tags.

An absent README is reported as `CARD_MISSING`. A failed README request is
reported separately as `CARD_READBACK_UNAVAILABLE`; provider failure is never
misrepresented as absence. Neither state activates a card writer.

## Workflow behavior

### Pull requests

The secret-free contract job validates JSON and Python syntax, runs the offline
self-test and unit suite, proves importlib loading without pre-registering the
module in `sys.modules`, and statically rejects provider mutation primitives.

### Protected-main pushes, schedule, and manual dispatch

The live job installs a pinned Hugging Face read client, performs current
provider inventory, uploads the report, and then enforces its terminal exit
code. Manual dispatch has no write-enabling input.

## Evidence files

Each live run writes:

- `estate-report.json`;
- `estate-report.json.sha256`;
- `estate-summary.md`;
- `issue-inventory.json`;
- `hf-estate.json`.

`PROVED` describes the source-defined contract and deterministic validation.
`MEASURED` is emitted only when every required provider readback completed from
that run. Partial, denied, malformed, or otherwise unverified collection is
labelled `BLOCKED` even when the outer report already carries a more specific
blocked state.
Production state, legal approval, remediation, deployment parity, and security
closure remain `NOT_CLAIMED` without their own exact evidence.

## Rollback

Before merge, close the successor pull request. After merge, revert through a
new signed and DCO-bearing protected pull request. Do not grant write
permissions or add a second Hugging Face writer as a rollback shortcut.
