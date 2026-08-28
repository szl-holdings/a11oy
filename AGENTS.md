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
- **LOCKED vs EXPERIMENTAL.** There are **8** locked-proven formulas
  `{F1, F4, F7, F11, F12, F18, F19, F22}` (no-axiom theorem `locked_count_eight`). **Never inflate
  the locked count.** Λ-uniqueness is **Conjecture 1**; Khipu BFT safety is **Conjecture 2** —
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

- **GitHub ↔ HF Space drift:** `hf-sync.yml` is the only automatic writer for the canonical
  Space. It derives the complete deployment set from Dockerfile `COPY` sources, publishes it,
  binds the exact GitHub SHA, and attests the immutable Space commit. Never add a second
  automatically triggered Space writer. Check `/api/build-info` and the Space API commit before
  claiming relock. Staging Space ≠ prod DNS. Apex `a-11-oy.com` stays Cloudflare
  orange-cloud (proxied). Stephen may add `_huggingface.a-11-oy.com` TXT later
  without dropping that proxy. Do not grey-cloud. Do not stamp HF custom domain
  LIVE. HF custom domain stays PENDING/UNAVAILABLE. This repo does not change DNS.
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

This is a **standalone subset** of the `szl-holdings/platform` monorepo. The root
`pnpm-workspace.yaml` makes the doctrine packages reproducibly installable, buildable, and
testable from a clean clone. The broader `web/` React SPA still depends on packages and
configuration from the parent monorepo; do not infer that the full SPA is standalone from the
doctrine-package build.

### Running tests

| Component | Command | Notes |
|-----------|---------|-------|
| `packages/a11oy-knowledge` | `cd packages/a11oy-knowledge && npm test` | Vitest. 26/27 pass (1 pre-existing failure in TH2 proof sketch). |
| `__tests__/` (compliance + adversarial) | `npx jest __tests__/` | Jest/ts-jest. Tests read canonical fixtures under `packages/knowledge/`, including on hosts that do not materialize Git symlinks. |
| `packages/qec-integrity` | `npx tsx packages/qec-integrity/src/qec_lineage.test.ts` | Custom runner, `node:assert/strict`. 24/24 pass. (receipt-chain lineage suite) |
| Doctrine workspace | `pnpm install --frozen-lockfile && pnpm test:doctrine && pnpm typecheck:doctrine && pnpm build:doctrine` | Clean-clone gate for `@a11oy/core` and `@a11oy/connection`. |
| `web/packages/a11oy-core` (custom) | `pnpm --dir web/packages/a11oy-core run test:standalone` | Runs the nine standalone doctrine test files, including KS-18. |

### Canonical fixtures for `__tests__/`

The compliance/adversarial Jest tests read the schema and vertical policies directly
from `packages/knowledge/`. Root-level symlinks remain compatibility entry points for
external consumers, but the test suite does not depend on the host materializing them.

### Benchmarks

- `npx tsx packages/measurement/composition_overhead.ts` — Λ-axis composition latency
- `npx tsx packages/measurement/merkle_dag_p50.ts` — Merkle DAG write latency

### Known build limitations

- **The broader `web/` SPA cannot start standalone**: it still depends on packages and
  configuration from the parent monorepo. The doctrine packages covered by
  `build:doctrine` are independently buildable.
- **`packages/a11oy-knowledge` build (`tsc`) fails**: pre-existing type errors (e.g.,
  `import assert`, `ProposedAxiom` schema mismatches). Tests still pass via vitest.
- **No linting**: `biome lint` is configured in `web/package.json` but requires the parent
  monorepo's biome.json and Vite setup.
</content>
