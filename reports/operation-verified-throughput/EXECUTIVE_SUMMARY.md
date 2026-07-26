<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Operation Verified Throughput executive summary

Generated at `2026-07-26T08:05:28+00:00` from tracked audit receipts.

## Outcome

| Workstream | Status | Evidence |
|---|---|---|
| Live Phase 0 inventory | MEASURED | 57 visible repositories; canonical detail captured in `audit/` |
| Critical-path source restore | MEASURED | 363 files; 0 mismatches; archive `5260a460dec5e807b6d133fc819dfa326fe24a8daa15a22e7c90b6c932a5ee5d` |
| Policy schemas and Ed25519 receipt boundary | IMPLEMENTED NOT DEPLOYED | `schemas/` and `packages/policy/src/verified/` |
| Runtime conformance | PASS | 105 assertions; receipt `audit/policy-runtime-verification.json` |
| Lean T1/T2 | PASS | Kernel check PASS; artifact `sha256:d5988892503c025a1158038744ab518d048bdd022c32e718d4ab8e67eced6380` |
| Declared doctrine/HF delivery path | IMPLEMENTED NOT DEPLOYED | PASS; deterministic payload `sha256:181c0fef1fbe8784e7d2acd7c832a10eeed2c7512eda9cc20b16203b246aa926` |
| Broader SPA build | FAILED | 12 requested workspace packages have no tracked manifest |
| Public proof-count change | RETIRED | No change; independent statement review and four-theorem gate are unmet |
| Production enforcement or traffic cutover | AWAITING AUTHORIZATION | Not attempted |

## Gate decision

**FAILED:** the operation is not operational. Cloud/cluster inventory, production backup
restore, independently verified staging provenance, admission rejection, identical-hardware
serving results, end-to-end telemetry, rollback, and independent review remain open.

Source baseline: `382ad2021c18ccb07e9be624edcf76eb163d777c`. This report describes branch work, not a deployment.
