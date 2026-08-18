# Solo Estate Security and Hugging Face Control Plane

## Purpose

This control plane gives one owner a durable, protected path for maintaining
A11oy security, GitHub issues, and the complete `SZLHOLDINGS` Hugging Face
estate without introducing a mandatory second-human bottleneck or weakening
release controls.

It is designed around four authorities:

1. **GitHub provider readback** for Dependabot, code-scanning,
   secret-scanning, repository advisories, protected-main policy, issues, and
   exact source identity.
2. **Hugging Face provider readback** for models, datasets, Spaces,
   collections, kernel-classified resources, immutable SHAs, cards, metadata,
   and runtime stages.
3. **Protected source control** for signed+DCO changes, exact-head checks,
   merge queue or protected auto-merge, rollback, and evidence retention.
4. **The solo owner** for legal/license selection, risk acceptance, secret or
   endpoint administration, and irreversible promotion decisions.

## Solo-builder contract

The estate remains operable by one authorized owner:

- no mandatory second human reviewer;
- automated independent review and attestation are allowed;
- exact-head binding is required;
- protected-main, signed+DCO history, and normal merge protections remain
  required;
- no force push, administrator merge bypass, self-approval, or direct main
  write;
- no automatic security-alert dismissal;
- no heuristic issue closure;
- no secret-value readback;
- no automatic Hugging Face visibility, hardware, storage, or deletion
  operation.

This keeps the system solo-operable without turning “solo” into an excuse to
remove evidence or protection.

## GitHub security sweep

The live workflow inventories:

- open Dependabot alerts;
- open code-scanning alerts;
- open secret-scanning alerts;
- repository security advisories;
- Dependabot configuration;
- CodeQL and secret-scanning workflow presence;
- `SECURITY.md` and `CODEOWNERS`;
- protected-main readback.

A denied permission is `BLOCKED`, not green. Open secret-scanning findings and
critical/high Dependabot or code-scanning findings are terminal. The controller
never dismisses an alert; closure requires the exact alert identifier, an exact
remediating commit or explicit risk authority, current-head checks, protected
merge, and post-merge provider readback.

## Issue sweep

Every open issue is classified deterministically by priority and domain. The
controller applies only additive labels and maintains one control issue:

`[SOLO-ESTATE] Security, issues, and Hugging Face closure`

The control issue contains the current security inventory, P0/P1/P2 issue
summary, Hugging Face counts, top findings, exact source revision, and immutable
workflow artifact name.

The controller does not close issues. P0 closure requires immutable evidence.
Coordination-only issues remain open until permanent implementation and live
readback exist. Major upgrades remain isolated until compatibility and rollback
proof are current.

## Hugging Face estate sweep

The audit inventories all organization:

- models;
- datasets;
- Spaces;
- collections;
- resources inferred as kernels from identifiers or tags.

For repository-backed resources it checks:

- full immutable SHA;
- README/card presence;
- YAML frontmatter;
- required sections;
- declared license for models and datasets;
- model pipeline/task metadata;
- Space SDK and runtime stage;
- mobile risks such as fixed-width media, raw tables, oversized table column
  counts, and unbounded lines;
- collection title and non-empty membership.

### Safe write boundary

Normal push and scheduled runs are read-only on Hugging Face. Manual dispatch
may enable `apply_safe_hf_cards`, which is restricted to creating a truthful
baseline `README.md` where no card exists at all. It never overwrites an
existing card and never infers a license.

All higher-quality upgrades—brand narrative, investor language, screenshots,
model/dataset-specific usage, limitations, citations, benchmarks, or collection
composition—must be derived from the exact source and reviewed as a resource-
specific change. Generic content is not allowed to overwrite stronger content.

## Workflow behavior

### Pull request

The contract job is secret-free and offline. It validates JSON, Python syntax,
issue classification, card-quality logic, redaction, and the solo-authority
invariants.

### Protected-main push

The live audit runs after the control-plane source merges. It applies additive
issue labels, audits security/Hugging Face, updates the control issue, uploads an
immutable 90-day artifact, and fails closed for terminal findings.

### Schedule

The same live audit runs every Monday. Scheduled execution does not make Hugging
Face writes.

### Manual dispatch

The owner can choose whether to apply additive labels and whether to create only
entirely missing baseline cards.

## Evidence

Each live run writes:

- `estate-report.json`;
- `estate-report.json.sha256`;
- `estate-summary.md`;
- `issue-triage.json`;
- `hf-estate.json`.

The report records the exact Git revision, policy digest, API readback states,
resource findings, mutations performed, and explicit non-mutations.

## Closure states

- `PASS`: no terminal security, P0 issue, or Hugging Face blocker was observed.
- `POLISH_REQUIRED`: the estate is operational but cards or metadata require
  quality work.
- `BLOCKED_SECURITY`: a terminal security finding or denied security authority
  remains.
- `BLOCKED_P0_ISSUES`: at least one open P0 issue remains.
- `BLOCKED_HUGGINGFACE`: a high Hugging Face metadata/runtime blocker remains.
- `BLOCKED_CONTROL_ISSUE`: the durable dashboard could not be written.

No state implies production deployment, license approval, or model quality
without its own exact evidence.

## Known external-authority class

Some work cannot be solved by source code alone, including:

- selecting a legally correct missing license;
- rotating or replacing a failing managed webhook endpoint;
- restoring provider permissions denied to `GITHUB_TOKEN`;
- authorizing paid Space hardware changes;
- accepting security risk.

Those items remain visible as `blocked:external-authority`; the system never
hides them by weakening a check.
