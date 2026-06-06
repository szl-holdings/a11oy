# Spec 02: Two-Track AUTHORIZED / OBSERVED State Model

**Invention 2 of 7**  
**Doctrine:** v11 LOCKED `749/14/163` · Kernel commit `c7c0ba17`  
**Status:** Design-complete · Implementation pending

---

## 1. Motivation

Peat treats all CRDT state equivalently: if a node holds the formation key and a valid Ed25519 certificate, its writes are as authoritative as any other node. There is one track. This is correct for coordination but insufficient for governance.

SZL-MESH introduces **two coexisting tracks** in the same CRDT store:
- **AUTHORIZED** — state that carries a valid doctrine receipt
- **OBSERVED** — state present in the CRDT but without a valid receipt

The key design invariant: **OBSERVED state is never dropped**. It remains visible for situational awareness and forensic analysis. The tracks determine display and actionability, not storage.

---

## 2. Track Definitions

```
AUTHORIZED track
  Condition:  CRDT change carries a DSSE receipt that passes full validation
              (see spec/01-dsse-receipts.md §5)
  Properties:
    - Signed under doctrine_version == "749/14/163"
    - Signed under kernel_commit == "c7c0ba17"
    - Signer's certificate is NOT in revocation list
    - change_hash matches the actual Automerge change chunk
    - Timestamp within ±5s of local UTC
  Display (Rosie): Solid indicator — green/amber by platform health
  Actionable:  YES — usable for command decisions without further verification
  Audit trail: YES — receipt provides doctrine-pinned evidence

OBSERVED track
  Condition:  CRDT change present but ANY receipt validation step fails, OR
              no receipt envelope is attached (vanilla peat node)
  Display (Rosie): Dashed indicator — grey
  Actionable:  NO — requires additional human verification before action
  Audit trail: PARTIAL — CRDT change is auditable, doctrine authority is not
```

---

## 3. Track Assignment Algorithm

Track assignment runs at the **Doctrine Receipt Gate (L4)** after every CRDT merge:

```
for each change in merged_crdt_changeset:
  if change.has_dsse_receipt():
    track = validate_receipt(change.dsse_receipt, change.raw_bytes, now())
  else:
    track = OBSERVED

  change.set_track(track)
  emit_sentra_event(change, track)
```

Track assignment is **idempotent and deterministic**: given the same change bytes and receipt, all nodes assign the same track (modulo clock skew ≤ 5s).

---

## 4. CRDT Document Annotation

SZL-MESH annotates the Automerge document map with track metadata without altering the change content:

```json
{
  "_szl_track": {
    "<change_hash>": {
      "track": "AUTHORIZED | OBSERVED",
      "receipt_validated_at": "<ISO-8601>",
      "validation_failure_reason": null | "MISSING_RECEIPT | BAD_SIGNATURE | WRONG_DOCTRINE | WRONG_KERNEL | REVOKED | CLOCK_SKEW | HASH_MISMATCH"
    }
  }
}
```

This annotation is itself a CRDT map — it merges deterministically across nodes. The `_szl_track` prefix is reserved; application documents must not use it.

---

## 5. Backwards Compatibility with Vanilla Peat

Vanilla peat nodes participate in the mesh normally:
- Their changes propagate via Automerge sync as usual
- SZL-MESH nodes receive these changes and classify them as **OBSERVED** (no receipt attached)
- No peat node is disconnected, banned, or rejected based on receipt status
- The CRDT network never partitions on receipt status

This ensures SZL-MESH nodes and peat nodes coexist in mixed formations without protocol incompatibility.

---

## 6. Rosie Fleet Cockpit Integration

The Rosie cockpit reads state exclusively from the SZL-MESH hub node gRPC API. New RPCs added beyond peat-node's 25-RPC surface:

| RPC | Returns |
|-----|---------|
| `GetAuthorizedPlatforms` | AUTHORIZED-track platform states only |
| `GetObservedPlatforms` | OBSERVED-track states (debug/forensic) |
| `GetReceiptLedger` | Recent DSSE receipts for audit |
| `GetDoctrinePinStatus` | Current doctrine version and kernel commit |

See `proto/szl_mesh.proto` for the protobuf definitions.

---

## 7. Command Decision Policy

For `transition_class == COMMAND`:

| Scenario | Track | Action |
|----------|-------|--------|
| Single AUTHORIZED command | AUTHORIZED | Display in Rosie; human confirms then executes |
| Concurrent AUTHORIZED commands (post-partition merge) | AUTHORIZED (both) | Display both; Rosie shows conflict; human resolves; execution receipt issued |
| OBSERVED command | OBSERVED | Rosie shows for awareness; human must re-issue as AUTHORIZED before execution |
| REVOKED node's command | OBSERVED (downgraded) | Shown in audit log; never actionable |

**Invariant:** No autonomous command execution during split-brain reconciliation without human confirmation.

---

## 8. State Track Lifecycle

```
CRDT change arrives
        │
        ▼
Receipt Gate validation (spec/01)
        │
   ┌────┴────┐
   │         │
AUTHORIZED  OBSERVED ── can be upgraded only by:
   │                    1. Re-issuance: originating node re-sends
   │                       with valid receipt attached
   │                    2. Cannot be upgraded by SZL-MESH itself
   ▼
Promoted to AUTHORIZED track
(immutable once set — downgrade only via revocation)
```

AUTHORIZED state can be **downgraded** to a `REVOKED` sub-state if the signing node's certificate is later added to the CRDT revocation list (see `spec/06-crdt-revocation.md`).

---

*Doctrine v11 LOCKED 749/14/163 · Λ = Conjecture 1 (NOT theorem)*  
*References: [spec/01-dsse-receipts.md](01-dsse-receipts.md) · [spec/06-crdt-revocation.md](06-crdt-revocation.md) · [Automerge](https://automerge.org)*
