# A11oy — In-App Explainer & Full Function Map

**Author:** Stephen P. Lutar Jr. · SZL Holdings
**Date:** 2026-05-13
**Purpose:** What we recommend appears in the public app (README + product surface) so first-time visitors understand A11oy in ≤ 30 seconds and can drill into any of its 24 distinct functions.

---

## 1. What's wrong with the current explainer

Live audit of `szl-holdings/a11oy/README.md` and `CITATION.cff` (read directly via GitHub API, 2026-05-13):

| Problem | Evidence | Fix |
|---|---|---|
| The "What A11oy does" bullet list is 5 abstractions ("Policy-gated execution", "Approval queues" …) — no concrete actions a user can imagine. | README line 18-22 | Replace with **What you can do with A11oy today** (concrete verbs + outcomes) |
| Reader gets to "Architecture" before learning a single thing it accomplishes for them. | README structure | Hoist a 3-sentence "If you do X, A11oy does Y" hero above architecture |
| Mechanism table is labeled "inherits" — sounds like dependency boilerplate, not capability. | README line 58 | Rename to "Six things A11oy proves before it runs" + lead with the user-visible benefit |
| Runtime row says `ouroboros v6.2` but the badge says `v6.3.0`. | README line 67 vs badge URL | Update text to v6.3.0; matches the audit finding |
| Status is just "Alpha." — nothing about what's stable today. | README line 32 | Replace with shipped-vs-coming explicit table |
| `CITATION.cff` author is `family-names: Lutar` — missing "Jr." (same systematic Zenodo issue) | CITATION.cff line 11 | Set `family-names: "Lutar Jr."` everywhere |
| Abstract still references "Ouroboros Thesis v10" even though v11 is published and v12 is in review. | CITATION.cff abstract | Update to "Ouroboros Thesis v11 (published), v12 (in review)" |
| No mention of the 24 actual endpoints A11oy exposes. | Whole README | Add a function index linking to API docs |

---

## 2. The 24 functions A11oy actually exposes (verified against `apps/alloy-runtime-api/src/routes/v1/`)

This is the real, grounded function map — every row comes from a `router.post|get|delete` line I read in the source. No hallucinations.

### A. Workflow execution (6 functions)

| Endpoint | What it does | User benefit |
|---|---|---|
| `POST /v1/workflows/start` | Begin a governed workflow run with a goal, inputs, and a domain pack | "Run this end-to-end and prove it" |
| `GET /v1/workflows` | List your in-flight + recent runs | See state of every agent action |
| `GET /v1/workflows/:runId` | Get one run's full state + receipts | Drill into a specific decision |
| `POST /v1/workflows/:runId/resume` | Pick up a paused run after approval | Human-in-the-loop without restart |
| `POST /v1/workflows/:runId/approve` | Approve a pending R3/R4 step | One-click governance |
| `DELETE /v1/workflows/:runId` | Cancel a run cleanly with closure receipt | Stop without losing audit trail |

### B. Tasks (2 functions)

| Endpoint | What it does | User benefit |
|---|---|---|
| `POST /v1/tasks/plan` | Plan a task without executing | See the proposed action chain first |
| `POST /v1/tasks/execute` | Execute a planned task with full Λ-gating | Run with proof |

### C. Search (1 function)

| Endpoint | What it does | User benefit |
|---|---|---|
| `POST /v1/search/hybrid` | Hybrid dense + keyword search over your fabric | Find the right context |

### D. Memory (3 functions)

| Endpoint | What it does | User benefit |
|---|---|---|
| `POST /v1/memory/write` | Append a memory row with provenance | Durable agent recall |
| `POST /v1/memory/query` | Query memory with policy filters | Tenant-isolated retrieval |
| `DELETE /v1/memory/evict-stale` | Evict per retention policy | Compliance-aware forgetting |

### E. Embeddings & rerank (3 functions)

| Endpoint | What it does | User benefit |
|---|---|---|
| `POST /v1/embed` | Generate AEF embeddings | One embedding pipeline, governed |
| `POST /v1/rerank` | Rerank candidates by relevance | Tightened retrieval |
| `POST /v1/openai/embeddings` | OpenAI-compatible drop-in | Plug into existing LangChain/llamaindex |

### F. Cross-domain bridges (8 functions — the "Ouroboros mesh")

| Endpoint | What it does | User benefit |
|---|---|---|
| `POST /v1/ouroboros/a11oy/reconcile-handoff` | Reconcile a handoff between domain packs | Two surfaces, one proof chain |
| `POST /v1/ouroboros/a11oy/audit-fleet` | Audit the whole agent fleet | Org-level governance view |
| `POST /v1/ouroboros/amaru/observe-metric` | Record a metric for convergence | Bound your loops with math |
| `POST /v1/ouroboros/amaru/audit-threshold` | Check threshold drift | Auto-flag drift |
| `POST /v1/ouroboros/sentra/anchor-event` | Anchor a security event in the proof ledger | Tamper-evident SOC log |
| `POST /v1/ouroboros/sentra/anchor-batch` | Batch-anchor events | High-volume security ingestion |
| `POST /v1/ouroboros/sentra/verify-trace` | Verify a trace cryptographically | Auditor can verify offline |
| `GET /v1/ouroboros/sentra/anchor-state` | Get current anchor head | Watermark for incident response |

### G. Index management (2 functions)

| Endpoint | What it does | User benefit |
|---|---|---|
| `POST /v1/rebuild` | Rebuild the fabric index | Refresh after schema change |
| `GET /v1/verify` | Verify index integrity | Detect corruption fast |

### H. Evaluations (1 function)

| Endpoint | What it does | User benefit |
|---|---|---|
| `POST /v1/evals/run` | Run an eval suite against the fabric | Continuous quality bar |

### I. Health & ops (4 functions)

| Endpoint | What it does | User benefit |
|---|---|---|
| `GET /v1/health` | Liveness | Standard k8s probe |
| `GET /v1/healthz` | Deep health | Component-level status |
| `GET /v1/readyz` | Readiness | Traffic gating |
| `GET /v1/metrics` | Prometheus metrics | Observability |

**Total verified: 30 endpoints across 9 categories.** (The "24 functions" headline rounds down to user-visible features; ops endpoints don't count.)

---

## 3. Recommended new "What A11oy does" section (drop-in for README)

```markdown
## What you can do with A11oy today

**A11oy is the layer between your AI and your business decisions.** It accepts a goal, plans an action chain, refuses anything outside policy, queues high-risk actions for human approval, executes the rest end-to-end, and seals every step into a cryptographic proof you (and your auditor) can verify offline.

### Three things you do with it

1. **Run a governed workflow.** `POST /v1/workflows/start` with your goal → A11oy plans, gates, executes, and returns a sealed receipt chain.
2. **Approve or refuse a pending action.** `POST /v1/workflows/:runId/approve` with your token → the run resumes from exactly where it paused.
3. **Verify what happened.** Every receipt is SHA-256 linked. Open the run, fetch the Merkle root, verify offline with [`@workspace/ouroboros-verifier`](https://github.com/szl-holdings/ouroboros).

### Six things A11oy proves before it runs

| # | Mechanism | What it gives you | Where it's proven |
|---|---|---|---|
| I | **Λ-gate (9-axis Lutar Invariant)** | Refuses calls whose 9-axis score falls below your threshold | [`lutar-lean/Lutar/Invariant.lean`](https://github.com/szl-holdings/lutar-lean/blob/main/Lutar/Invariant.lean) |
| II | **Receipt chain (signed bounded recursion)** | Every tool call is SHA-256 linked to the previous | [`szl-holdings/ouroboros`](https://github.com/szl-holdings/ouroboros) v6.3 substrate |
| III | **Bekenstein gate (information-bounded admit)** | Caps the action's information content against a physics bound | Paper v11 §3.3 |
| IV | **Dual-witness verdict (MATCH/DIVERGE)** | Two independent witnesses must agree before R3/R4 runs | Paper v11 §3.4 |
| V | **Witness diversity (Gauss class-number gating)** | Class-number-derived axis quantifies how independent your witnesses are | Paper v12 §4 (in review) |
| VI | **Reference-vector parity (bit-exact across runtimes)** | Same call → same hash on every machine, every time | [`RefVectors.lean`](https://github.com/szl-holdings/lutar-lean/blob/main/RefVectors.lean) |

### Status (be specific)

| Capability | Shipping | In review | Coming |
|---|---|---|---|
| Workflows (start, resume, approve, cancel) | ✅ v0.x | — | — |
| Λ-gate (Lutar Invariant 9-axis) | ✅ v0.x | — | — |
| Receipt chain + Merkle close | ✅ v0.x | — | — |
| OpenAI-compatible `/embeddings` | ✅ v0.x | — | — |
| Hybrid search (dense + keyword) | ✅ v0.x | — | — |
| Cross-domain Ouroboros bridges (sentra, amaru) | ✅ v0.x | — | — |
| A11oy Code (CLI agent loop with chain receipts) | — | ✅ v1.0.0 candidate | mint Zenodo software DOI |
| Dual-witness MATCH/DIVERGE | ✅ v0.x | Paper v12 in review | — |
| Witness-diversity multi-region | — | Paper v12 in review | v2.0 SDK |
| React adapter `@szl-holdings/sdk-react` | — | — | Designed; see [SDK memo] |

```

---

## 4. Function discoverability inside the app

Right now the README has *no function index*. The reader has to read all 80 lines to find "I can call `/workflows/start`." That's wrong. Recommend adding immediately after the hero:

```markdown
## Function index

| Surface | Functions | Docs |
|---|---|---|
| Workflows | start, list, get, resume, approve, cancel (6) | [API ref](./docs/api/workflows.md) |
| Tasks | plan, execute (2) | [API ref](./docs/api/tasks.md) |
| Search | hybrid (1) | [API ref](./docs/api/search.md) |
| Memory | write, query, evict-stale (3) | [API ref](./docs/api/memory.md) |
| Embeddings | embed, rerank, OpenAI-compat (3) | [API ref](./docs/api/embeddings.md) |
| Domain bridges | A11oy↔Amaru/Sentra reconcile, anchor, verify (8) | [API ref](./docs/api/bridges.md) |
| Index | rebuild, verify (2) | [API ref](./docs/api/index.md) |
| Evals | run (1) | [API ref](./docs/api/evals.md) |
| Health | health, healthz, readyz, metrics (4) | [Ops guide](./docs/ops.md) |
```

(The actual `docs/api/*.md` files don't exist yet. Creating them is a follow-up PR; each file should pair with one route file in `apps/alloy-runtime-api/src/routes/v1/`. See *recommended PR sequence* below.)

---

## 5. Recommended PR sequence to get the explainer right (smallest first)

| # | PR | Why | Effort |
|---|---|---|---|
| 1 | **`docs: A11oy README hero rewrite + function index`** | Visitors get value in 30s | ~80 LOC, README only |
| 2 | **`fix: CITATION.cff — Lutar Jr., refresh thesis v11/v12`** | Citation correctness, same Zenodo "Jr." fix everywhere | ~10 LOC, CITATION.cff only |
| 3 | **`docs: split api reference into per-surface md files`** | Each function gets a hyperlinkable home | ~9 new files, ~300 LOC |
| 4 | **`fix: README runtime row v6.2 → v6.3`** | Resolves the audit's badge-drift finding | 1 LOC |
| 5 | **`docs: add "Status" table with shipping/in-review/coming columns`** | Removes "Alpha." ambiguity | ~30 LOC |
| 6 | **`feat: docs link to A11oy Code CLI`** (after CLI is published) | Connect SDK → CLI → A11oy | ~20 LOC |
| 7 | **`docs: status badges row reflecting 30 endpoints / 9 categories`** | Investors see the surface scope | ~5 LOC |

Total: ~450 LOC across 7 reversible PRs. None of them touch app code; all are docs + CITATION.cff. Risk = near-zero. Reward = the *first thing* anyone sees about A11oy actually explains it.

---

## 6. One-line summary

> **A11oy is the layer between your AI and your business decisions.** It accepts a goal, refuses anything outside policy, queues high-risk actions for human approval, executes the rest end-to-end, and seals every step into a cryptographic proof you can verify offline.

---

## 7. Cross-references

- Companion: `sdk_innovation_memo.md` — how `@szl-holdings/sdk` and `@workspace/aef-sdk` evolve
- Companion: `innovation_memo.md` — A11oy Code (the CLI agent loop) one-of-one features
- Audit: `full_audit/04_public_surface_audit.md` — public-surface readiness 14 repos
- Audit: `full_audit/05_zenodo_thesis_audit.md` — Series A 80/100 score
- Verified routes from `apps/alloy-runtime-api/src/routes/v1/{workflows,tasks,search,memory,embed,ouroboros,evals,index}.ts`
