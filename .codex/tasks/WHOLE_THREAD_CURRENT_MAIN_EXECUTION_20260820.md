# A11oy Whole-Thread Current-Main Execution

**Issue:** #1355  
**Captured protected main:** `f5440d365471d656807a617e6b73b5b4dbe939ea`  
**Execution branch:** `codex/whole-thread-push-20260820`  
**Owner:** Stephen Lutar / SZL Holdings  
**Executor:** Codex

## Mission

Take over the active A11oy implementation estate, finish every collision-safe source lane, and push every qualified successor through normal protected promotion. This is an execution contract. A review, summary, recommendation list, or new roadmap does not satisfy it.

Before every write, recapture protected `main`, open pull requests, changed paths, exact heads, merge bases, signatures, DCO state, workflow conclusions, unresolved review threads, deployment ownership, and live-release dependencies. This file is a starting snapshot, not authority to ignore newer GitHub state.

## Captured active lanes

| PR | Lane | Captured state | Required disposition |
|---:|---|---|---|
| #1352 | deterministic HF Space source map | open / ready | qualify and promote first unless new evidence blocks it |
| #1351 | estate-wide HF Space frontend census | open / ready | qualify after source mapping |
| #1349 | scheduled live frontend canary | open / ready | qualify after or with source mapping |
| #1342 | ORO current-main core | draft | reconcile with #1333; only one ORO lineage survives |
| #1339 | Council authority kernel | draft | finish isolated authority package and promote independently |
| #1338 | universal HF frontend estate control plane | draft | finish after source-map/census/canary evidence exists |
| #1334 | Memory Covenant + token-ingress promotion | draft / stale base risk | rebuild on current main and complete integration |
| #1333 | operational ORO control plane | draft | reconcile with #1342; choose the complete current-main successor |
| #1320 | solo estate security/HF control plane | draft | finish provider audit boundaries and promote before broad HF rollout |
| #1311 | readiness freshness labels | open / likely superseded | prove exact supersession or build a clean successor; never merge duplicate semantics |

New overlapping PRs discovered during execution must be inserted into the graph and assigned one of the same terminal states.

## Terminal states

Every lane must finish as exactly one of:

- `MERGED_AND_VERIFIED`
- `SUPERSEDED_WITH_EXACT_EVIDENCE`
- `BLOCKED_EXTERNAL_AUTHORITY`
- `REJECTED_WITH_REASON`

`OPEN`, `DRAFT`, `PENDING`, `CI_RUNNING`, `REVIEWED_ONLY`, and `SOURCE_COMPLETE` are nonterminal.

## Execution phases

### Phase 0 — immutable recapture and collision map

1. Record exact protected-main SHA and tree.
2. Record every open PR head/base, changed files, commit signature state, DCO, mergeability, checks, review threads, and deployment surfaces.
3. Build a path-ownership matrix. One active writer owns a path at a time.
4. Detect semantic duplicates by comparing trees and patches against protected main. Titles and branch names are not evidence.
5. For a superseded lane, post the exact protected commit and smallest supporting diff before closing it.
6. Do not rerun deterministic failures without source changes. Fix the source or create a clean successor.

### Phase 1 — read-only source and frontend evidence

Preferred order, subject to current changed-path evidence:

1. #1352 — canonical Space-to-GitHub source map.
2. #1349 — live organization/Space/domain frontend canary.
3. #1351 — estate-wide frontend census.

Each must be current-main-native, exact-head green, DCO-compliant, independently reviewed, and free of unresolved P0–P2 findings. These lanes are evidence/control-plane installations, not permission for manual Hub writes.

### Phase 2 — deterministic authority kernel

Finish #1339 as an isolated Council authority package:

- preserve Authority, Sentinel, Verifier, and Value separation;
- retain categorical vetoes, exact-target capabilities, budgets, correlation discounting, minority objections, deterministic identities, and append-only ledger verification;
- keep models as advisers rather than authority;
- complete package integration, schemas, tests, documentation, Docker inclusion if runtime-delivered, and rollback;
- do not claim independent operators, managed signing, production autonomy, or deployment without separate evidence.

Promote through a clean current-main successor if the existing history is stale or unsigned.

### Phase 3 — one ORO implementation

Reconcile #1333 and #1342:

1. Compare exact changed paths, public APIs, persistence, signer boundary, schemas, dashboards, Docker delivery, tests, and truth labels.
2. Select the smallest complete current-main lineage.
3. Transplant only missing reviewed work from the losing lane.
4. Close the losing lane with exact replacement evidence.
5. Finish plan/run/barrier/approval APIs, durable evidence, signer refusal, root runtime registration, container delivery, Uvicorn smoke, and bounded real-workflow demonstration.
6. Keep well-founded termination labeled `MODELED` unless machine proof exists; do not claim global optimality or general causal identification.

### Phase 4 — estate security authority

Finish #1320 before enabling broad mutation-capable rollout:

- inventory GitHub security surfaces and provider permission failures fail-closed;
- classify issues without heuristic closure;
- inventory HF models, datasets, Spaces, collections, and kernel-classified resources;
- never expose credential values;
- ordinary runs remain read-only;
- any manual missing-card creation remains bounded, create-only, owner-dispatched, and never overwrites an existing card or infers a license.

### Phase 5 — universal HF frontend control plane

Finish #1338 using evidence from #1352, #1349, #1351, and #1320:

- mutate only supported card/frontend shells;
- preserve YAML frontmatter and application-specific behavior;
- treat canonical GitHub-backed assets as source-native and Hub audit-only;
- create HF pull requests first and merge only through the protected rollout workflow;
- preserve exact parent revisions and rollback preimages;
- never touch weights, tokenizer artifacts, dataset rows/schemas, visibility, hardware, storage, secrets, or signing keys;
- do not call the estate complete until the immutable report says `complete: true` with zero blocked and failed assets.

### Phase 6 — Memory Covenant and semantic-token promotion

Reconcile #1334 against current main:

- PostgreSQL-authoritative Memory Covenant v2 with non-bypass RLS role hardening;
- bounded outbox leasing and append-only receipt/audit controls;
- tokenizer semantic-oracle qualification;
- digest-bound Semantic Token Contract;
- content-addressed Prefix Foundry;
- contained file-native repository ingestion;
- bounded token/prefix/KV routing with honest `SAMPLE` and `MODELED` public labels;
- governed routes registered before SPA fallback;
- migrations, runtime status/refusal paths, schemas, Docker delivery, and focused tests;
- database access and live provider evidence remain fail-closed when unavailable.

### Phase 7 — protected promotion and live proof

For every promotion:

1. Rebuild or reconcile on the latest protected main.
2. Require physical DCO trailers and acceptable GitHub signature state.
3. Run the complete exact-head repository matrix.
4. Resolve all P0–P2 review findings and review threads.
5. Verify protected main still equals the reviewed base.
6. Promote only by the repository's protected squash mechanism using the exact reviewed head.
7. After merge, recapture main before touching dependent lanes.
8. Hugging Face publication must run only through the canonical protected workflow.
9. Require immutable GitHub SHA, HF repository SHA, HF runtime SHA, served build/source SHA, bounded stable readback, and domain/Space smoke evidence before labeling deployment verified.

## Non-negotiable prohibitions

- no direct protected-main write;
- no administrator or ruleset bypass;
- no force push;
- no self-approval;
- no required-check weakening, renaming, or allowlisting to manufacture green;
- no secret-value readback, logging, hashing, copying, or disclosure;
- no manual Hugging Face overwrite;
- no model training, weight mutation, hardware/visibility/storage mutation, or provider billing change unless a separately authorized task explicitly requires it;
- no production, signing, parity, autonomy, or performance claim without immutable evidence.

## Required receipts

Maintain a machine-readable ledger under `.codex/receipts/whole-thread-20260820/` containing:

- `state.json` — current protected main and lane status;
- `path-owners.json` — collision matrix;
- `promotions.json` — reviewed head, base, checks, merge commit, and rollback for every merge;
- `deployment.json` — canonical workflow run and immutable source/runtime identities;
- `final-disposition.json` — terminal disposition for every captured and newly discovered lane.

Generated evidence must not contain credentials, private payloads, tenant data, or unredacted provider responses.

## First required action

Comment on issue #1355 with the recaptured exact state and chosen first lane. Then implement or reconcile that lane and push source changes. Do not stop after the comment.

Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
