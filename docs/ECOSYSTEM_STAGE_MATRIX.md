# SZL ecosystem stage matrix

The machine-readable matrix is [`ecosystem-stage-matrix.json`](ecosystem-stage-matrix.json).

It answers one question: **what stage is every major SZL surface in right now?**

## Stage labels

| Stage | Meaning |
| --- | --- |
| `operational` | Code/tests/docs support an active demo path in GitHub. |
| `supporting-operational` | Supports the demo as library, proof, receipt, telemetry, brand, trust, or workflow infrastructure. |
| `blocked-upstream` | Requires upstream proof/CI/release correction before broad claims. |
| `proxy-ready` | Patch/artifact exists but target repo write or owner action is required. |
| `release-payload` | Included in checksummed/signed or generated payload artifacts. |
| `generated-mirror` | Hugging Face mirror generated from GitHub-backed content. |
| `staged` | Prepared but not public/verified/live enough for active claims. |
| `excluded-until-funded` | Visible scaffold, intentionally outside active-demo scope. |

## Generate and verify

```bash
pnpm hf:ecosystem:write
pnpm hf:ecosystem:audit
pnpm theorem:runtime:audit
pnpm ecosystem:stage:write
pnpm ecosystem:stage
```

## Current hard boundaries

- GitHub is canonical.
- Hugging Face is discovery/diligence, generated from GitHub where possible.
- Counsel, Terra, and Carlota Jo are excluded until funded.
- UDS catalog-grade claims require signed release assets and UDS package
  integration evidence.
- Lean proof claims must distinguish runtime-verified code from proof closure.

