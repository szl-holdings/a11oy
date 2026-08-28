<!--
SPDX-License-Identifier: Apache-2.0
© 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11 LOCKED
-->

# Investor smoke gate (S1–S12)

Fail-closed HTTP + static contract for investor-honest claims. **Do not merge this
bootstrap as a substitute for INTI / KALLPA product fixes.** This PR encodes the
assertions. It does not rewrite `data/genome.json`, does not weaken Immutable HF
repository byte parity (Dockerfile untouched), does not POST, and does not touch
PR 1363 or PR 1366.

Workflow: `.github/workflows/investor-smoke-gate.yml`

| Job (exact check-run name) | What it proves |
|---|---|
| `Investor smoke contract (S1-S12 static)` | Fixtures, skip-as-green rejection, genome labelling, S12 YAML, D-rows, L-row SNAPSHOT date |
| `Investor smoke bind (S7 kernel slot)` | `cnt-locked` / `setTiers.locked` must source `/api/a11oy/v1/honest` `locked_formula_count` (8) |
| `Investor smoke live probes` | GET/HEAD against `https://a-11-oy.com` and `https://a11oy.net` |

This pull request cannot certify those names as control-plane-required. See
`.github/BRANCH_PROTECTION.md`.

## Owners

| Defect | Owner | This PR |
|---|---|---|
| Trust Center `cnt-locked` and landing `setTiers.locked` bind genome 25 into the kernel slot | **INTI** (identity a11oy agent) | Bind assertion only. Re-probe after INTI's PR. |
| HEAD 405 vs GET 200 on `/console`, `/trust`, `/healthz`, `/readyz`, `/api/health`; HEAD `/api/a11oy/healthz` 404 vs GET 200; signer enum missing on `/api/health`, `/healthz`, `/api/a11oy/v1/health` | **KALLPA** | Probes only. No HEAD handlers, no signer fields added here. |
| Memory covenant PG18 (PR 1366) | out of scope | Documented RED. Not this gate. |

## S7 bind (do not rewrite genome)

Two real numbers:

| Count | Source | Meaning |
|---|---|---|
| **8** | `GET /api/a11oy/v1/honest` → `locked_formula_count` / `locked_formula_ids` | Locked-proven **kernel** `{F1, F4, F7, F11, F12, F18, F19, F22}` |
| **144** entries / **25** `LOCKED-PROVEN` tags | `GET /api/a11oy/v1/genome` → `count` / `tier_counts['LOCKED-PROVEN']` | Genome **catalog** (duplicates + extra Q1/Q2 rows). May remain, **labelled separately**. |

**Lean-8 ≠ genome-144** is a labelling rule, not a deletion. This gate **must not**
assert `tier_counts['LOCKED-PROVEN'] == 8` and **must not** demand 25 be deleted.

**The fail is the BIND:**

- `web/trust.html` `cnt-locked` currently assigns `tc['LOCKED-PROVEN']` from `/genome`.
- `a11oy_landing.html` `loadGenomeTiers()` calls `setTiers({ locked: tc["LOCKED-PROVEN"], ... })`.
- `loadOverview()` calls `setTiers(o.proof_tiers)` whose `locked` is the same genome catalog count.

Those kernel slots must source `/api/a11oy/v1/honest` `locked_formula_count` (8), labelled.
If they still read genome 25 into that slot → **RED**.

Tiny fixtures (detector self-test only):

- `tests/fixtures/investor_smoke/kernel_slot_genome_bind.html` — must RED
- `tests/fixtures/investor_smoke/kernel_slot_honest_bind.html` — kernel from `/honest`; genome 25 allowed on a **different** labelled node

## Matrix

Verdicts: `PASS` · `FAIL` · `UNAVAILABLE` · `SNAPSHOT <date>` · `UNCONFIGURED`.
A missing probe is **FAIL** (skip-as-green rejected). `SNAPSHOT` without a date is
rejected. `UNAVAILABLE` is allowed only for S4 / S6 / S9. `UNCONFIGURED` is allowed
only for wire-D. L1–L6 are `SNAPSHOT 2026-08-28` (not executed; never "production-scale"
with no N).

| ID | Check | Honest result this PR encodes | Evidence |
|---|---|---|---|
| S1 | GET `/` 200 both origins (follow redirects) | Live probe | `https://a-11-oy.com/` · `https://a11oy.net/` |
| S2 | HEAD must not 405/404 where GET is 200; health JSON signer enum `{DSSE-LIVE, UNSIGNED-LOCAL, unavailable}` | Live FAIL until KALLPA | `/console` `/trust` `/healthz` `/readyz` `/api/health` plus HEAD `/api/a11oy/healthz`; signer on `/api/health` `/healthz` `/api/a11oy/v1/health`. Lean SHA `c7c0ba17` is **not** enough. GET `/api/a11oy/healthz` already has `rollup.signer.status`. |
| S3 | Live-fetch numbers labelled MEASURED or UNAVAILABLE | Live FAIL if ISS coords are bare digits | `/api/a11oy/v1/live/iss` is the surface (`/live-fetch/status` may 404) |
| S4 | Staging receipt-write | **UNAVAILABLE** (no URL; no POST) | — |
| S5 | Ledger GET does not mint | Static PASS (handlers are GET summary / `receipt_minted: False`); live confirms | `szl_energy_ledger.handle_ledger` · `GET /api/a11oy/v1/ledger` |
| S6 | Refuse / abstain | **UNAVAILABLE** (no live path; no POST) | `szl_willay_gateway` |
| S7 | Kernel slot bind | Static **FAIL** until INTI | `tests/test_investor_smoke_bind.py` |
| S8 | Designed 404 | Static PASS (soft-404 guard); live JSON 404 | `szl_runtime_contracts._install_soft_404_guard` |
| S9 | Authz empty-state | **UNAVAILABLE** (gated routes unpublished) | — |
| S10 | OG image 200 | Live probe | `/og-card.png` · `/social-preview-v5.png` · `/social-preview-series-a.png` |
| S11 | HF Space 200 | Live probe | `https://szlholdings-a11oy.hf.space/` |
| S12 | README card YAML | Static PASS | `README.md` frontmatter |
| L1–L6 | Stress | **SNAPSHOT 2026-08-28** | Not run |
| D1 | JSON-LD identity | Static | `a11oy_landing.html` `application/ld+json` |
| D2 | Views routed or ROADMAP | Static | `pages/console.html` `VIEWS` |
| D3 | No unlabelled hero digit | Static | `#hs-proven` labelled Locked Lean-proven |
| D4 | Λ = Conjecture 1 | Static | landing |
| D5 | Lean-8 ≠ genome-144 | Static PASS as labelling (not deletion) | `data/genome.json` + `/honest` |
| D6 | Deprecation in first 20 lines | Static | `docs/doctrine/DOCTRINE_V11_LOCKED.md` |
| D7 | Cross-surface locked-8 ids | Static | landing |
| D8 | request-id on 5xx | Static | `szl_prod_hardening.py` |
| D9 | CSP test exists | Static | `tests/test_security_headers.py` |
| D10 | Screenshot freshness | **SNAPSHOT 2026-07-25** | `audit/screenshot-catalog.md` |
| wire-D | Signing / SLSA L2 | **UNCONFIGURED** | `GET /wires/D` (L2 roadmap, not claimed) |

## Required vs noise workflows

Root `.github/workflows/` currently holds **130** YAML files. Nested copies under
`docs/` and `proofs/` exist for other packages. **Do not mass-delete.** Required
contexts are listed in `.github/BRANCH_PROTECTION.md`. `smoke-monitor.yml` is a
tolerant 6-hour schedule (majority-down only) and is **not** this fail-closed gate.

## Out of scope (standing)

- Never merge PR 1363 (HOLD).
- PR 1366 memory covenant: **RED**, out of scope.
- No Dockerfile / hf-sync admission-input changes.
- No POST to live endpoints.
- No genome.json rewrite.

## Measured live (2026-08-28, GET/HEAD only, no POST)

Primary origin `https://a-11-oy.com` plus `https://a11oy.net`. This is a probe
record, not a claim that production is green.

| ID | Status | Evidence |
|---|---|---|
| S1 | PASS | GET `/` → 200 on both origins |
| S2 | FAIL (KALLPA) | HEAD `/console` `/trust` `/healthz` `/readyz` `/api/health` = 405 while GET = 200; HEAD `/api/a11oy/healthz` = 404 while GET = 200; GET `/api/health`, `/healthz`, `/api/a11oy/v1/health` have no signer enum. Lean SHA is not enough. |
| S3 | FAIL | `GET /api/a11oy/v1/live/iss` `mode=live` with unlabeled `latitude` / `longitude` / `altitude` / `velocity` |
| S4 | UNAVAILABLE | no staging URL |
| S5 | PASS | GET `/api/a11oy/v1/ledger` and `/energy/ledger` → 200, no mint |
| S6 | UNAVAILABLE | no live refuse path |
| S7 | FAIL (INTI) | source bind still genome→kernel slot. Live `GET /api/a11oy/v1/honest` **does** expose `locked_formula_count=8` (bind target exists). |
| S8 | PASS | undeclared `*.js` → JSON 404 |
| S9 | UNAVAILABLE | gated routes unpublished |
| S10 | PASS | `/og-card.png`, `/social-preview-v5.png`, `/social-preview-series-a.png` → 200 `image/png` |
| S11 | PASS | `https://szlholdings-a11oy.hf.space/` → 200 |
| S12 | PASS | README YAML |
| Try Khipu source | PASS | `pages/console.html` `#try-khipu-panel` (after #1390) |
| Try Khipu live HTML | FAIL | GET `/console` 200 without `try-khipu-panel` (Space not yet carrying that SHA; do not invent the string) |
| L1–L6 | SNAPSHOT 2026-08-28 | not executed |
| wire-D | UNCONFIGURED | L2 roadmap |

## Run locally

```bash
python3 -m pytest -q tests/test_investor_smoke_gate.py
python3 -m pytest -q tests/test_investor_smoke_bind.py   # RED until INTI
python3 scripts/investor_smoke_gate.py --mode live \
  --origin https://a-11-oy.com --origin https://a11oy.net
```
