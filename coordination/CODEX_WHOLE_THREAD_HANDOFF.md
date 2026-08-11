<!-- SZL-CODEX-WHOLE-THREAD-FINISH-V1 -->
# Codex Primary Handoff — Whole SZL Thread

The canonical cross-repository execution contract is published in:

- Organization issue: https://github.com/szl-holdings/.github/issues/415
- Organization PR: https://github.com/szl-holdings/.github/pull/414
- Canonical workcell: `szl-holdings/.github/coordination/codex/whole-thread-finish-2026-08-11/CODEX_WORKCELL.md`
- Machine workgraph: `szl-holdings/.github/coordination/codex/whole-thread-finish-2026-08-11/WORKGRAPH.json`
- Coordination payload head: `4f6a8536e79c2101811b24645e8d13e91296a638`

Use A11oy as the primary control plane for executing the workcell. Begin by recapturing current state and writing the required coordination evidence. Then execute the A11oy public-truth and terminal-health lane, followed by the dependency-linked Hugging Face, model/Forge, database, MCP, responsive presentation, deployment, and final-proof workstreams through separate protected repository branches and pull requests.

Do not stop at a review, plan, mock, local-only patch, or issue handoff. Preserve repository rulesets, managed-secret boundaries, exact-head checks, license/provenance gates, immutable holdouts, database backup/restore requirements, and exact-revision deployment receipts.

Allowed workstream terminal states:

- `VERIFIED_CURRENT`
- `TERMINAL_FAILURE`
- `BLOCKED_MANAGED_PREREQUISITE`

The final response must be an evidence matrix with repository, base OID, PR, merged OID, deployed OID or digest, tests, receipt, terminal status, and residual risk for every workstream.