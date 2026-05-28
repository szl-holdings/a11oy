# a11oy

> Vertical alignment substrate — policy, measurement, knowledge, and QEC-integrity packages for governed AI execution

[![CI](https://github.com/szl-holdings/a11oy/actions/workflows/ci.yml/badge.svg)](https://github.com/szl-holdings/a11oy/actions/workflows/ci.yml)
[![CodeQL](https://github.com/szl-holdings/a11oy/actions/workflows/codeql.yml/badge.svg)](https://github.com/szl-holdings/a11oy/actions/workflows/codeql.yml)
[![OpenSSF Scorecard](https://api.securityscorecards.dev/projects/github.com/szl-holdings/a11oy/badge)](https://securityscorecards.dev/viewer/?uri=github.com/szl-holdings/a11oy)
[![License](https://img.shields.io/badge/license-BSL--1.1-28251D?style=flat-square)](./LICENSE)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.x-3178C6?style=flat-square&logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Node.js](https://img.shields.io/badge/Node.js-24+-339933?style=flat-square&logo=node.js&logoColor=white)](https://nodejs.org/)
[![MCP Compatible](https://img.shields.io/badge/MCP-compatible-805AD5?style=flat-square)](https://github.com/modelcontextprotocol/typescript-sdk)
[![DOI](https://img.shields.io/badge/DOI-10.5281%2Fzenodo.20434276-805AD5?style=flat-square&logo=doi&logoColor=white)](https://doi.org/10.5281/zenodo.20434276)
[![Series-A Engineering](https://img.shields.io/badge/Series--A-Engineering-28251D?style=flat-square)](https://szlholdings.com)
[![Doctrine v6](https://img.shields.io/badge/Doctrine-v6-01696F?style=flat-square)](https://github.com/szl-holdings/platform/blob/main/docs/doctrine/szl-doctrine.md)

`a11oy` (Alloy) is the governed agentic execution fabric of SZL Holdings — the seven-layer substrate that connects live enterprise signals to human-confirmed decisions with cryptographic proof at every transition. It provides TypeScript packages for policy enforcement, signal measurement, knowledge-graph traversal, and QEC-integrity verification across all SZL domain verticals.

> [!NOTE]
> This repository ships the core fabric packages consumed by [`szl-holdings/platform`](https://github.com/szl-holdings/platform). The deployment surface for Alloy is the platform monorepo; this repo contains the standalone alignment substrate packages.

---

## Architecture

```mermaid
flowchart TD
    subgraph packages["a11oy Packages"]
        POL[packages/policy\nCovenant Policy Engine\nApproval gate enforcement]
        MEA[packages/measurement\nSignal scoring + PRISM\nBaseline drift detection]
        KNO[packages/knowledge\nKnowledge-graph traversal\nDomain ontology queries]
        QEC[packages/qec-integrity\nQuantum-error-correction\nlineage verification]
    end
    subgraph platform["szl-holdings/platform"]
        ALLOY[Alloy Execution Fabric\n7-layer governed pipeline]
    end
    packages --> ALLOY
    POL -->|"approval gate\n(layer 6)"| ALLOY
    MEA -->|"signal correlation\n(layers 2–3)"| ALLOY
    KNO -->|"explanation context\n(layer 4)"| ALLOY
    QEC -->|"proof-chain integrity\n(layer 7)"| ALLOY
```

---

## Packages

| Package | Purpose | Key Types |
|---------|---------|-----------|
| `packages/policy` | Covenant Policy Engine — evaluates all actions against governance rules before execution | `CovenantPolicy`, `ApprovalGate`, `PolicyDecision` |
| `packages/measurement` | Signal scoring, PRISM correlation, baseline drift detection | `SignalScore`, `PRISMFrame`, `DriftReport` |
| `packages/knowledge` | Knowledge-graph traversal and domain ontology queries | `KnowledgeGraph`, `OntologyQuery`, `DomainNode` |
| `packages/qec-integrity` | Quantum-error-correction lineage verification (CSS-QEC backed by `lutar-lean`) | `QECLineage`, `IntegrityProof`, `CSSVector` |

---

## Quick Start

```bash
# Install via npm
npm install @szl-holdings/a11oy-policy
npm install @szl-holdings/a11oy-measurement

# Or with pnpm
pnpm add @szl-holdings/a11oy-policy

# Development (clone + workspace)
git clone https://github.com/szl-holdings/a11oy.git
cd a11oy
pnpm install
pnpm run build
pnpm run test
```

---

## How It Works

Every action in the SZL platform must pass through the policy engine before execution:

1. **Signal ingress** — `measurement` scores incoming events against PRISM baselines
2. **Knowledge context** — `knowledge` retrieves relevant domain ontology for explanation
3. **Policy evaluation** — `policy` checks the action against Covenant Policy rules
4. **Approval gate** — if policy requires human approval, `policy` creates an `ApprovalGate`
5. **Execution unlock** — only after gate resolution does the action proceed
6. **QEC verification** — `qec-integrity` verifies proof-chain cryptographic lineage

The Λ-invariant (lambda axis) constrains the policy evaluation: no recommendation with confidence below the configured threshold proceeds to the approval gate without escalation.

---

## Security and Governance

- OpenSSF Scorecard: **7.0** (as of 2026-05-28) — see [scorecard report](https://securityscorecards.dev/viewer/?uri=github.com/szl-holdings/a11oy)
- CodeQL security scanning on every push to main
- All packages are consumed exclusively via the platform governance layer; no direct external API surface
- QEC-integrity lineage is formally verified in [`szl-holdings/lutar-lean`](https://github.com/szl-holdings/lutar-lean)

---

## How to Cite

```bibtex
@software{szl_holdings_a11oy_2026,
  title  = {a11oy — Governed Agentic Execution Fabric},
  author = {{SZL Holdings}},
  year   = {2026},
  doi    = {10.5281/zenodo.20434276},
  url    = {https://github.com/szl-holdings/a11oy}
}
```

[![DOI](https://img.shields.io/badge/DOI-10.5281%2Fzenodo.20434276-805AD5?style=flat-square&logo=doi&logoColor=white)](https://doi.org/10.5281/zenodo.20434276)
[![ORCID](https://img.shields.io/badge/ORCID-0009--0001--0110--4173-A6CE39?style=flat-square&logo=orcid&logoColor=white)](https://orcid.org/0009-0001-0110-4173)

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the engineering workflow. All contributions require CI green on all required checks and one reviewer approval. Doctrine v6 tone required in PR descriptions.

Related: [`szl-holdings/platform`](https://github.com/szl-holdings/platform) · [`szl-holdings/sentra`](https://github.com/szl-holdings/sentra) · [`szl-holdings/rosie`](https://github.com/szl-holdings/rosie) · [`szl-holdings/lutar-lean`](https://github.com/szl-holdings/lutar-lean)

---

## License

BSL-1.1 — See [LICENSE](./LICENSE) for terms. Copyright (c) 2024-2026 SZL Holdings.
