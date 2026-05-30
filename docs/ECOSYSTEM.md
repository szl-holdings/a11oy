# SZL Holdings operational ecosystem

A11oy is the GitHub-side operational hub for the public SZL Holdings substrate.
The full build is not a single repository: the product runtime lives in
`platform`, theorem/proof truth lives in `ouroboros-thesis` and `lutar-lean`,
receipt infrastructure lives across `ouroboros`, `rosie`, `amaru`, `sentra`,
`uds-mesh`, and `vsp-otel`, and vertical repos track product surfaces and
governance charters.

The machine-readable registry is [`ecosystem-registry.json`](ecosystem-registry.json).
The investor-demo readiness report is
[`ecosystem-readiness-report.json`](ecosystem-readiness-report.json). Validate
both with:

```bash
pnpm ecosystem:audit
pnpm ecosystem:readiness
```

The operating-system layer is
[`ECOSYSTEM_OPERATING_SYSTEM.md`](ECOSYSTEM_OPERATING_SYSTEM.md), with the
machine-readable anatomy/formula map in
[`anatomy-formula-runtime-map.json`](anatomy-formula-runtime-map.json). Validate
the full OS contract with:

```bash
pnpm ecosystem:os:audit
```

If sibling repos are cloned under `.repos/szl-holdings/`, the audit also reports
local checkout coverage. Use:

```bash
bash scripts/clone-org-repos.sh
pnpm ecosystem:audit -- --require-local
```

## Readiness tiers

| Tier | Meaning |
| --- | --- |
| `hub` | A11oy operational hub and payload publisher. |
| `runtime-composition` | Composing monorepo / deployed runtime surface. |
| `runtime-substrate` | Runtime library or loop substrate. |
| `formal-proof` | Lean/proof substrate. |
| `formal-thesis` | DOI-pinned research thesis and claim language. |
| `receipt-substrate` | Receipt, provenance, minting, or drift component. |
| `mesh-contract` | UDS mesh pointer and span contract. |
| `observability` | Telemetry / OpenTelemetry export surface. |
| `vertical-product` | Product or vertical-market repo. |
| `trust` | Public trust and replay artifacts. |
| `brand` | Brand, anatomy, and preview assets. |
| `org-governance` | Reusable org workflows and governance templates. |

## Current operational read

| Repo | Tier | Readiness | Operational note |
| --- | --- | --- | --- |
| `a11oy` | hub | operationalizing | Doctrine CI, Python payload bundle, deploy manifest, and Hugging Face publish path now live on this branch. |
| `platform` | runtime-composition | production-monorepo | Canonical deployed product monorepo; A11oy hub should publish contracts, not duplicate the platform runtime. |
| `ouroboros` | runtime-substrate | production-substrate | Runtime spine for governed loops and receipts. |
| `lutar-lean` | formal-proof | formal-substrate | Proof source of record; public claims should map to exact files and current proof status before marketing/docs repeat all-green language. |
| `ouroboros-thesis` | formal-thesis | canonical-thesis | v18 DOI is the current citation anchor for Series-A materials; GitHub release reconciliation remains an upstream action. |
| `rosie` | receipt-substrate | uds-component | CSS ingress receipt orchestration. |
| `amaru` | receipt-substrate | uds-component | Receipt minting / Cardano anchor layer. |
| `sentra` | receipt-substrate | uds-component | Drift and remediation layer. |
| `uds-mesh` | mesh-contract | pointer-manifest | Binds UDS component releases and span schemas. |
| `vsp-otel` | observability | source-package | Lambda-axis span exporter and Hugging Face dataset bridge. |
| `szl-cookbook` | operator-docs | recipes | Operator recipes and payload patterns. |
| `agi-forecast` | forecast | source-package | Scenario/forecast gauges for governance trajectory. |
| `vessels` | vertical-product | demo | Real demo surface; identity should be reconciled across maritime, fleet-command, and MCP-handshake language. |
| `counsel` | vertical-product | scaffold | Governance scaffold; product implementation is pending or in platform. |
| `terra` | vertical-product | scaffold | Governance scaffold; product implementation is pending or in platform. |
| `carlota-jo` | vertical-product | scaffold | Governance scaffold for advisory operations. |
| `szl-trust` | trust | artifact-ledger | Real run artifacts; public portal/replay automation remain next operational layer. |
| `szl-brand` | brand | production-assets | Canonical anatomy, mockups, previews, and visual doctrine. |
| `.github` | org-governance | production-workflows | Reusable workflow and template source of truth. |

## Active-demo naming policy

The active showcase centers the real GitHub repositories and does not use the
retired/stale product-name framing `KORA`, `LUMINA`, `PARAGON`, or active
`Lyte` copy. `counsel`, `terra`, and `carlota-jo` remain visible for
transparency but are excluded from active-demo claims until funded.

## Operational order before Hugging Face push

1. GitHub branch is green: DCO, docs, CodeQL, SBOM, secret scan, Doctrine Build.
2. `pnpm payload:bundle` emits and verifies the operational tarball.
3. The bundle includes the ecosystem registry, provenance docs, deploy manifest,
   built doctrine outputs, and Hugging Face payload.
4. `HF_TOKEN` is supplied as a GitHub secret, not committed or pasted into
   repository files.
5. The manual `Publish Hugging Face Payload` workflow publishes the generated
   payload to `SZLHOLDINGS/a11oy-v19-substrate`.
