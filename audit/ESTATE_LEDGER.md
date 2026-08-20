<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Operation Verified Throughput estate ledger

Generated at `2026-07-26T08:52:31+00:00` by `scripts/operation_verified_throughput_inventory.py`.

| Surface | Label | Evidence |
|---|---|---|
| GitHub organization and canonical repository | MEASURED | `audit/github-estate.json` |
| Rulesets and `main` protection | MEASURED | `audit/repository-rulesets.json`; read-only capture |
| Workflow action references | MEASURED | `audit/workflow-action-pins.json` |
| Workflow identity declarations | MEASURED | `audit/identity-and-oidc-estate.json` |
| Secret metadata | MEASURED | `audit/secrets-inventory-redacted.json`; values absent |
| Tracked Lean mirror | MEASURED | `audit/lean-baseline.json`; clean build recorded separately |
| Serving hardware parity | BLOCKED | No authorized identical-GPU staging node is connected |
| Production collectors | BLOCKED | No production collector access is connected |
| Cloud, registry, and cluster estate | BLOCKED | No production cloud credentials are connected |
| Deployment identity endpoints | MEASURED | `audit/deployment-identities.json`; failures remain failures |
| Production mutation | RETIRED | This inventory performs no production mutation |

Gate 1 is **BLOCKED** until the cloud/cluster estate is inventoried, a production backup is
restored, and every P0 discrepancy is closed or accepted through the approval manifest.
