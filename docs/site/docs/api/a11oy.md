# a11oy API (package surface)

[a11oy](/flagships/a11oy) is consumed as **TypeScript packages**, not a public HTTP API — its
governance surface is reached exclusively through the
[`szl-holdings/platform`](https://github.com/szl-holdings/platform) layer. This page documents
the package interface.

## Packages

| Package | npm | Key exports |
|---------|-----|-------------|
| `@szl-holdings/a11oy-policy` | published | `CovenantPolicy`, `ApprovalGate`, `PolicyDecision` |
| `@szl-holdings/a11oy-measurement` | published | `SignalScore`, `PRISMFrame`, `DriftReport` |
| `packages/knowledge` | workspace | `KnowledgeGraph`, `OntologyQuery`, `DomainNode` |
| `packages/qec-integrity` | workspace | `QECLineage`, `IntegrityProof`, `CSSVector` |

## `CovenantPolicy.evaluate`

```ts
import { CovenantPolicy, type PolicyDecision } from '@szl-holdings/a11oy-policy'

const policy = new CovenantPolicy()
const decision: PolicyDecision = policy.evaluate({
  action: 'deploy-model',
  axes: {
    moralGrounding: 0.97,        // sacred, floor 0.95
    measurabilityHonesty: 0.96,  // sacred, floor 0.95
    empiricalGrounding: 0.93,    // structural, floor 0.90
    // ...remaining structural + introspection axes
  },
})

// decision.passed       → boolean (conjunctive AND over all 13 axes)
// decision.failedAxes   → string[] of axes below floor
// decision.continuumHash → receipt hash
```

The Λ-invariant constrains evaluation: no recommendation below the configured confidence
threshold reaches the approval gate without escalation. See the
[a11oy flagship page](/flagships/a11oy) for the 7-layer pipeline.

> No public HTTP API is exposed by design — all calls go through the platform governance layer.
> An OpenAPI surface, if one is published in future, will be rendered on the
> [API Reference index](/api/).
