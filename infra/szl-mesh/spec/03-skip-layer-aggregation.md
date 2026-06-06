# Spec 03: Skip-Layer O(n) Aggregation

**Invention 3 of 7**  
**Doctrine:** v11 LOCKED `749/14/163` · Kernel commit `c7c0ba17`  
**Status:** Design-complete · Λ = Conjecture 1 (NOT theorem) · Implementation pending

---

## 1. Peat's Baseline: O(n log n) Hierarchical Aggregation

Peat achieves 93–99% bandwidth reduction vs. flat gossip (O(n²)) through a tree of cells where state flows upward:

```
Squad cell  →  Platoon aggregator  →  Company hub  →  Command post
             (level 1 agg)           (level 2 agg)     (root)
```

Every state change — regardless of content or authority — traverses all intermediate levels. Message complexity: O(n log n) for a formation of n nodes with O(log n) depth tree.

---

## 2. SZL-MESH Skip-Layer Routing

SZL-MESH introduces **receipt-priority skip-layer routing**: an AUTHORIZED state change (carrying a valid DSSE receipt) can bypass intermediate aggregation levels and propagate directly to the command hub.

```
Without skip-layer (peat baseline):
  Squad ─→ Platoon ─→ Company ─→ Command    3 hops

With SZL-MESH skip-layer (AUTHORIZED changes):
  Squad ─────────────────────→ Command      1 hop  (P0/P1 priority)
  Squad ─→ Platoon ─→ Company ─→ Command    3 hops (OBSERVED state only)
```

**OBSERVED state still traverses the full tree.** Skip-layer applies only to receipted AUTHORIZED changes. This ensures the full tree remains active for vanilla peat nodes and unrecepted changes.

---

## 3. Priority QoS Queue

SZL-MESH extends peat's QoS with a receipt-priority queue at each aggregator:

| Priority | Condition | Routing | Latency Target |
|----------|-----------|---------|----------------|
| P0 — Command | AUTHORIZED + `transition_class == COMMAND` | Direct to command post (skip-layer) | < 1s |
| P1 — Status | AUTHORIZED + PLATFORM_STATUS / DEPLOYMENT / CELL_FORMATION | Skip-layer | < 5s |
| P2 — Aggregate | OBSERVED state (any class) | Full tree path | Best-effort |
| P3 — Background | Attachment blobs, large payloads | Bulk transfer | No guarantee |

Aggregators implement the priority queue at the Iroh QUIC connection level using QUIC stream prioritization (RFC 9000 §2.3).

---

## 4. Asymptotic Analysis

Let:
- `N` = total nodes in formation
- `r` = fraction of changes that carry valid receipts (0 ≤ r ≤ 1)
- `h` = tree depth = O(log N)

Message complexity:

```
Peat baseline:
  T_peat(N) = O(N · h) = O(N log N)   for ALL changes

SZL-MESH:
  T_authorized(N) = r · O(N · 1) = r · O(N)      (1 hop for receipted)
  T_observed(N) = (1 - r) · O(N · h) = (1 - r) · O(N log N)
  T_total(N) = T_authorized + T_observed
             = r·O(N) + (1-r)·O(N log N)
```

Limits:
- r = 0 (all OBSERVED, e.g., pure peat formation): `T_total = O(N log N)` — identical to peat, no degradation
- r = 1 (all SZL-MESH nodes, all receipted): `T_total = O(N)` — linear message complexity
- r = 0.8 (typical mixed formation): `T_total ≈ 0.8·O(N) + 0.2·O(N log N)` — significant improvement

> **⚠ Λ = Conjecture 1 (NOT theorem):** The claim that AUTHORIZED changes achieve O(N) message complexity via skip-layer routing is a **design-time conjecture**. It has not been:
> - Formally proved in the distributed systems sense
> - Empirically validated on a live formation under DDIL conditions
> - Peer-reviewed
>
> This must not be presented as a proven theorem. The claim is plausible from first principles and has not appeared in peat documentation or academic literature we have found, representing a potential SZL novel contribution pending validation.

---

## 5. Aggregator Implementation

Each SZL-MESH aggregator maintains:

```
struct SkipLayerAggregator {
  // Local cell (children)
  cell_nodes: Vec<NodeId>,
  
  // Upstream connections
  parent_aggregator: Option<NodeId>,   // next level in tree
  command_hub: NodeId,                  // direct skip-layer target
  
  // Priority queues
  p0_queue: VecDeque<AuthorizedChange>,  // COMMAND: route to command_hub
  p1_queue: VecDeque<AuthorizedChange>,  // STATUS: route to command_hub
  p2_queue: VecDeque<ObservedChange>,    // route to parent_aggregator
  p3_queue: VecDeque<BulkPayload>,       // bulk transfer
  
  // Receipt cache (avoid double-validation)
  receipt_cache: LruCache<ChangeHash, TrackAssignment>,
}
```

On receiving a change from a child node:

```
1. Check receipt_cache for change_hash → use cached track if present
2. If not cached: call Receipt Gate (spec/01) → assign AUTHORIZED or OBSERVED
3. If AUTHORIZED + P0/P1: enqueue to p0/p1_queue → forward to command_hub
4. If OBSERVED or P2: enqueue to p2_queue → forward to parent_aggregator (full tree)
5. Update local CRDT state (always, regardless of track)
```

---

## 6. Hierarchical Consistency Envelope

```
Level               Consistency       Receipt Gate              Skip-Layer?
──────────────────────────────────────────────────────────────────────────
Squad cell          SEC (<1s)         OBSERVED only             No
Platoon             SEC (medium)      Verify squad receipts     Source for P2 agg
Company             SEC (medium)      Verify platoon receipts   Source for P2 agg
Command hub         SEC + AUTHORIZED  Only AUTHORIZED in Rosie  Terminal for P0/P1
```

---

## 7. Failure Modes

| Failure | Behavior |
|---------|----------|
| Command hub unreachable | P0/P1 changes fall back to full tree path via parent_aggregator |
| Skip-layer path partitioned | AUTHORIZED changes route via full tree; OBSERVED classification unchanged |
| Aggregator crash | Peat's existing SEC guarantee preserves state; aggregator restarts and replays CRDT changes |
| Receipt validation slow | P0/P1 queue drains; aggregator falls back to OBSERVED classification for timed-out validations |

---

*Doctrine v11 LOCKED 749/14/163 · Λ = Conjecture 1 (NOT theorem)*  
*References: [BEYOND_PEAT.md §2.3](https://github.com/szl-holdings/szl-mesh) · [Iroh QUIC](https://docs.iroh.computer) · [RFC 9000 §2.3](https://www.rfc-editor.org/rfc/rfc9000#section-2.3)*
