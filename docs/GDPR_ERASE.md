# GDPR Article 17 — Right to Erasure Endpoint

**Flagship:** a11oy
**Endpoint:** `POST /api/a11oy/v2/erase`
**Doctrine v11 — 749 / 14 / 163 — replay hash c7c0ba17**
**Updated:** 2026-06-02

---

## Summary

Public flagships do not store end-user PII. All HF Spaces are unauthenticated and public.
This endpoint exists as the GDPR Article 17 minimum viable surface: it accepts an erasure
request, signs a receipt (whether or not any data exists to erase), and returns that signed
receipt to the caller.

---

## Request

```http
POST /api/a11oy/v2/erase
Content-Type: application/json

{
  "caller_id": "<string — your identifier, used only to label the receipt>",
  "confirmation": "DELETE-MY-DATA"
}
```

**Fields:**

| Field | Type | Required | Description |
|---|---|---|---|
| `caller_id` | string | yes | Caller-supplied identifier (not stored, used only in the receipt label) |
| `confirmation` | string | yes | Must be the literal string `DELETE-MY-DATA` |

---

## Response

```json
{
  "status": "acknowledged",
  "message": "Public flagships don't store user PII. Khipu chain receipts are auditable, not PII. Personal data deletion via rosie /api/rosie/v2/unay/erase (separate handler for operator session memory). Audit-trail receipt of this deletion request signed and returned.",
  "receipt": {
    "payload": {
      "type": "gdpr_erase_request",
      "flagship": "a11oy",
      "caller_id_label": "<caller_id from request>",
      "ts": "<ISO8601 timestamp>",
      "doctrine": {
        "declarations": 749,
        "axioms": 14,
        "sorries": 163,
        "replay_hash": "c7c0ba17"
      }
    },
    "signature": "<Wire D DSSE Ed25519 signature>",
    "prev_hash": "<Khipu chain prev_hash>"
  }
}
```

---

## What data is and is not held

| Data class | Held by a11oy? | Notes |
|---|---|---|
| PII from HF Space callers | **No** | HF Spaces are unauthenticated; no accounts, no cookies |
| Khipu chain receipts | Yes (audit trail) | Receipts are cryptographic audit records, not PII; deletion would break chain integrity |
| Operator session memory (rosie only) | rosie only | Route to `POST /api/rosie/v2/unay/erase` for operator session data |
| GitHub interaction data | GitHub (not us) | Contact GitHub directly for their data deletion |

---

## Implementation Reference

The endpoint handler (`serve.py`) must:

1. Validate `confirmation == "DELETE-MY-DATA"` — return 400 if not.
2. Build a receipt payload with `type: "gdpr_erase_request"`, `flagship`, `caller_id_label`, `ts`, and `doctrine` numbers.
3. Sign via `szl_dsse.sign(payload, WIRE_D_SIGNING_KEY)` — return 500 if signing fails.
4. Return 200 with `status: "acknowledged"` and the signed receipt.
5. **Do not log** `caller_id` beyond the signed receipt.
6. **Do not store** the request (the signed receipt itself is the audit trail).

```python
# Reference implementation (docs/reference; do not copy verbatim into serve.py without review)
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import szl_dsse, datetime, os

router = APIRouter()

class EraseRequest(BaseModel):
    caller_id: str
    confirmation: str

@router.post("/api/a11oy/v2/erase")
async def gdpr_erase(body: EraseRequest):
    if body.confirmation != "DELETE-MY-DATA":
        raise HTTPException(400, "confirmation must be 'DELETE-MY-DATA'")
    payload = {
        "type": "gdpr_erase_request",
        "flagship": "a11oy",
        "caller_id_label": body.caller_id,
        "ts": datetime.datetime.utcnow().isoformat() + "Z",
        "doctrine": {"declarations": 749, "axioms": 14, "sorries": 163, "replay_hash": "c7c0ba17"},
    }
    key = os.environ.get("WIRE_D_SIGNING_KEY")
    if not key:
        raise HTTPException(500, "Signing key not configured")
    receipt = szl_dsse.sign(payload, key)
    return {
        "status": "acknowledged",
        "message": (
            "Public flagships don't store user PII; Khipu chain receipts are auditable not PII. "
            "Personal data deletion via rosie /api/rosie/v2/unay/erase (separate handler). "
            "Audit-trail receipt of deletion request signed."
        ),
        "receipt": receipt,
    }
```

---

## Routing to rosie

For operator session memory (if applicable), route the request to rosie:

```http
POST https://SZLHOLDINGS-rosie.hf.space/api/rosie/v2/unay/erase
Content-Type: application/json

{
  "caller_id": "<your identifier>",
  "confirmation": "DELETE-MY-DATA"
}
```

---

*Co-Authored-By: Perplexity Computer Agent*
*Doctrine v11 — 749/14/163 — c7c0ba17*
