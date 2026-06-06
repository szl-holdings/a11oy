# Spec 04: CRDT-Native Byzantine Corroboration

**Invention 4 of 7**  
**Doctrine:** v11 LOCKED `749/14/163` · Kernel commit `c7c0ba17`  
**Status:** Design-complete · Implementation pending

---

## 1. The Byzantine Problem in CRDT Systems

Peat assumes **fail-stop nodes**: a node is either online and honest, or offline. A Byzantine peer — a node that holds a valid formation key and Ed25519 certificate but has been adversarially controlled — can inject arbitrary CRDT changes signed with its valid key. Peat has no defense against this.

SZL-MESH adds **Byzantine corroboration** layered on top of the CRDT — not as a consensus protocol (which would sacrifice AP availability), but as a **soft voting annotation** that runs alongside the AP CRDT without blocking writes.

---

## 2. Design Philosophy: Soft Safety, Not BFT Consensus

Classical BFT consensus (PBFT, Tendermint, HotStuff) achieves Byzantine safety but **blocks during partition** — sacrificing availability for safety. SZL-MESH takes a different trade-off:

| Property | PBFT/Tendermint | SZL-MESH Corroboration |
|----------|-----------------|------------------------|
| Byzantine safety | Strong (f < n/3) | Soft (f < k, for configured k) |
| Availability | Blocks during partition | AP — never blocks |
| Write latency | Consensus round-trip | Immediate (local) |
| Corroboration latency | N/A | Eventual (async, within window T) |
| Works under DDIL | No | Yes |

SZL-MESH achieves **Byzantine soft-safety** — correct classification of state for the common case — while preserving full AP availability. This is a different point in the BFT trade-off space.

---

## 3. Corroboration Protocol

### 3.1 Overview

```
1. Any node N_i writes state S_v for document D, key K  (immediate, AP)
2. Corroboration Collector observes changes from all nodes in the cell
3. When k independent nodes {N_1, N_2, ..., N_k} have all written S_v 
   for the same (D, K) within time window T:
   → Change is annotated CORROBORATED in the CRDT
4. A single Byzantine node N_byz alone cannot achieve CORROBORATED 
   for false state S_false if k > 1
```

### 3.2 Corroboration Policy

Corroboration policies are per-`transition_class`:

```yaml
# Default corroboration policies
corroboration_policies:
  - transition_class: COMMAND
    k: 2
    n: all_in_cell          # quorum drawn from all enrolled cell nodes
    window_seconds: 30
    
  - transition_class: PLATFORM_STATUS
    k: 2
    n: all_in_cell
    window_seconds: 30
    
  - transition_class: DEPLOYMENT
    k: 1                    # single-node quorum (solo deployment scenarios)
    n: all_in_cell
    window_seconds: 60
    
  - transition_class: PACKAGE
    k: 1
    n: all_in_cell
    window_seconds: 120
    
  - transition_class: CELL_FORMATION
    k: 2
    n: all_in_cell
    window_seconds: 10
```

Policies are replicated as CRDT metadata and versioned with the doctrine version.

### 3.3 CRDT Annotation for Corroboration

Corroboration state is stored in a separate CRDT document (never mutating application state):

```json
{
  "corroboration": {
    "<change_hash>": {
      "status": "PENDING | CORROBORATED | FAILED",
      "corroborating_nodes": ["<node_id_1>", "<node_id_2>"],
      "policy_k": 2,
      "window_expires_at": "<ISO-8601>",
      "corroborated_at": "<ISO-8601> | null"
    }
  }
}
```

The corroboration document is a CRDT map; concurrent writes from multiple corroboration collectors converge deterministically.

---

## 4. Formal Properties

### 4.1 Corroboration Safety

**Theorem (informal):** Let `f` be the number of Byzantine nodes in a cell of `n` nodes. For a corroboration policy with threshold `k`, if `k > f`, then Byzantine nodes cannot achieve `CORROBORATED` for any false state value `S_false` for which no honest node has independently observed `S_false`.

**Proof sketch:** For `S_false` to become `CORROBORATED`, `k` distinct nodes must report `S_false`. If `k > f`, at least one of the `k` reporters must be honest. An honest node reports only what it has observed. If no honest node has observed `S_false`, no honest node reports it, so the quorum of `k` cannot be achieved by Byzantine nodes alone.

This is weaker than PBFT safety (which holds against up to `f < n/3` Byzantine nodes for all values, under all conditions) but does not sacrifice availability.

### 4.2 Corroboration Liveness

**Property:** If `k` honest nodes independently observe the same value `S_v` for `(D, K)` within window `T`, and all `k` nodes are connected to the corroboration collector within `T`, then `S_v` achieves `CORROBORATED` within `T + propagation_delay`.

**Note:** If the cell is partitioned and fewer than `k` honest nodes are reachable, corroboration stalls at `PENDING`. This is the availability trade-off — CRDT writes still succeed; corroboration is best-effort.

---

## 5. Byzantine Detection via Sentra

The sentra integration (spec/07) exposes corroboration metrics:

```
szl_mesh_byzantine_corroboration_failures{node_id}
  → A node that repeatedly reports values that fail corroboration
  → Anomaly threshold: >5 failures in 60s → Byzantine candidate alert

szl_mesh_corroboration_quorum_time_seconds{transition_class}
  → Time to achieve k-of-n quorum
  → High values: cell fragmentation or Byzantine interference
```

A Byzantine candidate alert triggers human review and may initiate certificate revocation (see spec/06).

---

## 6. Interaction with Receipt Gate

Corroboration and receipt validation are **independent** checks:

| Receipt Status | Corroboration Status | Combined Classification |
|----------------|---------------------|------------------------|
| AUTHORIZED | CORROBORATED | Highest confidence — command-ready |
| AUTHORIZED | PENDING | High confidence (single-receipt) — usable for command |
| OBSERVED | CORROBORATED | Medium confidence — multiple nodes agree, no doctrine proof |
| OBSERVED | PENDING | Low confidence — situational awareness only |
| AUTHORIZED | FAILED | Alert — node signed receipt but peers don't corroborate the value |

The AUTHORIZED + FAILED combination is particularly significant: it may indicate a Byzantine node that obtained a Formation CA certificate and is issuing receipts for false state.

---

## 7. Write Quota Enforcement (Layer B2)

To prevent Byzantine state flooding, SZL-MESH enforces per-node write quotas at the aggregator level:

```
max_changes_per_node_per_minute: 600       (10/second average)
max_document_size_per_node_bytes: 10485760  (10 MB)
max_peers_per_node: 50
```

Quotas are replicated as CRDT metadata. Excess changes from any node are quarantined pending human review and logged as a Sentra alert event.

---

*Doctrine v11 LOCKED 749/14/163 · Λ = Conjecture 1 (NOT theorem)*  
*References: [BYZANTINE_HANDLING.md](https://github.com/szl-holdings/szl-mesh) · [Castro & Liskov 1999 PBFT](https://dl.acm.org/doi/10.1145/296806.296824) · [Shapiro et al. 2011 SEC](https://inria.hal.science/inria-00555588v1/document)*
