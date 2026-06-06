# FLP impossibility & CAP — honest liveness/safety caveat (WU-1)

The `MeshQuorum` attestor (`src/mesh/quorum.py`) decides "mesh healthy" from organ
heartbeats using a Byzantine **n ≥ 3f + 1** rule with a **2f + 1** agreement
quorum. This document states honestly what that decision can and cannot guarantee.

## FLP impossibility

Fischer, Lynch, and Paterson (1985) proved that in an asynchronous system with even
a single crash fault, **no deterministic consensus protocol can guarantee both
safety and liveness**. We do not claim to evade this. `MeshQuorum` is a *health
attestor*, not a consensus protocol: it reports whether a Byzantine quorum is
observed live, and it **refuses to assert health it cannot observe**.

## CAP — we choose CP

Under a network partition the mesh cannot be simultaneously Consistent, Available,
and Partition-tolerant (Brewer; Gilbert & Lynch). **We choose CP:** when
`partition_guard` detects two membership views that disagree, `healthy()` returns
`healthy=False, partition=True` with reason `"partition detected — refusing
consensus"`. We sacrifice **availability** (we will say "unhealthy / unknown")
rather than sacrifice **safety** (we will never claim a consensus that a split mesh
cannot actually deliver).

## What is REAL vs. declared boundary

- **REAL:** the quorum math (`n ≥ 3f+1`, `live ≥ 2f+1`), the partition guard, and
  the DSSE receipt over each decision (reuses `pinn_dsse` PAE; UNSIGNED marker when
  the cosign key is absent — no signature is ever fabricated).
- **Declared boundary:** live cluster heartbeat polling is **out of scope**.
  Heartbeats and membership views are injected by the caller; tests inject lists.
  This module opens no cluster connection.

> Λ is **Conjecture 1 — never a theorem**. The published Byzantine result is cited
> from `lutar-lean` PR #178 (`Lutar.Round10.ByzantineQuorum`), where §1–§3 are
> proved theorems and the optimality lower bound is an honest tagged `sorry`.

---

*See `ADR_UDS_MESH_HOME.md` (ADR-0001). Doctrine v11 — 749/14/163 — c7c0ba17.*

Signed-off-by: Yachay <yachay@szlholdings.ai>
Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
