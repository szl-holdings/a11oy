<!--
SPDX-License-Identifier: Apache-2.0
© 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11 LOCKED
-->

# Investor smoke gate (S1–S12)

Fail-closed HTTP + static contract. **Do not merge until QHAPAQ names the
required checks green.** Encodes assertions only. Does not rewrite
`data/genome.json`, does not weaken Immutable HF repository byte parity
(Dockerfile untouched), does not POST, does not add HEAD handlers or signer
fields (those landed in **1394** on main), and does not touch PR 1363 or
PR 1396. **Do not invent LIVE.** a11oy.net dual-origin smokes are a later cut.

Workflow: `.github/workflows/investor-smoke-gate.yml`

| Job (exact check-run name) | What it proves |
|---|---|
| `Investor smoke contract (S1-S12 static)` | Fixtures, skip-as-green rejection, S12 YAML, D-rows, L-row SNAPSHOT date |
| `Investor smoke bind (S7 kernel chips → /honest 8)` | Kernel chips bind to `/honest` `locked_formula_count` (8 or N/A) |
| `Investor smoke live probes` | GET/HEAD against `https://a-11-oy.com` only (measured, never invented) |

This pull request cannot certify those names as control-plane-required. See
`.github/BRANCH_PROTECTION.md`.

## Owners

| Defect | Owner | This PR |
|---|---|---|
| S7 console `#cnt-locked` still missing | **PR 1396** (do not touch here) | Fail-closed bind. Landing `#pt-locked` via `loadKernelLocked` and trust `#cnt-locked` are on main via 1394. Console `#cnt-locked` is still required. Genome `LOCKED-PROVEN=25` is a real catalog tier. |
| S1 HEAD vs GET | **1394 on main** | Probe only. Live origin is measured; source HEAD is not LIVE. |
| S2 signer contract | **1394 on main** | Probe only. `DSSE-LIVE` only on `/api/a11oy/healthz` rollup.signer; lean health JSON is `ABSENT` / `UNAVAILABLE`. |
| S3 unlabeled live coords | this gate | Fail-closed: UNAVAILABLE, MEASURED **with method**, or unit-labelled. Do not invent MEASURED. |
| PR 1366 memory covenant PG18 | out of scope | **RED**. Not this gate. |
| PR 1363 | HOLD | Do not touch. |

## S7 — kernel-chip bind (both numbers are real)

The fail is the **bind**, not the catalog count.

- Genome `LOCKED-PROVEN=25` is a **catalog** tier. It may remain, labelled, never
  green, never the kernel.
- `GET /api/a11oy/v1/honest` `locked_formula_count=8` is the **kernel**.
- Lean-8 ≠ genome-144. D5 stays a catalog-size label.

PASS only when **all** of these bind the kernel chip to
`GET /api/a11oy/v1/honest` `locked_formula_count` (show **8 or N/A**):

1. `a11oy_landing.html` `#pt-locked` via `loadLockedKernel` **or** 1394
   `loadKernelLocked` — **not** `setTiers.locked` from genome, **not**
   `proof_tiers.locked`
2. `web/trust.html` `#cnt-locked` — **not** genome `tier_counts['LOCKED-PROVEN']`
3. `pages/console.html` `#cnt-locked` — same rule

Landing and Trust bind on current main (1394). Console `#cnt-locked` is still
absent, so the bind job stays **RED until PR 1396**. This PR does **not**
rewrite `data/genome.json` or implement that UI.

## Matrix

Verdicts: `PASS` · `FAIL` · `UNAVAILABLE` · `SNAPSHOT <date>` · `UNCONFIGURED`.
A missing probe is **FAIL**. `SNAPSHOT` without a date is rejected.
`UNAVAILABLE` is allowed only for S4 / S6 / S9. `UNCONFIGURED` is allowed only
for wire-D. L1–L6 are `SNAPSHOT 2026-08-28`.

| ID | Check | Honest result this PR encodes |
|---|---|---|
| S1 | HEAD must not 405/404 where GET is 200 | Source: 1394 on main. Live: measured only |
| S2 | `DSSE-LIVE` only on `/api/a11oy/healthz` rollup.signer; lean health `ABSENT`/`UNAVAILABLE` | Source: 1394 on main. Live: measured only |
| S3 | Live coords UNAVAILABLE, MEASURED with method, or unit-labelled; no raw unlabeled latitude in first viewport | Source: 1394 units. Live: measured only |
| S4 | Staging receipt-write | **UNAVAILABLE** (no POST) |
| S5 | Ledger GET does not mint | PASS |
| S6 | Refuse / abstain | **UNAVAILABLE** (no POST) |
| S7 | Kernel chips → `/honest` `locked_formula_count` (8 or N/A) | **FAIL** until PR 1396 console `#cnt-locked` |
| S8 | Designed JSON 404 | PASS |
| S9 | Authz empty-state | **UNAVAILABLE** |
| S10 | OG image 200 | PASS |
| S11 | HF Space 200 | PASS |
| S12 | README YAML | PASS |
| L1–L6 | Stress | **SNAPSHOT 2026-08-28** |
| D5 | Catalog size 144 ≠ kernel 8 | PASS (size label; catalog LOCKED-PROVEN=25 is not the kernel) |
| D10 | Screenshots | **SNAPSHOT 2026-07-25** |
| wire-D | Wire D attestation (roadmap, not claimed) | not live |
| PR 1366 | Memory covenant | **RED out of scope** |

## Out of scope (standing)

- Never merge PR 1363 (HOLD).
- Do not touch PR 1396.
- PR 1366: **RED**, out of scope.
- No Dockerfile / hf-sync admission-input changes.
- No POST.
- No genome.json rewrite.
- Do not invent LIVE from source-only 1394.
- a11oy.net dual-origin smokes: later cut.

## Measured live

Canonical origin `https://a-11-oy.com`. Re-probe after deploy; do not copy
source PASS onto the live job.

See the pull-request body for the last measured live matrix.

## Run locally

```bash
python3 -m pytest -q tests/test_investor_smoke_gate.py
python3 -m pytest -q tests/test_investor_smoke_bind.py   # RED until PR 1396 console chip
python3 scripts/investor_smoke_gate.py --mode live --origin https://a-11-oy.com
```
