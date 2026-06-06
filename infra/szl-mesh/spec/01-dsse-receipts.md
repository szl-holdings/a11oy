# Spec 01: Doctrine-Pinned DSSE Receipts on CRDT State Transitions

**Invention 1 of 7**  
**Doctrine:** v11 LOCKED `749/14/163` · Kernel commit `c7c0ba17`  
**Status:** Design-complete · Implementation pending

---

## 1. Motivation

Peat signs each CRDT operation with the originating node's Ed25519 key. This provides integrity: every change has a provable author. What peat does NOT provide is **governance authority**: proof that a specific change was authorized under a specific locked governance doctrine.

SZL-MESH adds a DSSE (Dead Simple Signing Envelope) receipt to every Automerge change that crosses a policy boundary. The receipt is the cryptographic link between a CRDT state transition and the governance doctrine that authorized it.

---

## 2. DSSE Envelope Structure

SZL-MESH receipts follow the [DSSE specification](https://github.com/secure-systems-lab/dsse):

```json
{
  "payloadType": "application/vnd.szl.mesh.state-transition+json",
  "payload": "<base64url(StateTransitionStatement)>",
  "signatures": [
    {
      "keyid": "<Ed25519-pubkey-fingerprint>",
      "sig": "<base64url(Ed25519-sig-over-PAE(payloadType, payload))>"
    }
  ]
}
```

The PAE (Pre-Authentication Encoding) follows DSSE §3:

```
PAE(type, body) = "DSSEv1" + SP + LEN(type) + SP + type + SP + LEN(body) + SP + body
```

---

## 3. StateTransitionStatement

The `payload` field (base64url-decoded) is a JSON `StateTransitionStatement`:

```json
{
  "type": "szl-mesh/state-transition/v1",
  "doctrine_version": "749/14/163",
  "kernel_commit": "c7c0ba17",
  "crdt_document_id": "<automerge-doc-id>",
  "change_hash": "<sha256-hex-of-automerge-change-chunk>",
  "from_state_head": ["<prev-head-1>", "<prev-head-2>"],
  "to_state_head": ["<new-head>"],
  "transition_class": "PLATFORM_STATUS | DEPLOYMENT | PACKAGE | COMMAND | CELL_FORMATION",
  "node_id": "<sha256-hex-of-ed25519-pubkey>",
  "timestamp_utc": "2026-06-02T22:00:00Z",
  "policy_context": {
    "section_889_vendors": ["Huawei", "ZTE", "Hytera", "Hikvision", "Dahua"],
    "slsa_level": "L1"
  }
}
```

### Field Semantics

| Field | Type | Invariant |
|-------|------|-----------|
| `type` | string | Always `"szl-mesh/state-transition/v1"` |
| `doctrine_version` | string | Always `"749/14/163"` (LOCKED) |
| `kernel_commit` | string | Always `"c7c0ba17"` (LOCKED) |
| `crdt_document_id` | string | The Automerge document UUID this change belongs to |
| `change_hash` | string | SHA-256 of the raw Automerge change chunk bytes (hex) |
| `from_state_head` | string[] | Array of Automerge heads before this change |
| `to_state_head` | string[] | Array of Automerge heads after this change |
| `transition_class` | enum | One of the 5 transition classes |
| `node_id` | string | SHA-256 of the signer's Ed25519 public key |
| `timestamp_utc` | ISO-8601 | Must be within ±5s of receiving node's UTC clock |
| `policy_context.section_889_vendors` | string[] | Exactly the 5 Section 889 vendors (informational) |
| `policy_context.slsa_level` | string | Always `"L1"` |

---

## 4. Transition Classes

| Class | Description | Priority |
|-------|-------------|----------|
| `COMMAND` | A command issued to a fleet platform | P0 — skip-layer |
| `DEPLOYMENT` | Package deployment state change | P1 — skip-layer |
| `PLATFORM_STATUS` | Platform health/status update | P1 — skip-layer |
| `PACKAGE` | Package metadata update | P2 — full tree |
| `CELL_FORMATION` | Cell topology change (join/leave) | P1 — skip-layer |

---

## 5. Receipt Validation Algorithm

Receipt Gate validation (pseudocode):

```
function validate_receipt(dsse_envelope, automerge_change_chunk, receiving_node_time):
  1. Parse DSSE envelope; extract payloadType, payload, signatures[0]
  2. Assert payloadType == "application/vnd.szl.mesh.state-transition+json"
  3. Decode payload → stmt (StateTransitionStatement)
  4. Assert stmt.doctrine_version == "749/14/163"
  5. Assert stmt.kernel_commit == "c7c0ba17"
  6. Verify Ed25519 signature:
       sig_valid = Ed25519.Verify(
         pubkey = lookup_node_pubkey(stmt.node_id),
         message = PAE(payloadType, payload),
         signature = signatures[0].sig
       )
  7. Assert sig_valid == true
  8. Assert lookup_node_pubkey(stmt.node_id) is not in revocation_list
  9. Assert SHA-256(automerge_change_chunk) == stmt.change_hash
  10. Assert |stmt.timestamp_utc - receiving_node_time| <= 5 seconds
  
  if all assertions pass:
    return AUTHORIZED
  else:
    return OBSERVED
```

Any assertion failure downgrades the change to OBSERVED; the CRDT change is **never dropped**.

---

## 6. Receipt Storage

Receipts are stored alongside the CRDT change in the peat persistence layer. Each node maintains a local receipt ledger:

```
receipt_ledger/
  <change_hash>.dsse.json   — the DSSE envelope
  <change_hash>.change      — the raw Automerge change chunk
```

The `GetReceiptLedger` gRPC RPC (see `proto/szl_mesh.proto`) exposes recent receipts for audit.

---

## 7. Wire Encoding

When propagating CRDT changes over the mesh, SZL-MESH nodes attach the DSSE receipt as a metadata field in the peat wire protocol extension. Vanilla peat nodes see only the CRDT change (no receipt metadata); they are backwards-compatible and the change appears as OBSERVED at SZL-MESH nodes.

---

## 8. Relation to Invention 2 (Two-Track State)

Receipt validation is the gating mechanism for the AUTHORIZED track. If this spec changes, `spec/02-two-track-state.md` must be updated in tandem.

---

*Doctrine v11 LOCKED 749/14/163 · Λ = Conjecture 1 (NOT theorem)*  
*References: [DSSE spec](https://github.com/secure-systems-lab/dsse) · [peat-node proto](https://github.com/defenseunicorns/peat-node/tree/main/proto)*
