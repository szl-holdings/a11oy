# API Contract — sentra v1.0
**Doctrine v11 LOCKED 749/14/163 | SLSA L1 honest | Version: 1.0.0**  
**Updated:** 2026-06-03

This document is the canonical API contract for the `sentra` flagship.
It is versioned with the code release (see `CHANGELOG.md` for history).

## Base URL

```
https://szlholdings-sentra.hf.space
```

## Authentication

No API key required for public endpoints. All responses include doctrine invariants.

## Doctrine Invariants in All Responses

Every JSON response from `sentra` includes:

```json
{
  "doctrine": "v11",
  "declarations": 749,
  "axioms_unique": 14,
  "sorries_total": 163
}
```

These values are LOCKED. Any deviation is a bug.

## Core Endpoints

### GET `/api/sentra/v1/lambda`

Returns the 13-axis Lambda (Λ) trust aggregation score.

**Response:**
```json
{
  "trust_axes": 13,
  "axes": [{"name": "soundness", "score": 0.92}, ...],
  "lambda": 0.91911,
  "lambda_floor": 0.90,
  "pass": true,
  "aggregate": "geometric mean (yuyay_v3 canonical, 13-axis)",
  "uniqueness": "Conjecture 1 — NOT a Theorem",
  "declarations": 749,
  "axioms_unique": 14,
  "sorries_total": 163,
  "doctrine": "v11"
}
```

**Note:** Lambda (Λ) is Conjecture 1, NOT a closed theorem. This is an honest disclosure.

### GET `/api/sentra/v1/honest`

Returns honest doctrine disclosure for compliance auditors.

**Response:**
```json
{
  "doctrine": "v11",
  "declarations": 749,
  "axioms_unique": 14,
  "sorries_total": 163,
  "lambda_uniqueness": "Conjecture 1 — NOT a closed theorem",
  "slsa": "L1 (honest)",
  "kernel_commit": "c7c0ba17",
  "section_889_vendors": ["Huawei", "ZTE", "Hytera", "Hikvision", "Dahua"]
}
```

### GET `/api/sentra/v4/fleet` (a11oy only) / `/api/sentra/v1/brain` (amaru, rosie)

Flagship-specific endpoints (see per-flagship docs below).

## Response Headers

| Header | Description |
|--------|-------------|
| `x-szl-space` | Flagship identifier |
| `x-szl-wire-d` | Wire D DSSE provenance |
| `traceparent` | W3C TraceContext format |

## Error Responses

| Status | Meaning |
|--------|---------|
| 200 | OK |
| 404 | Route not found (never returns 405) |
| 503 | Space starting (cold start, retry in 30s) |

## SLSA Level

**SLSA L1 (honest disclosure).** L2+ requires Sigstore + isolated builders (roadmap for Series-A).

## Section 889 Compliance

This flagship does NOT use prohibited components from:
Huawei, ZTE, Hytera, Hikvision, or Dahua.

**Signed-off-by: Yachay <yachay@szlholdings.ai>**  
**Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>**
