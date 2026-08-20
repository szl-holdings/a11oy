# Sentra — Defensive Doctrine

**Version:** 1.0 · **Classification:** Internal Platform Doctrine · **Effective:** 2026-05-05

---

## Core Principle

Sentra operates exclusively within a **defensive containment** posture.
Every action the platform can initiate is constrained to assets the tenant **owns, has contracted scope over, or has explicitly authorized** in the Asset Registry.

Sentra will **never** initiate offensive, exploitation, or attacker-infrastructure targeting actions.

---

## EXECUTABLE_STATUSES

Actions may only execute against assets with one of these `ownership_status` values:

| Status | Meaning |
|--------|---------|
| `owned` | Tenant-owned infrastructure, fully in scope |
| `authorized` | Third-party asset with documented authorization |
| `contracted_scope` | Covered under a contracted penetration-testing or red-team scope |
| `lab` | Isolated lab/sandbox environment explicitly flagged for testing |

All other statuses (`blocked`, `unknown`, `external`, `attacker`, `unverified`) are **non-executable**. Any action attempted against a non-executable asset is blocked by the Safety Gate and logged as a policy denial.

---

## ALLOWED_ACTION_CLASSES

```
detect · enrich · alert · contain_owned_asset · isolate_owned_asset
revoke_owned_access · rotate_owned_secret · patch_owned_asset
block_inbound_owned_fw · quarantine_owned_endpoint · preserve_evidence
export_evidence · notify · escalate · update_case · generate_report
```

---

## DENIED_ACTION_CLASSES (Documentation-Only)

The following action classes are recorded for documentation and threat-modeling purposes only. They **cannot be executed** through Sentra:

```
attack_external · exploit_attacker_infra · offensive_recon
lateral_move_external · persistence_install · exfiltrate_data
```

Any attempt to invoke these classes returns `SENTRA_DENIAL_MESSAGE` and is persisted to the Policy Enforcement Log and Audit Trail.

---

## Safety Gate Behavior

The `runPolicyGate()` function in `src/lib/policy-engine.ts` enforces:

1. **Action class allowlist** — If the action class is not in `ALLOWED_ACTION_CLASSES`, deny immediately.
2. **Asset ownership check** — If the target asset's `ownership_status` is not in `EXECUTABLE_STATUSES`, deny with full context.
3. **Approval gate** — High-impact actions require a pending `approved` entry in the Approval Queue before execution.
4. **Audit append** — Every gate evaluation (allow or deny) is appended to the immutable Audit Trail with a hash-chain entry.

**Denial message (exact):**

> Action blocked by Sentra Policy Enforcement: target is not registered as an owned or authorized tenant asset, or the action is outside defensive scope.

---

## Doctrine Citations

All decisions reference the following frameworks:

| Framework | Scope |
|-----------|-------|
| NIST SP 800-61r2 | Computer Security Incident Handling |
| NIST CSF 2.0 | Identify → Protect → Detect → Respond → Recover |
| CISA CIRCIA §3(a) | Defensive containment obligations |
| MITRE D3FEND D3-DA | Detect & Analyze |
| MITRE D3FEND D3-NI | Network Isolation |
| MITRE D3FEND D3-ER | Evidence Retention |
| NIST SP 800-86 | Evidence collection, chain of custody |

---

## A11oy Orchestration Boundary

A11oy agents operating through the Sentra Operations surface are bound to the same doctrine. The A11oy Policy Guard in `SentraOps.tsx` enforces:

- **Kill Switch** — Immediately halts all running A11oy→Sentra agent operations.
- **Dry-Run Mode** — Simulates all actions without executing them; all results are logged as `dry_run: true`.
- **Charter enforcement** — Each agent has a declared `charter` that limits its `allowed_action_classes` to a subset of the Sentra allowlist.

No A11oy agent may exceed the permissions of the Sentra policy gate.
