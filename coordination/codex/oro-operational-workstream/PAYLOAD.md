# ORO operational execution payload

**Owner:** Stephen Lutar / SZL Holdings  
**Primary runtime:** `szl-holdings/a11oy`  
**Formal evidence:** `szl-holdings/lutar-lean`  
**Operating standard:** Zero-Bandaid Law  
**Delivery:** audit → branch → test → PR → protected checks → qillqaq evidence → merge queue → live readback

## Objective

Make ORO — Obligation-Ranked Orbits — a real A11oy control plane for cyclic agent graphs. The normal stopping mechanism must be structural: a reviewed rank decreases at every loop-closing barrier. `recursion_limit` remains only a defect backstop.

The delivered system must answer, with durable evidence:

- why another superstep is permitted;
- why fan-out did not mint authority or budget;
- which global invariants held after merged reduction;
- why the orbit halted or continued;
- which candidate, evaluator, formula, rank, Codex, and source revisions were used;
- why the result cannot self-certify or self-release;
- whether the relevant termination theorem is runtime-enforced, modeled, or machine-checked.

## Required architecture

### 1. Rank plane

Implement a frozen four-component rank:

1. unresolved obligations;
2. evidence deficits;
3. integer budget units;
4. turn allowance.

Requirements:

- reject booleans, floats, negative components, malformed tuples, overflow, and version drift;
- define objective convergence separately from rank exhaustion;
- consume a parent control turn before fan-out;
- partition obligations, evidence deficits, budget, and turns across children;
- prove conservation over the declared allocation receipt;
- compare parallel frontiers with a reviewed finite-multiset extension or equivalent well-founded construction;
- record `rank_before`, `rank_after`, allocation receipt, rank version, and theorem binding on every barrier.

### 2. Codex plane

The Codex is a signed data manifest selecting protected local predicates. It may not carry executable code.

Baseline blocking invariants:

- total provenance;
- no citation to an unretrieved span;
- unit consistency;
- canonical integer/decimal money, never binary float;
- UTC boundary timestamps;
- kernel and rank unaddressed;
- scoped authorization;
- evaluator immutability;
- no self-certification;
- protected paths unchanged;
- canonical formula commit;
- complete orbit lineage;
- signed barrier receipts.

Every invariant must bind stable ID, semantic version, source blob digest, implementation digest, input schema, and golden vectors.

### 3. Barrier plane

Global checks occur only after reducers merge. The barrier must:

- validate participant membership and generation;
- reject conflicting duplicate arrivals;
- enforce absolute TTL and bounded response size;
- compute a domain-separated semantic hash;
- detect semantic cycles;
- evaluate all blocking Codex predicates;
- verify rank decrease unless objective convergence already holds;
- invalidate the rejected transition and derived descendants on failure;
- emit a canonical signed DSSE/in-toto-compatible receipt;
- force a well-formed closing turn on every halt.

### 4. Three nested orbits

- **Discovery:** read-only; mines authenticated GitHub, GitLab, official documentation, and publications; captures license and source digest; cannot write production.
- **Evolution:** isolated branch/worktree; cannot modify its evaluator; compares candidate to immutable baseline; stores every rejection.
- **Task:** executes admitted work only; cannot create a release.

### 5. Six-cell role model

Implement separate, authority-bounded configurations for:

- Scout;
- Architect;
- Builder;
- Verifier;
- Sentinel;
- Integrator.

Each role gets an explicit tool and MCP allowlist. Cloning must deep-replace mutable tool/MCP/handoff configuration. No role may approve or merge its own work.

### 6. Evidence store

Use strict SQLite migrations for the first release. Monetary values must use integer micros or canonical decimal text. Store:

- orbit runs;
- barriers;
- rank allocations;
- invariant results;
- semantic hashes;
- negative results;
- candidate/baseline comparisons;
- approvals;
- signed receipts;
- completion/refusal certificates.

Approval must be independent of candidate and evaluator authors. Duplicate submissions must be idempotent.

### 7. Runtime and frontend

Expose before the SPA catch-all:

- `/oro` and `/oro/v5` zero-CDN dashboards;
- health/readiness;
- plan create/list/read/execute;
- orbit, barrier, cycle, invariant, and negative-result readback;
- intent, completion, and refusal certificate APIs.

Add exact Dockerfile `COPY` coverage for every runtime file. Add demo-critical route tests and real Uvicorn loopback HTTP smoke tests. Persistence and signing must fail closed in production when durable storage or a governed signer is unavailable.

### 8. Formal evidence

Create narrow Lean witnesses in `lutar-lean` for:

- well-foundedness of the reviewed nested lexicographic rank;
- transitive authority attenuation;
- no lower-authority admissible member within a declared finite candidate basis.

Protected evidence must execute:

```bash
lake exe cache get
lake build FrontierShowcase
lake env lean --no-sorries Showcase/Frontier/ORORankWitness.lean
lake env lean --no-sorries Showcase/Frontier/ORONegativeSpaceWitness.lean
```

Do not claim that these theorems prove worker correctness, network liveness, predicate correctness, full action enumeration, global optimality, or unrestricted autonomous improvement.

## One narrow demonstration

Inspect one failing or historically failing repository workflow. Create an isolated candidate repair. Run real static, test, security, replay, provenance, and formula checks. Compare to an immutable baseline. Emit signed barrier lineage and a refusal or nomination. Open a PR; never self-merge it. The demonstration must make no direct production write.

## Required permanent PRs

### A11oy runtime PR

Suggested branch: `feat/oro-operational-control-plane-v1`

Must include runtime, schemas, migrations, APIs, dashboards, Docker copies, tests, docs, and a narrow demonstration. Protected CI is authoritative.

### Lean evidence PR

Suggested branch: `feat/oro-formal-witnesses-v1`

Must include only the reviewed witness source, Lake root registration, tests/workflow evidence, and honest claim boundaries.

### A11oy proof-binding PR

Suggested branch: `chore/oro-proof-binding-v1`

Created only after the Lean PR merges. Data-only binding must include theorem names, exact merged Lean commit, workflow run, artifact digest, toolchain version, rank definition digest, and verification timestamp.

## Acceptance

A phase is complete only when `ACCEPTANCE.json` is satisfied and `STATUS.md` records protected evidence. Local or draft-branch tests are necessary but not sufficient for production claims.

The public labels before Lean merge are:

```text
runtime_enforced: MEASURED only after protected runtime readback
well_founded_termination: MODELED
machine_checked_termination: NOT_PROVED
global_action_optimality: NOT_CLAIMED
general_causal_identification: NOT_CLAIMED
```

## Completion condition

1. Runtime PR merged through protected delivery.
2. Lean PR merged with `lake build` and `--no-sorries` evidence.
3. Proof-binding PR merged.
4. A11oy live readback reports exact source revision, persistent-store integrity, signer identity, rank/Codex versions, and theorem binding.
5. Organization health, GitHub license, Hugging Face license, and public-link controls pass from current protected main.
6. This coordination PR is closed without merge.
