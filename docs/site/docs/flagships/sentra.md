# Policy — Drift Detector

> **Naming note.** This component was previously tracked under the internal codename *sentra*
> (a coinage on the English *sentry* — never a Quechua word). The honest, user-facing name is
> **Policy** (the posture / drift-detection surface); the codename is retired and kept here only
> as historical context.

## Overview

The **Policy** drift detector is the **anomaly-detection and observability substrate** of the
SZL governed platform. It models enterprise cyber posture as a **Kitaev surface** — security
state is a topological surface, and drift is the deviation from the ground-state configuration.

> **Frontier capability.** A Kitaev-surface posture-drift detector on a Λ-axis-governed
> observability fiber — `Lutar/QEC/KitaevSurface` formal lattice basis
> ([Ouroboros Thesis DOI 10.5281/zenodo.20434276](https://doi.org/10.5281/zenodo.20434276)).

**Anatomy mapping:** the Policy drift detector is the operational face of the
[Hukulla](/anatomy/#hukulla) immune system and the [OTel-VSP](/anatomy/#otel-vsp)
nervous/observability fiber.

```mermaid
flowchart TD
    subgraph Ingest
        T1[Sensor adapters: CVE · SIEM · endpoint]
        T2[Audit fiber tap: proof-chain events]
    end
    subgraph Detect
        D1[Kitaev surface model: stability score]
        D2[Baseline comparator: posture delta]
        D3[Threat classifier: CVSS-weighted]
    end
    subgraph Respond
        R1[Incident queue by severity]
        R2[Covenant policy gate]
        R3[Audited + proof-sealed remediation]
    end
    Ingest --> Detect --> Respond
    T2 -->|lineage| D1
```

## How it works

1. **Continuous posture scoring** — a real-time topological stability score across the surface.
2. **Drift events** — any delta beyond the policy threshold raises a classified event.
3. **Incident queue** — events ranked by CVSS-weighted severity.
4. **Policy gate** — every remediation passes the [a11oy](/flagships/a11oy) Covenant gate.
5. **Proof chain** — every response is sealed in the SZL audit fiber with full attribution.

The Kitaev-surface stability model gives an objective stability scalar rather than a
hand-tuned alert threshold — drift is measured against a topological ground state.

## Example — score posture drift

```ts
import { driftScore } from '@szl/policy-drift'

const report = driftScore({ baseline: surfaceA, observed: surfaceB })

console.log(report.stability) // topological stability score
report.events
  .sort((a, b) => b.cvss - a.cvss)
  .forEach(e => console.log(e.id, e.cvss, e.requiresApproval))
```

## Source & evidence

- **Model:** Kitaev-surface basis in ouroboros-thesis, `Lutar/QEC/KitaevSurface`
- **DOI:** [10.5281/zenodo.20434276](https://doi.org/10.5281/zenodo.20434276)
- **License:** Proprietary
