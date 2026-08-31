# @szl-holdings/rae1

**RAE-1 (Receipt-Attested Evaluation) Protocol — TypeScript Reference Implementation**

Version: 1.0.0 | Protocol: rae1.0 | Node.js ≥ 20 | TypeScript 5.4+

---

## What Is RAE-1?

RAE-1 is SZL Holdings' cryptographically verifiable AI benchmark attestation protocol. It is the only protocol that combines:

1. **DSSE-signed receipts** (per RAE_1_PROTOCOL.md §2) — every benchmark problem evaluation produces a signed JSON envelope
2. **SHA-256 hash chaining** (§4) — receipts are linked so any tampering is detectable
3. **Lean 4 theorem reference** (§2.2) — each receipt cites a machine-verifiable PAC-Bayes bound on what the score *means*

An outside reviewer can verify any SZL evaluation run with just this package and the public `receipts.jsonl` — in under 5 minutes.

## Lean Theorem Reference

Every receipt in a RAE-1 chain cites:

```json
{
  "lean_theorem_name": "SZL.AGI.PACBayes.capability_improvement_rate_bound",
  "lean_theorem_file": "Lutar/PACBayes/CapabilityImprovementRate.lean",
  "lean_commit_sha": "c4d1379568...",
  "lean_repo": "szl-holdings/lutar-lean",
  "lean_build_status": "sorry_disclosed",
  "lean_sorry_count": 2
}
```

The theorem bounds the maximum plausible capability improvement per evaluation period:

```
score_next - score_prior ≤ sqrt((KL + ln(2√m/δ)) / (2m))
```

For m=12 (competition-math benchmark), KL=ln(3), δ=0.05: bound ≈ **48.9% per period**.

The 2 sorries are explicitly named (`AsymptoticTightness`, `KLMonotonicity`) with discharge routes documented in the Lean file header. This is Doctrine v6 compliant — no undisclosed sorries.

## Installation

```bash
pnpm add @szl-holdings/rae1
# or
npm install @szl-holdings/rae1
```

## Quick Start

```typescript
import { validateReceiptChain, validateRAE1Schema } from "@szl-holdings/rae1";
import { readFileSync } from "fs";

// Verify a complete benchmark receipt chain
const content = readFileSync("runtime/bench-2025/receipts.jsonl", "utf8");
const result = validateReceiptChain(content);

console.log("Valid:", result.valid);           // true if chain intact
console.log("Score:", result.score_01);        // e.g., 0.0833 (1/12)
console.log("Head:", result.chain_head);       // 64-char hex SHA-256
console.log("N solved:", result.n_solved);     // e.g., 1
console.log("Errors:", result.errors);         // [] if valid
```

```typescript
// Validate a single DSSE envelope
import { validateRAE1Schema } from "@szl-holdings/rae1";

const envelope = JSON.parse(receiptLine);
const validation = validateRAE1Schema(envelope);
if (!validation.valid) {
  console.error("Invalid receipt:", validation.errors);
}
```

```typescript
// Verify HMAC signature on a receipt
import { verifyHMAC } from "@szl-holdings/rae1/hmac";

const key = Buffer.from(process.env.RAE1_HMAC_KEY!, "base64url");
const valid = verifyHMAC(envelope, key);
```

## API Reference

### `schema` — Types

```typescript
import type { DSSEEnvelope, RAE1Payload, RAE1JudgeRecord } from "@szl-holdings/rae1/schema";
```

| Export | Description |
|--------|-------------|
| `RAE1Payload` | Inner JSON payload type (base64url-decoded) |
| `DSSEEnvelope` | Outer DSSE wrapper with payloadType + payload + signatures |
| `RAE1JudgeRecord` | Single judge evaluation record |
| `ChainSummary` | latest.json format for published run summaries |
| `RAE1_SCHEMA_VERSION` | `"rae1.0"` |
| `RAE1_PAYLOAD_TYPE` | `"application/vnd.szl.rae1+json"` |
| `CHAIN_GENESIS` | `"GENESIS"` |

### `validate` — Schema Validation

```typescript
import { validateRAE1Schema, encodePayload, decodePayload } from "@szl-holdings/rae1/validate";
```

| Function | Description |
|----------|-------------|
| `validateRAE1Schema(envelope)` | Full RAE-1 v1.0 schema + semantic validation |
| `encodePayload(payload)` | Encode RAE1Payload to base64url JSON |
| `decodePayload(encoded)` | Decode base64url back to RAE1Payload |

**Validation enforces (Doctrine v6):**
- `lean_build_status !== "sorry_undisclosed"` — violation is an error
- `judges.length >= 3` — RAE-1 §3.1
- `is_solved` consistent with `ensemble_verdict`
- All required fields present with correct types

### `chain` — Chain Integrity

```typescript
import { validateReceiptChain, computeChainHead, computeLineHash } from "@szl-holdings/rae1/chain";
```

| Function | Description |
|----------|-------------|
| `validateReceiptChain(jsonlContent)` | Full SHA-256 chain validation over JSONL |
| `computeChainHead(jsonlContent)` | Compute chain head only (faster) |
| `computeLineHash(line)` | SHA-256 of one receipt line (for prev_hash field) |
| `verifyReceiptLinkage(line, prevHash, index)` | Spot-check a single receipt |
| `serializeEnvelope(envelope)` | Compact JSON for JSONL (no whitespace) |

### `hmac` — HMAC Verification

```typescript
import { pae, verifyHMAC, signEnvelope } from "@szl-holdings/rae1/hmac";
```

| Function | Description |
|----------|-------------|
| `pae(items)` | DSSE Pre-Authentication Encoding |
| `verifyHMAC(envelope, key)` | Verify HMAC-SHA-256 signature |
| `signEnvelope(envelope, key, keyid)` | Add HMAC-SHA-256 signature to envelope |

## Doctrine v6 Compliance

- **No `sorry_undisclosed`**: `validateRAE1Schema` rejects any receipt with undisclosed sorries
- **Real code**: No stub implementations — all functions have real behavior
- **Lean ref in every gate JSDoc**: All exported functions cite the Lean theorem + commit SHA
- **Signed commits**: All commits must include `Signed-off-by:` (DCO)

## References

- [RAE_1_PROTOCOL.md](../../audit_2026-05-29_evening/agi_synthesis/RAE_1_PROTOCOL.md) — full protocol specification
- [CURSOR_AGI_PR_QUEUE.md](../../audit_2026-05-29_evening/agi_synthesis/CURSOR_AGI_PR_QUEUE.md) — PR queue
- [Lutar/PACBayes/CapabilityImprovementRate.lean](../../../lutar-lean/Lutar/PACBayes/CapabilityImprovementRate.lean) — Lean theorem
- DSSE spec: [github.com/secure-systems-lab/dsse](https://github.com/secure-systems-lab/dsse)
- competition-math benchmark suite: [arXiv:2407.11214](https://arxiv.org/abs/2407.11214)
- PAC-Bayes: [arXiv:2407.20122](https://arxiv.org/abs/2407.20122), [arXiv:2510.25569](https://arxiv.org/abs/2510.25569)

---

*RAE-1 v1.0 · SZL Holdings · Doctrine v6 · Generated 2026-05-29*
