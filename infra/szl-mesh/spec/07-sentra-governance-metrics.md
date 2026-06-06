# Spec 07: Sentra Governance Metrics (First-Class Telemetry Channel)

**Invention 7 of 7**  
**Doctrine:** v11 LOCKED `749/14/163` · Kernel commit `c7c0ba17`  
**Status:** Design-complete · Implementation pending

---

## 1. Motivation

Peat exposes `GetSyncStats` for basic sync monitoring and emits CDC events to Kafka/NATS for downstream consumers. Neither peat nor any other mesh protocol (Consul, Istio, Linkerd) exposes **governance-layer integrity metrics** — i.e., metrics about whether state transitions are authorized, whether Byzantine activity is detected, and whether doctrine compliance is being maintained.

SZL-MESH treats governance integrity as a **first-class telemetry channel**: a dedicated set of Prometheus-compatible metrics fed into sentra's immune filter, enabling anomaly detection on governance health — not just network health.

---

## 2. Metric Definitions

### 2.1 Receipt Rate: `szl_mesh_authorized_fraction`

```
Name:    szl_mesh_authorized_fraction
Type:    Gauge (computed per scrape interval)
Labels:  formation_id, cell_id, transition_class
Formula: count(AUTHORIZED changes in window T) / count(total changes in window T)
Window:  60 seconds (configurable)
```

**Sentra anomaly rule:** If `szl_mesh_authorized_fraction < 0.7` for any `cell_id` for more than 2 consecutive windows → **Governance Anomaly Alert**.

Interpretation:
- `1.0` — all changes receipted; full-authority mesh
- `0.5–1.0` — mixed formation with peat-native nodes or intermittent partitions
- `< 0.3` — severe: possible Byzantine flooding of OBSERVED track, or mass doctrine mismatch

---

### 2.2 Byzantine Corroboration Failures: `szl_mesh_byzantine_corroboration_failures_total`

```
Name:    szl_mesh_byzantine_corroboration_failures_total
Type:    Counter
Labels:  node_id, formation_id, transition_class
Increments: when a node's change fails k-of-n corroboration quorum within window T
```

**Sentra anomaly rule:** If `rate(szl_mesh_byzantine_corroboration_failures_total[60s]) > 5` for any `node_id` → **Byzantine Candidate Alert** for that node.

Action: Human review triggered; may initiate revocation ceremony (spec/06).

---

### 2.3 Revocation Propagation Lag: `szl_mesh_revocation_propagation_lag_seconds`

```
Name:    szl_mesh_revocation_propagation_lag_seconds
Type:    Histogram (buckets: 0.1, 0.5, 1, 5, 30, 60, 300, 3600)
Labels:  formation_id, revoked_node_id
Measures: time from revocation_at timestamp to node receiving CRDT entry
```

**Sentra anomaly rule:** If `histogram_quantile(0.99, szl_mesh_revocation_propagation_lag_seconds) > 300` (5 minutes) → **Partition Severity Alert**.

Interpretation: High lag indicates severe mesh partitioning; revoked nodes may be operating unchecked in isolated cells.

---

### 2.4 Doctrine Version Mismatches: `szl_mesh_doctrine_version_mismatch_count`

```
Name:    szl_mesh_doctrine_version_mismatch_count
Type:    Counter
Labels:  formation_id, claimed_doctrine_version, claimed_kernel_commit
Increments: when an enrollment request claims wrong doctrine_version or kernel_commit
```

**Sentra anomaly rule:** Any non-zero value → **Doctrine Mismatch Alert**.

Interpretation:
- Stale nodes attempting enrollment after doctrine update
- Rogue nodes attempting enrollment with fabricated doctrine claims
- Misconfigured deployment

---

### 2.5 Split-Brain Recovery: `szl_mesh_split_brain_recovery_seconds`

```
Name:    szl_mesh_split_brain_recovery_seconds
Type:    Histogram
Labels:  formation_id, cell_id
Measures: time from partition heal to full CRDT convergence (all nodes at same head)
```

---

### 2.6 Pre-Partition Change Count: `szl_mesh_pre_partition_change_count`

```
Name:    szl_mesh_pre_partition_change_count
Type:    Counter
Labels:  formation_id, cell_id
Increments: once per partition event with the count of changes written during partition
```

High values indicate significant divergence that requires human review of the AUTHORIZED/OBSERVED reconciliation.

---

### 2.7 Sentra Event Schema

Every SZL-MESH state transition emits a structured event to sentra's perception loop:

```json
{
  "event_type": "szl_mesh_state_transition",
  "formation_id": "<formation-uuid>",
  "cell_id": "<cell-uuid>",
  "node_id": "<sha256-of-pubkey>",
  "crdt_document_id": "<automerge-doc-id>",
  "change_hash": "<sha256-hex>",
  "receipt_status": "AUTHORIZED | OBSERVED | MISSING",
  "corroboration_status": "PENDING | CORROBORATED | FAILED | N/A",
  "track": "AUTHORIZED | OBSERVED | REVOKED",
  "transition_class": "PLATFORM_STATUS | DEPLOYMENT | PACKAGE | COMMAND | CELL_FORMATION",
  "doctrine_version": "749/14/163",
  "kernel_commit": "c7c0ba17",
  "latency_ms": 234,
  "node_count_in_cell": 12,
  "timestamp_utc": "2026-06-02T22:00:00Z"
}
```

Events are emitted over a dedicated gRPC stream (`SentraEventStream` RPC — see `proto/szl_mesh.proto §SzlMeshSentra`).

---

## 3. Sentra Immune Filter Integration

Sentra's immune filter applies anomaly detection rules on the governance metrics stream. The filter is modeled on the biological immune system: healthy baseline → deviation detection → alert → human review → possible response (revocation, formation reset).

```
SZL-MESH node
    │
    ├─ Prometheus scrape endpoint :9090/metrics
    │   → szl_mesh_* metrics (pull)
    │
    └─ gRPC SentraEventStream
        → Per-transition structured events (push)
        → Sentra immune filter: anomaly detection
        → Alert → rosie Fleet Cockpit notification
```

Sentra's existing perception loop at `https://szlholdings-sentra.hf.space` consumes these events. The immune filter configuration is managed in the sentra flagship — SZL-MESH is the producer only.

---

## 4. No Other Mesh Protocol Has This

Cross-protocol comparison:

| Protocol | Sync metrics | Network metrics | Governance integrity metrics |
|----------|-------------|-----------------|------------------------------|
| Peat (GetSyncStats) | ✓ | Partial | ✗ |
| Consul | ✓ | ✓ | ✗ |
| Istio | ✓ | ✓ | ✗ |
| Linkerd | ✓ | ✓ | ✗ |
| **SZL-MESH** | ✓ | ✓ | **✓ (first-class)** |

The SZL-MESH governance metrics channel — receipt rate, doctrine violations, Byzantine quotas, revocation lag — is novel in the mesh protocol space.

---

## 5. Prometheus Scrape Configuration

```yaml
# prometheus.yml scrape config for szl-mesh-node sidecar
scrape_configs:
  - job_name: szl_mesh
    static_configs:
      - targets: ['localhost:9090']
    metric_relabel_configs:
      - source_labels: [__name__]
        regex: 'szl_mesh_.*'
        action: keep
```

---

*Doctrine v11 LOCKED 749/14/163 · Λ = Conjecture 1 (NOT theorem)*  
*References: [SZL_MESH_DESIGN_v1.md §6.2](https://github.com/szl-holdings/szl-mesh) · [sentra flagship](https://szlholdings-sentra.hf.space) · [Prometheus data model](https://prometheus.io/docs/concepts/data_model/)*
