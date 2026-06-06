# Sentra — Quality Sweep Checklist

**Purpose:** Pre-release verification checklist for Sentra defensive SOC platform.

---

## Architecture Checks

- [x] `sentra-store.ts` — In-memory reactive store; single source of truth; 1389 lines; seed produces 200+ assets, 50+ incidents, 100+ approvals, 500+ audit entries
- [x] `policy-engine.ts` — `runPolicyGate()` enforces allowlist, ownership, approval; returns `PolicyGateResult` with `allowed`, `reason`, `doctrine_citations`
- [x] `integration-adapters.ts` — 16 stub adapters; Safety Gate enforced on all `executeAction()` calls; no real outbound calls
- [x] All pages import from `@/lib/sentra-store` — no page has its own mocked data
- [x] All pages call `ensureSeeded()` via `useSentraStore()` — consistent data across navigation

## Defensive Doctrine Checks

- [x] No page renders an "attack" or "offensive" action button
- [x] Containment Actions page shows action class as `ALLOWED` or `DOCUMENTATION ONLY` — never executable for denied classes
- [x] Asset Registry `ownership_status` badge shown on every asset row; non-executable statuses highlighted in amber/red
- [x] Incident Detail v2 — Contain tab shows Safety Gate block for non-owned assets
- [x] Policy Enforcement Log shows only real `policyLogs` from store — no mocked data
- [x] Audit Trail verify button calls `sentraStore.verifyAuditChain()` and surfaces `checkedEntries` + `firstInvalidId`
- [x] `SENTRA_DENIAL_MESSAGE` matches exactly: "Action blocked by Sentra Policy Enforcement: target is not registered as an owned or authorized tenant asset, or the action is outside defensive scope."

## UI / Navigation Checks

- [x] Sentra App.tsx — `sentra-command` nav section wired with 9 items
- [x] `/incidents/:id` route registered as standalone `<Route>` — correctly parameterized
- [x] A11oy App.tsx — `SentraOps` lazy import + route at `${base}/sentra-ops`
- [x] A11oy layout.tsx — `SENTRA OPS ⬡` nav group visible
- [x] Both Vite dev servers started and serving without errors

## Data Integrity Checks

- [x] `verifyAuditChain()` iterates all 500+ audit entries; checks prev_hash linkage
- [x] `verifyEvidencePack()` computes and compares Merkle roots
- [x] `computeBlastRadius()` returns `BlastRadiusPreview` with downstream_services, revoked_sessions, rollback_cost
- [x] `sessionDigest` array captures all store mutations in the current session

## A11oy Orchestration Checks

- [x] `SentraOps.tsx` — 7 agents with charters, allowed_action_classes, status
- [x] Kill Switch state tracked in React state; all agent cards reflect it
- [x] Dry-Run Mode toggle present and wired
- [x] 6 jobs with Deploy + Dry-Run buttons; last-run metadata shown
- [x] Orchestration Policy Guard panel renders doctrine enforcement table

## Known Limitations (In-App Demo)

- Integration adapters are stubs — no real outbound API calls are made
- Evidence Merkle computation uses `simpleHash()` (djb2 variant) — not cryptographic SHA-256
- Audit chain `entry_hash` uses `simpleHash()` — suitable for demo; production would use Web Crypto API
- All data resets on page reload (in-memory store; no persistence layer)
