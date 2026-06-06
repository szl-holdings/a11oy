# Spec 06: CRDT-Native Revocation Without OCSP

**Invention 6 of 7**  
**Doctrine:** v11 LOCKED `749/14/163` · Kernel commit `c7c0ba17`  
**Status:** Design-complete · Implementation pending

---

## 1. Motivation

Peat relies on certificate TTL (90-day expiry) for de-facto revocation. In air-gapped DDIL environments, OCSP is operationally infeasible: there is no guaranteed path to an OCSP responder, and OCSP stapling requires periodic online access. When a node is compromised mid-mission, TTL-based revocation means the compromised node remains trusted for up to 90 days.

SZL-MESH replaces OCSP with a **CRDT-replicated revocation list** that propagates through the mesh using the same AP CRDT substrate already present in every node.

---

## 2. Revocation CRDT Document

```
crdt_document_id: "szl-mesh/revoked-certs/formation-<formation_id>"
crdt_type: Automerge grow-only set (LWW map keyed by cert_fingerprint)
```

Document schema:

```json
{
  "revoked": {
    "<cert_fingerprint_sha256>": {
      "node_id": "<sha256-of-ed25519-pubkey>",
      "cert_fingerprint": "<sha256-hex-of-DER-cert>",
      "revoked_at": "<ISO-8601>",
      "reason": "BYZANTINE | COMPROMISED | DOCTRINE_MISMATCH | ADMINISTRATIVE | SECTION_889",
      "revoked_by": "<node_id-of-issuing-formation-ca-operator>",
      "revocation_receipt": "<base64url-DSSE-envelope-authorizing-revocation>"
    }
  }
}
```

The `revoked` map is a grow-only CRDT: entries are **never removed**. This guarantees monotonicity — a revocation that propagates to a node cannot be un-done by a concurrent CRDT merge.

---

## 3. Revocation Issuance Protocol

Revocation is issued by the Formation CA operator (a node holding Supervisor role):

```
1. Operator identifies node N_byz to revoke (manual decision or sentra alert)
2. Operator constructs RevocationEntry for N_byz's certificate
3. Operator signs RevocationEntry with their DSSE receipt (doctrine_version=749/14/163)
4. RevocationEntry is written to "szl-mesh/revoked-certs/formation-<id>" CRDT
5. CRDT sync propagates the entry across the mesh:
     - Connected nodes: sub-second propagation
     - Partitioned nodes: propagation occurs when any path reconnects
6. All nodes receiving the entry immediately reject further messages from N_byz
7. Past CRDT changes from N_byz are NOT deleted — they are downgraded to REVOKED status
   (for forensic audit purposes)
```

---

## 4. Revocation Check at Message Receipt

Every SZL-MESH node performs a revocation check before accepting any peer message:

```
function accept_message(msg, sender_node_id, sender_cert_fingerprint):
  revocation_doc = crdt_store.get("szl-mesh/revoked-certs/formation-<id>")
  if sender_cert_fingerprint in revocation_doc["revoked"]:
    log_event(REVOKED_NODE_MESSAGE_REJECTED, sender_node_id)
    return REJECT
  return PROCESS
```

The check uses the **local CRDT replica** — no network call required. This preserves AP availability: revocation checks never block on partition.

---

## 5. Properties

| Property | Value |
|----------|-------|
| **AP available** | Revocations propagate via CRDT; checks use local replica — never blocks on network |
| **Eventually consistent** | Revocation reaches partitioned cell when any path reconnects (SEC guarantee) |
| **Monotonic** | Grow-only set: revocations are never un-done by CRDT merge |
| **Air-gap compatible** | No external OCSP server, no CRL distribution point — fully self-contained |
| **Audit trail** | Every revocation carries a DSSE receipt (doctrine-pinned) and persists in CRDT history |
| **Convergence** | All nodes with the same revocation set reject the same nodes (deterministic) |

---

## 6. Revocation Propagation Timing

Propagation timing depends on mesh connectivity:

| Scenario | Propagation Latency |
|----------|---------------------|
| Within a connected cell | < 1 second (Iroh QUIC direct sync) |
| Across platoon boundary | 1–5 seconds (aggregator relay) |
| Partitioned cell, reconnected | Immediately upon reconnection (CRDT sync) |
| BLE-only path | 1–30 seconds (BLE throughput limited) |
| Full formation isolation | Delayed until any mesh path reconnects |

The **residual risk** is that a revoked node continues to operate until its local cell receives the revocation CRDT update. This is mitigated by the Byzantine corroboration layer (spec/04) which limits what a Byzantine node can achieve even without revocation.

---

## 7. Interaction with Two-Track State (spec/02)

When a revocation entry is received, the SZL-MESH node:

1. Marks all future messages from the revoked node as OBSERVED
2. Retroactively downgrades **past AUTHORIZED changes** from the revoked node to `REVOKED` sub-status in the `_szl_track` annotation CRDT
3. Does NOT delete past CRDT changes (forensic preservation)
4. Emits a Sentra alert event for each downgraded change

The Rosie cockpit displays REVOKED-status changes in a distinct amber/red indicator, flagging them for human audit.

---

## 8. Sentra Monitoring

```
szl_mesh_revocation_propagation_lag_seconds{formation_id}
  → Time between revocation_at timestamp and last node receiving the CRDT entry
  → High lag = partition severity indicator or sync failure

szl_mesh_revoked_node_message_rejections_total{node_id, revoked_node_id}
  → Count of messages rejected from revoked node after revocation
  → Non-zero = revoked node is still transmitting (persistent threat)

szl_mesh_revocation_count{formation_id}
  → Total revocations in the formation
  → Baseline: 0; any non-zero = security event
```

---

## 9. Comparison with OCSP and CRL

| Mechanism | OCSP | CRL | SZL-MESH CRDT Revocation |
|-----------|------|-----|--------------------------|
| Requires network to check | Yes (OCSP responder) | No (cached CRL) | No (local CRDT replica) |
| Air-gap compatible | No | Partial (if CRL pre-staged) | Yes |
| Real-time propagation | Yes (online check) | No (CRL update frequency) | Eventually consistent (sub-second in connected cell) |
| Revocation issuance | Online, requires CA access | Offline, signed CRL | Online, CRDT write |
| Monotonicity | Varies | Yes (CRL only grows) | Yes (grow-only CRDT set) |
| Audit trail | OCSP log | CRL history | CRDT history (immutable) |

---

*Doctrine v11 LOCKED 749/14/163 · Λ = Conjecture 1 (NOT theorem)*  
*References: [BYZANTINE_HANDLING.md §3.2 Layer B4](https://github.com/szl-holdings/szl-mesh) · [RFC 6960 OCSP](https://www.rfc-editor.org/rfc/rfc6960) · [Automerge grow-only set](https://automerge.org/docs/)*
