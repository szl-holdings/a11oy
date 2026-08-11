<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->
<!-- SZL-CODEX-WHOLE-THREAD-FINISH-V1 -->
# Codex Primary Handoff — Whole SZL Thread

The canonical cross-repository execution contract is published in:

- Organization issue: https://github.com/szl-holdings/.github/issues/415
- Canonical organization PR: https://github.com/szl-holdings/.github/pull/416
- Canonical workcell: `szl-holdings/.github/coordination/codex/whole-thread-finish-2026-08-11/WORKCELL.md`
- Coordination branch: `codex/whole-thread-finish-2026-08-11-v2`
- Exact coordination payload head: `2d6101c8ef9ba766fa668c016ae827049206a990`
- Superseded organization PR: #414, replaced solely to satisfy exact DCO author identity.

Use A11oy as the primary control plane for executing the workcell. Begin by recapturing current state and writing the required coordination evidence. Then execute the A11oy public-truth and terminal-health lane, followed by the dependency-linked Hugging Face, model/Forge, database, MCP, responsive presentation, deployment, and final-proof workstreams through separate protected repository branches and pull requests.

Do not stop at a review, plan, mock, local-only patch, or issue handoff. Preserve repository rulesets, managed-secret boundaries, exact-head checks, license/provenance gates, immutable holdouts, database backup/restore requirements, and exact-revision deployment receipts.

Allowed workstream terminal states:

- `VERIFIED_CURRENT`
- `TERMINAL_FAILURE`
- `BLOCKED_MANAGED_PREREQUISITE`

The official Codex connector has acknowledged the PR mention but requires a Codex Cloud environment for this repository before cloud execution can begin. After environment provisioning, invoke Codex against this PR and the canonical organization issue.

The final response must be an evidence matrix with repository, base OID, PR, merged OID, deployed OID or digest, tests, receipt, terminal status, and residual risk for every workstream.