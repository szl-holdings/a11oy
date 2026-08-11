# ORO operational workstream status

**State:** `IN_PROGRESS`  
**Coordination branch:** `work/oro-operational-workstream-v1`  
**Coordination PR:** pending creation  
**Production claim:** `NOT_VERIFIED`

## Current verified estate boundary

| Lane | State | Evidence boundary |
|---|---|---|
| Central governed secret-name audit | MERGED | `.github` PR #349 merged as `99b1c61eaca6018dd9e840f708dcbb5bb0a4dbad`; no secret values were read or recorded. |
| Expired Doctrine PAT lane | RETIRED | `szl-doctrine` PR #15 merged as `ddd23ca2824d162bf6300b3e2e7e7a1537bc84fb`. |
| Historical fixed-SHA SDA controller | RETIRED_ON_MAIN | Historical workflow, controller, and manifest are absent on `.github/main`; the retirement tombstone is present. PR #348 itself closed without merge and is not cited as the delivery vehicle. |
| Platform Vessels/control repair | MERGED | Platform PR #510 merged as `9ad61506d3938f8b65bdb6e88a74b434dcb6998d`. |
| A11oy operational evidence repair | MERGED | A11oy PR #1093 merged as `bd6560526bde20fccf556d6255f274a176beacc1`. |
| Cookbook compiler repair | MERGED | Cookbook PR #83 merged as `1be98cc0fed44fba98bfb89a1056c6f3364ae736`. |

## ORO delivery phases

| Phase | State | Completion evidence required |
|---|---|---|
| 0. Protect truth | IN_PROGRESS | Pin current A11oy, formula, kernel, and Lean source revisions; inventory protected paths and existing signer/persistence contracts. |
| 1. Runtime control plane | NOT_STARTED | Permanent A11oy PR with rank, Codex, barrier, storage, APIs, dashboard, Docker wiring, adversarial tests, real HTTP smoke, and signed narrow demonstration. |
| 2. Formal witnesses | NOT_STARTED | Permanent lutar-lean PR with protected `lake build` and exact `--no-sorries` evidence. |
| 3. Proof binding | BLOCKED | Data-only A11oy PR after the Lean PR merges. |
| 4. Runtime activation | BLOCKED | Protected A11oy merge, durable store, governed signer, exact live source readback, and restart-persistence evidence. |
| 5. Estate reconciliation | BLOCKED | Current-main organization health, GitHub license, Hugging Face license, and public-link controls all green. |
| 6. Coordination retirement | BLOCKED | Close this draft coordination PR without merge after permanent PRs and live evidence exist. |

## Claim ledger

```text
runtime_enforced: NOT_MEASURED
well_founded_termination: MODELED
machine_checked_termination: NOT_PROVED
global_action_optimality: NOT_CLAIMED
general_causal_identification: NOT_CLAIMED
```

## Immediate execution queue

1. Audit current A11oy signer, persistence, FastAPI registration, Dockerfile copy, test, and migration conventions.
2. Open the permanent A11oy runtime branch and implement the smallest end-to-end control-plane slice.
3. Open the independent lutar-lean witness branch.
4. Run protected checks; repair source defects without weakening gates.
5. Merge through normal protected delivery.
6. Bind immutable Lean evidence into A11oy.
7. Activate runtime and perform exact live readback.
8. Run the organization control sweep.

## Update rule

Every update must record exact repository, branch, head SHA, PR, workflow run, artifact digest, test result, blocker, and next action. A local pass, draft PR, or queued workflow is never a production-complete state.
