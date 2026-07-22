<!--
SPDX-License-Identifier: Apache-2.0
© Stephen P. Lutar Jr. (ORCID 0009-0001-0110-4173) · Doctrine v11 LOCKED
-->

# AGENTS.md — source of truth for AI coding agents (Forge, Claude Code, Cursor)

> This file is the doctrine-bearing context every AI coding agent must read **before**
> touching this repo. `CLAUDE.md` points here. Machine-readable per-concern rules live in
> [`.claude/rules/`](.claude/rules/). When unsure, **prefer the honest label and ask before claiming.**

---

## What this repo is

**a11oy** — the governed agentic substrate of SZL Holdings. Every action is doctrine-gated
before it runs, executed on a governed agent loop, metered in joules, and sealed as a signed
Khipu receipt; the whole thing ships through a signed supply chain. See
[`README.md`](README.md) and [`docs/architecture.md`](docs/architecture.md).

**Shape today:** flat-rooted — ~222 `a11oy_*.py` / `szl_*.py` modules plus `serve.py` (boot
entry + route assembly). The logical taxonomy (`agents` / `tools` / `services` +
`provenance` / `governance` / `energy` / `supply-chain`) is a *map*, documented in
`docs/architecture.md` — not a physical move. When you need to know which file to edit, use
the [Where things live](#where-things-live) table.

---

## DOCTRINE — non-negotiable (v11 LOCKED)

These are enforced, not aspirational. A diff that breaks one of these is a **doctrine
failure**, not a style nit — it will fail the doctrine-grep CI gate and the honest-status
review.

- **HONEST LABELS.** Never claim **MEASURED** without a real, fresh exporter delta. Unverified =
  **SAMPLE**; future = **ROADMAP**; design-only = **MODELED**. Never fabricate joules, proofs,
  signatures, or status. *HONESTY OVER CHECKLIST.*
- **NO BANNED TOKENS.** No marketing-hype superlatives and no retired codenames (remapped to
  honest roles). The **doctrine-grep CI gate** holds the authoritative ban-list as data (see
  `.github/workflows/doctrine-grep.yml`); respect `.doctrine-allowlist` for files that must
  enumerate the list by design.
- **DENY-BY-DEFAULT.** Any new agent action path must clear `governance/` (constitution +
  doctrine gate + guards) **before** execution.
- **RECEIPT-ON-WRITE, NOT ON-READ.** Signing belongs on state changes, never on GETs. Do **not**
  add sign-per-request side effects to read paths (see the `/frontier/manifest` no-sign-on-GET
  fix — keep it that way).
- **LOCKED vs EXPERIMENTAL.** The proof-carrying canonical registry admits **5**
  locked-proven formulas `{F1, F11, F12, F18, F19}`. F4, F7, and F22 are
  source-present **EXPERIMENTAL** entries, not locked. **Never inflate the locked
  count.** Λ-uniqueness is **Conjecture 1**; Khipu BFT safety is **Conjecture 2** —
  never call either a theorem.
- **MEASURED-ONLY JOULES.** Energy is MEASURED only with a real NVML/GPU-lung delta; otherwise
  honest SAMPLE/DEGRADED. Carbon is ROADMAP (no live grid feed).
- **NEVER COMMIT A KEY.** No secrets, signing keys, or tokens in the tree. Respect
  `.gitleaks.toml`. The sandbox must never be able to read a secret or forge a receipt.
- **HONEST BLOCKED BEATS FAKE GREEN.** A truthful BLOCKED/DENY is better than a fabricated pass.
- **NEVER WEAKEN A CI GATE.** Do not relax the doctrine-grep gate, the demo-critical route
  guard, or any honest-status check to make a diff pass.
- **CITE PRIOR ART.** External ideas (e.g. Ponytail restraint, the references in
  `docs/architecture.md`) are cited, never claimed as ours.

---

## Where things live

Logical map over the flat repo (modules already exist; this is a "which file to edit" guide).
Full table + module lists in [`docs/architecture.md`](docs/architecture.md).

| Layer | Role | Representative modules |
|---|---|---|
| **agents/** | the brain — agentic loop, react core, code engine | `a11oy_agent_loop`, `a11oy_react_core`, `szl_agentic_loop`, `a11oy_code_engine`, `a11oy_code_orchestrator`, `a11oy_v4_agent` |
| **tools/** | pluggable levers | `a11oy_mcp_client`, `szl_connector_mcp`, `szl_sovereign_search`, `szl_rag`, `a11oy_org_rag` |
| **services/** | business logic + plumbing | `serve` (entry), `szl_backend_hardening`, `szl_budget_router`, `szl_llm_registry` |
| **provenance/** | signed receipts | `szl_provenance`, `szl_dsse`, `szl_khipu*`, `szl_receipt_substrate`, `szl_khipu_verify` |
| **governance/** | doctrine gate + restraint / Λ + guards | `a11oy_constitution`, `szl_governance_gateway`, `szl_restraint*`, `szl_lambda_tripwire`, `szl_codename_gate`, `szl_colang_policy` |
| **energy/** | joules + carbon (ROADMAP) | `szl_energy_operator`, `szl_energy_ledger`, `szl_energy_projection`, `joule_billing`, `szl_joules_truth` |
| **supply-chain/** | cosign · SLSA · UDS · SBOM (ROADMAP) | `szl_uds_fleet`, `szl_uds_portability`, `runtime_attestation`, `sign_cert_dsse` |

**Rule:** no new top-level module without a taxonomy home — say which layer it belongs to in
the PR description, and (if it serves a route) add a corresponding Dockerfile `COPY` line.

---

## Live surfaces (don't break these)

These return HTTP 200 today and are demo-critical:
`/console` · `/frontier` · `/governance` · `/orbital` · and the APIs
`/api/a11oy/v1/{honest, energy/ledger, energy/operator/status, restraint/info,
frontier/manifest, compute-pool-hardened, pnt/limits}`.

If a demo-critical route guard test exists (e.g. `tests/test_demo_critical_routes.py`), extend
its route list when you add a demo-critical route — never delete a registration. Register new
API routes **before** the SPA catch-all, or they fall through to an HTML 200.

---

## Known gotchas (read before debugging — full list in `KNOWN_GOTCHAS.md`)

- **GitHub ↔ HF Space drift:** `hf-sync.yml` syncs only `README.md`; app code reaches the Space
  only when the GHCR image is rebuilt and the Space references the new tag. Check the commit in
  `/api/a11oy/healthz`.
- **Per-file `COPY` in the Dockerfile:** a new `.py` not `COPY`-ed in is absent at runtime; its
  route silently falls through to the SPA catch-all (HTML 200, no JSON). Add a `COPY` line.
- **`from __future__ import annotations` + FastAPI/Pydantic:** breaks model validation at
  runtime; don't use it in files defining route handlers / Pydantic models.
- **OMEN is not an energy lung under stock env:** needs `A11OY_OMEN_BASE_URL` +
  `A11OY_OMEN_STANDBY=0`. Joules are honest SAMPLE otherwise.
- **Energy ledger is ephemeral** unless `SZL_ENERGY_LEDGER_PATH` is on a persistent volume.
- **Some bare page paths are SPA-shell-only;** a route-table test can't catch a missing client
  route.

---

## Build & Test

### Repo context

This is a **standalone subset** of the `szl-holdings/platform` monorepo. The `web/` directory
(React SPA) cannot run standalone — it depends on 22+ `workspace:*` packages from the parent
monorepo. The buildable/testable surface is the **standalone packages** and the **root-level
test suites**.

### Running tests

| Component | Command | Notes |
|-----------|---------|-------|
| `packages/a11oy-knowledge` | `cd packages/a11oy-knowledge && npm test` | Vitest. 26/27 pass (1 pre-existing failure in TH2 proof sketch). |
| `__tests__/` (compliance + adversarial) | `npx jest __tests__/` | Jest/ts-jest. 106/110 pass (4 pre-existing failures). Requires root-level symlinks — see below. |
| `packages/qec-integrity` | `npx tsx packages/qec-integrity/src/qec_lineage.test.ts` | Custom runner, `node:assert/strict`. 24/24 pass. (receipt-chain lineage suite) |
| `web/packages/a11oy-core` (vitest) | `cd web/packages/a11oy-core && npx vitest run` | Only `lid-check.test.ts` uses vitest API (15 tests). |
| `web/packages/a11oy-core` (custom) | `npx tsx web/packages/a11oy-core/src/<subdir>/__tests__/<file>.test.ts` | 7 test files use `node:assert/strict` custom runners: quaternion-state (16), madhava-bound (8), pac-bayes-bound (8), composition-ring (7), false-position (7), akhmim-table (9), quadratic-solver (7). Run each with `npx tsx`. |
| `web/packages/a11oy-core` (KS-18) | `npx tsx web/packages/a11oy-core/src/quantum/__tests__/kochen-specker-18.test.ts` | 3 tests. |

### Symlinks required for `__tests__/`

The compliance/adversarial Jest tests reference files via relative paths from
`__tests__/compliance/`:
- `../../a11oy-knowledge.schema.json` → must exist at repo root
- `../../policies/vertical` → must exist at repo root

These are set up by the update script as symlinks to `packages/knowledge/`:
```
ln -sf packages/knowledge/a11oy-knowledge.schema.json a11oy-knowledge.schema.json
mkdir -p policies
ln -sf ../packages/knowledge/vertical policies/vertical
```

### Benchmarks

- `npx tsx packages/measurement/composition_overhead.ts` — Λ-axis composition latency
- `npx tsx packages/measurement/merkle_dag_p50.ts` — Merkle DAG write latency

### Known build limitations

- **`web/` SPA cannot start**: depends on `workspace:*` packages and `vite.config.ts` from the
  parent monorepo.
- **`packages/a11oy-knowledge` build (`tsc`) fails**: pre-existing type errors (e.g.,
  `import assert`, `ProposedAxiom` schema mismatches). Tests still pass via vitest.
- **`web/packages/a11oy-core` and `a11oy-connection` build (`tsc`) fails**: `tsconfig.json`
  extends `../../../../tsconfig.base.json` which only exists in the parent monorepo. A stub at
  `/tsconfig.base.json` is needed for vitest (handled by setup).
- **No root `pnpm-workspace.yaml` or `pnpm-lock.yaml`**: this repo uses npm for per-package installs.
- **No linting**: `biome lint` is configured in `web/package.json` but requires the parent
  monorepo's biome.json and Vite setup.
</content>
