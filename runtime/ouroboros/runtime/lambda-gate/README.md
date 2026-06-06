# ouroboros/lambda-gate

**Operationalizes:** TH1 — Λ-Gate (9-axis conjunctive evaluator)  
**Repo:** szl-holdings/ouroboros  
**Path:** packages/lambda-gate

## What it does

Implements the primary quality gate. Every artefact must pass through the Λ-gate before it can be stored as a valid `Receipt`. The gate uses a **conjunctive AND** policy:

- All 9 axes ≥ 0.90
- Critical axes (`moralGrounding`, `measurabilityHonesty`) ≥ 0.95
- Composite Λ (arithmetic mean) ≥ 0.90

Only artefacts that clear **all three conditions simultaneously** are stored and returned to callers.

### 9 Axes

| Axis | Critical |
|------|---------|
| moralGrounding | ✓ |
| measurabilityHonesty | ✓ |
| epistemicHumility | |
| harmAvoidance | |
| logicalCoherence | |
| citationIntegrity | |
| noveltyContribution | |
| reproducibility | |
| stakeholderAlignment | |

## HTTP endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/receipts` | Submit receipt candidate; returns `{receipt, eval, stored}` |
| `GET`  | `/receipts/:hash` | Retrieve stored receipt by SHA-256 hash |
| `GET`  | `/receipts` | List all stored receipts |
| `POST` | `/verify` | Re-evaluate stored receipt `{hash}` |

## Env vars

| Var | Default | Purpose |
|-----|---------|---------|
| `PORT` | `3001` | HTTP listen port |

## Install & test

```bash
pnpm install
pnpm test
# Start server
PORT=3001 node dist/server.js
```
