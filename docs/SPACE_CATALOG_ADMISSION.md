<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Space catalog admission decision

Status: **PROPOSED SOURCE POLICY / runtime integration ROADMAP**.

Keep the existing five public product doors as production candidates. Additional
public Hub repositories are research/staging without production qualification,
not automatically new product entries. Unknown additions require review. Catalog
membership is not application readiness, data approval or permission to execute.

The [machine-readable decision](../data/space-catalog-admission-decision.json)
records the September 24 public inventory observation and the selected admission
requirements. It is a review input, not a second inventory collector or publisher.
The user delegated this choice during the ecosystem audit; this document does not
fabricate independent review or source admission.

The existing `/api/a11oy/v1/spaces/health` reported five canonical entries and 21
observed public applications. Five app probes succeeded in that observation, while
inventory equality remained DEGRADED. Those facts do not qualify the other 16.
This file makes no current runtime promise: see the live endpoint for fresh state.

## Non-production does not mean safe to expose

`david-leads` remains subject to the existing folded-PII visibility review. Other
existing fold, private and Unify decisions are not reversed by a research label.
Do not publish private data, unpause applications, erase records or change Hub
visibility as an automatic consequence of this classification.

## Integration boundary

Runtime classification and display are ROADMAP until the existing source-inventory
workstream admits this policy. [PR #2152](https://github.com/szl-holdings/a11oy/pull/2152)
already owns inventory review/publication readback; do not add a parallel collector
or publisher. The shared Space module also has a cross-repository parity contract.

A future compatible API must show production membership, research/staging,
unclassified additions and live health separately. It must retain missing-entry,
upstream/schema, exact-contract and dependency failures. Classification cannot
turn an unreachable engine, stale telemetry or malformed response into LIVE.

Promotion requires admitted source, canonical publication/readback, exact deployed
identity, API and data/authentication review, a witnessed backend request, and
receipt verification where required. No training, model adoption, publication or
deployment follows merely from accepting this source decision.
