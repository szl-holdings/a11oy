# Sentra — Demo Walkthrough

**Audience:** Internal demos, investor walkthroughs, SOC evaluator sessions.

---

## Quick Start

1. Open the Sentra app (preview pane → Sentra dropdown)
2. Navigate to **Sentra Command ⬡ → Command Center**
3. The Command Center displays live-computed metrics from the in-app data store (seed data: 50+ incidents, 200+ assets, 500+ audit entries, 100+ approvals)

---

## Key Demo Flows

### Flow 1 — Incident Detection → Containment Loop

1. **Command Center** — Note the active incident count and open approval queue badge.
2. **SOC Operations → Incidents** — Open any active incident.
3. Click an incident row → **Incident Detail v2** opens.
4. Tab: **Contain** — Shows executable containment actions for owned assets. Non-owned assets are shown with the Safety Gate denial overlay.
5. Tab: **Evidence** — Attach evidence items; Merkle root auto-computes.
6. Tab: **Attribution** — MITRE ATT&CK TTPs shown with counterfactual blast-radius preview.
7. Tab: **Escalate** — File executive escalation or law-enforcement referral.

### Flow 2 — Approval Queue

1. **Sentra Command ⬡ → Approval Queue**
2. Shows pending high-impact actions with blast-radius impact frames.
3. Approve or reject an action — decision is logged to Policy Enforcement Log and Audit Trail.

### Flow 3 — Evidence Vault → Chain of Custody

1. **Sentra Command ⬡ → Evidence Vault**
2. Filter by incident. Select an evidence item.
3. Click **Lock Evidence** — item becomes immutable, COC entry appended.
4. Click **Verify Merkle** — shows computed root vs. stored root.

### Flow 4 — Audit Trail Verification

1. **Sentra Command ⬡ → Audit Trail**
2. Click **Verify Chain** — iterates 500+ audit entries, validates prev/current hash chain.
3. Any tampered entry would appear as "INVALID" with the first failing entry ID surfaced.

### Flow 5 — Policy Enforcement Log

1. **Sentra Command ⬡ → Policy Enforcement Log**
2. Filter to `deny` decisions — shows every blocked action with denial reason and doctrine citation.
3. Demonstrates that offensive/external actions are blocked by default.

### Flow 6 — Reports Generator

1. **Sentra Command ⬡ → Reports Generator**
2. Select report type (Executive Brief, Technical IR, Law Enforcement Referral, etc.)
3. Select target incident. Click **Generate** — report appears with full incident context.
4. Click **Download JSON** or **Print** to export.

### Flow 7 — A11oy Sentra Operations (in A11oy app)

1. Open A11oy app → **SENTRA OPS ⬡ → Sentra Operations**
2. Seven agents listed with charters, allowed action classes, and current status.
3. Toggle **Kill Switch** to halt all agents.
4. Toggle **Dry-Run Mode** — all subsequent operations simulate without executing.
5. Six jobs available (Incident Sweep, Evidence Collection Sweep, etc.) with Deploy / Dry-Run buttons.
6. **Orchestration Policy Guard** panel at bottom shows doctrine enforcement status.

---

## Seed Data Summary

| Dataset | Count |
|---------|-------|
| Registry Assets | 200+ (mix of owned, authorized, lab, unknown, external) |
| Incidents | 50+ (P1–P4, all statuses) |
| Approvals | 100+ (pending, approved, rejected, expired) |
| Audit Entries | 500+ (hash-chained) |
| Evidence Items | Seeded per headline incident |
| Policy Logs | Generated during store seed |
| Playbooks | 1 full playbook (7 steps) on headline incident |

---

## Navigation Map

| Sentra Nav | Page |
|------------|------|
| Sentra Command ⬡ → Command Center | `/command-center` |
| Sentra Command ⬡ → Asset Registry | `/asset-registry` |
| Sentra Command ⬡ → Containment Actions | `/containment-actions` |
| Sentra Command ⬡ → Evidence Vault | `/evidence-vault` |
| Sentra Command ⬡ → Approval Queue | `/approval-queue` |
| Sentra Command ⬡ → Integrations Hub | `/integrations-hub` |
| Sentra Command ⬡ → Reports Generator | `/reports-generator` |
| Sentra Command ⬡ → Policy Enforcement Log | `/policy-log` |
| Sentra Command ⬡ → Audit Trail | `/audit-trail` |
| SOC Operations → Incidents → [row] | `/incidents/:id` |
| A11oy → SENTRA OPS ⬡ → Sentra Operations | `/sentra-ops` |
