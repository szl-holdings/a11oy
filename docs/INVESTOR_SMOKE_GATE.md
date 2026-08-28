<!--
SPDX-License-Identifier: Apache-2.0
© 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11 LOCKED
-->

# Investor smoke gate (S1–S12)

AYNI cut. Fail-closed HTTP + static contract. **Do not merge.** Encodes assertions
only. Does not rewrite `data/genome.json` or Trust Center copy, does not weaken
Immutable HF repository byte parity (Dockerfile untouched), does not POST, does
not add HEAD handlers or signer fields, and does not touch PR 1363 or PR 1366.
**a11oy.net and kernel smokes are a later cut.**

Workflow: `.github/workflows/investor-smoke-gate.yml`

| Job (exact check-run name) | What it proves |
|---|---|
| `Investor smoke contract (S1-S12 static)` | Fixtures, skip-as-green rejection, S12 YAML, D-rows, L-row SNAPSHOT date |
| `Investor smoke bind (S7 LOCKED-PROVEN=8)` | genome `tier_counts.LOCKED-PROVEN` must equal `/honest` `locked_formula_count` (8) |
| `Investor smoke live probes` | GET/HEAD against `https://a-11-oy.com` only |

This pull request cannot certify those names as control-plane-required. See
`.github/BRANCH_PROTECTION.md`.

## Owners

| Defect | Owner | This PR |
|---|---|---|
| S7 genome `LOCKED-PROVEN` 25 vs `/honest` 8 | **INTI** | Fail-closed assertion. Keep RED until every surface agrees, labelled. Do not rewrite genome or Trust Center copy. |
| S1 HEAD 405 vs GET 200 | **KALLPA** | Probes only. No HEAD handlers. |
| S2 signer enum missing | **KALLPA** | Probes only. No signer fields. Lean SHA is not enough. |
| S3 unlabeled live coords | this gate | Fail-closed: UNAVAILABLE or MEASURED **with method**. Do not invent MEASURED. |
| PR 1366 memory covenant PG18 | out of scope | **RED**. Not this gate. |

## S7 — count agreement (do not fake it)

Fail-closed assertion:

`genome tier_counts.LOCKED-PROVEN` **must equal** `/api/a11oy/v1/honest` `locked_formula_count` **= 8**.

Today the repo genome tags 25 LOCKED-PROVEN rows while `/honest` reports 8.
INTI owns the real count. This PR does **not** rewrite `data/genome.json` or
Trust Center copy to make them look equal.

Catalog **size** 144 is not the locked kernel (D5 labels that). Tag-count
agreement is S7.

## Matrix

Verdicts: `PASS` · `FAIL` · `UNAVAILABLE` · `SNAPSHOT <date>` · `UNCONFIGURED`.
A missing probe is **FAIL**. `SNAPSHOT` without a date is rejected.
`UNAVAILABLE` is allowed only for S4 / S6 / S9. `UNCONFIGURED` is allowed only
for wire-D. L1–L6 are `SNAPSHOT 2026-08-28`.

| ID | Check | Honest result this PR encodes |
|---|---|---|
| S1 | HEAD must not 405/404 where GET is 200 | Live FAIL until KALLPA |
| S2 | Health JSON signer enum `{DSSE-LIVE, UNSIGNED-LOCAL, unavailable}` | Live FAIL until KALLPA |
| S3 | Live coords UNAVAILABLE or MEASURED with method; no raw unlabeled latitude in first viewport | Live FAIL on `/live/iss` bare digits |
| S4 | Staging receipt-write | **UNAVAILABLE** (no POST) |
| S5 | Ledger GET does not mint | PASS |
| S6 | Refuse / abstain | **UNAVAILABLE** (no POST) |
| S7 | genome LOCKED-PROVEN == `/honest` 8 | **FAIL** until INTI |
| S8 | Designed JSON 404 | PASS |
| S9 | Authz empty-state | **UNAVAILABLE** |
| S10 | OG image 200 | PASS |
| S11 | HF Space 200 | PASS |
| S12 | README YAML | PASS |
| L1–L6 | Stress | **SNAPSHOT 2026-08-28** |
| D5 | Catalog size 144 ≠ kernel 8 | PASS (size label; tag agreement is S7) |
| D10 | Screenshots | **SNAPSHOT 2026-07-25** |
| wire-D | SLSA L2 | **UNCONFIGURED** |
| PR 1366 | Memory covenant | **RED out of scope** |

## Out of scope (standing)

- Never merge PR 1363 (HOLD).
- PR 1366: **RED**, out of scope.
- No Dockerfile / hf-sync admission-input changes.
- No POST.
- No genome.json or Trust Center rewrite.
- a11oy.net dual-origin smokes: later cut.
- Kernel smokes: later cut.

## Measured live (2026-08-28, GET/HEAD only, no POST)

Canonical origin `https://a-11-oy.com`. Re-probe after INTI / KALLPA identity PRs.

See the pull-request body for the live matrix recorded at ship time.

## Run locally

```bash
python3 -m pytest -q tests/test_investor_smoke_gate.py
python3 -m pytest -q tests/test_investor_smoke_bind.py   # RED until INTI
python3 scripts/investor_smoke_gate.py --mode live --origin https://a-11-oy.com
```
