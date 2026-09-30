<!--
SPDX-License-Identifier: Apache-2.0
© 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11 LOCKED
-->

# Investor smoke gate (S1–S12)

Fail-closed source contracts plus fail-closed provider monitoring. The workflow
does not rewrite `data/genome.json`, weaken Immutable HF repository byte parity,
POST to the runtime, add HEAD handlers or signer fields, or infer application
health from a static page. **Do not invent LIVE.**

Provider liveness is not a pull-request admission check. Pull requests prove the
deterministic repository contract and the S7 source bind. The static apex and
canonical runtime are measured after a protected-main push, on the six-hour
schedule, and by manual dispatch. A failed provider measurement must remain red
in those monitor events; it cannot be relabelled green, but it also cannot
prevent an unrelated source-only security or documentation repair from merging.
A skipped live job on a pull request is a declared lifecycle state, not a health
claim.

## Public-origin contract

- Static product front door: `https://a-11-oy.com`
- Canonical application runtime: `https://szlholdings-a11oy.hf.space`
- Independent proof origin: `https://a11oy.net`

The static front door is not an API origin. It is probed independently for a
reachable HTTP 200 root. S1–S12 runtime routes, API responses, HEAD/GET parity,
signer state, ledger behavior, and source-bound application checks run against
the canonical Hugging Face Space until an independently proved edge proxy
changes that architecture.

Workflow: `.github/workflows/investor-smoke-gate.yml`

| Job (exact check-run name) | Events | What it proves |
|---|---|---|
| `Investor smoke contract (S1-S12 static)` | PR, protected-main push, schedule, manual | Fixtures, origin separation, skip-as-green rejection, S12 YAML, D-rows, L-row SNAPSHOT date |
| `Investor smoke bind (S7 kernel chips → /honest 8)` | PR, protected-main push, schedule, manual | Kernel chips bind to `/honest` `locked_formula_count` (8 or N/A) |
| `Investor smoke live probes` | Protected-main push, six-hour schedule, manual; explicitly skipped on PR | Static apex reachability plus GET/HEAD assertions against the canonical application runtime; no POST |

The two deterministic jobs are suitable source-admission checks. The live job is
a post-merge and scheduled provider monitor. Requiring that live job on pull
requests would couple repository admission to unrelated DNS, edge, hosting, and
runtime availability and recreate the deadlock this lifecycle removes.

## Owners

| Defect | Owner | This gate |
|---|---|---|
| S7 console `#cnt-locked` | **PR 1396** (merged `c038cc95`) | Fail-closed bind. Landing `#pt-locked` via `loadKernelLocked`, trust `#cnt-locked` (1394), and console `#cnt-locked` (1396) must stay bound to `/honest`. Genome `LOCKED-PROVEN=25` is a real catalog tier. |
| S1 HEAD vs GET | **1394 on main** | Probe only. Runtime is measured; source HEAD is not LIVE. |
| S2 signer contract | **1394 on main** | Probe only. `DSSE-LIVE` only on `/api/a11oy/healthz` rollup.signer; lean health JSON is `ABSENT` / `UNAVAILABLE`. |
| S3 unlabeled live coords | this gate | Fail-closed: UNAVAILABLE, MEASURED **with method**, or unit-labelled. Do not invent MEASURED. |
| Static apex reachability | Pages front door | Root must return HTTP 200; no application API capability is inferred. |
| Provider monitor lifecycle | this workflow | Live failures remain red after protected merge and on schedule; they do not gate unrelated source PRs. |
| PR 1366 memory covenant PG18 | out of scope | **RED**. Not this gate. |
| PR 1363 | HOLD | Do not touch. |

## S7 — kernel-chip bind (both numbers are real)

The fail is the **bind**, not the catalog count.

- Genome `LOCKED-PROVEN=25` is a **catalog** tier. It may remain labelled, never
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

Landing, Trust, and Console bind on current main (1394 + **1396**
`c038cc95`). This gate does **not** rewrite `data/genome.json` or re-implement
that UI.

## Matrix

Verdicts: `PASS` · `FAIL` · `UNAVAILABLE` · `SNAPSHOT <date>` · `UNCONFIGURED`.
A missing runtime probe is **FAIL**. `SNAPSHOT` without a date is rejected.
`UNAVAILABLE` is allowed only for S4 / S6 / S9. `UNCONFIGURED` is allowed only
for wire-D. L1–L6 are `SNAPSHOT 2026-08-28`.

| ID | Check | Honest result this gate encodes |
|---|---|---|
| S1 | HEAD must not 405/404 where GET is 200 | Source: 1394 on main. Canonical runtime: measured only |
| S2 | `DSSE-LIVE` only on `/api/a11oy/healthz` rollup.signer; lean health `ABSENT`/`UNAVAILABLE` | Source: 1394 on main. Canonical runtime: measured only |
| S3 | Live coords UNAVAILABLE, MEASURED with method, or unit-labelled; no raw unlabeled latitude in first viewport | Source: 1394 units. Runtime: measured only. One ISS TimeoutError retry; persistent timeout is FAIL |
| S4 | Staging receipt-write | **UNAVAILABLE** (no POST) |
| S5 | Ledger GET does not mint | Runtime probe |
| S6 | Refuse / abstain | **UNAVAILABLE** (no POST) |
| S7 | Kernel chips → `/honest` `locked_formula_count` (8 or N/A) | In-repo bind plus canonical runtime `/honest` |
| S8 | Designed JSON 404 | Runtime probe |
| S9 | Authz empty-state | **UNAVAILABLE** |
| S10 | OG image 200 | Runtime probe |
| S11 | HF Space 200 | Canonical runtime root |
| S12 | README YAML | Static repository contract |
| L1–L6 | Stress | **SNAPSHOT 2026-08-28** |
| D5 | Catalog size 144 ≠ kernel 8 | PASS (size label; catalog LOCKED-PROVEN=25 is not the kernel) |
| D10 | Screenshots | **SNAPSHOT 2026-07-25** |
| wire-D | Wire D attestation (roadmap, not claimed) | not live |
| PR 1366 | Memory covenant | **RED out of scope** |

## Out of scope and standing boundaries

- Never merge PR 1363 (HOLD).
- PR 1396 is merged; do not re-edit console chrome in this gate.
- PR 1366 remains red and out of scope.
- No Dockerfile or hf-sync admission-input changes.
- No POST.
- No `genome.json` rewrite.
- Do not infer application health from the static front door.
- Do not invent LIVE from source-only evidence.
- `a11oy.net` dual-origin smokes remain separate.

## Measured-live lifecycle

The live job performs two independent measurements:

1. `https://a-11-oy.com/` must be a reachable static product front door.
2. `https://szlholdings-a11oy.hf.space` must satisfy the fail-closed runtime
   S1–S12 GET/HEAD assertions.

A pass on either origin does not substitute for a pass on the other. These
measurements run on every protected-main push, every six hours, and on manual
dispatch. A provider outage therefore remains continuously observable even when
a source PR is intentionally isolated from that external failure.

## Run locally

```bash
python3 -m pytest -q tests/test_investor_smoke_gate.py tests/test_investor_smoke_origin_contract.py
python3 -m pytest -q tests/test_investor_smoke_bind.py
python3 scripts/investor_smoke_gate.py --mode live --origin https://szlholdings-a11oy.hf.space
```
