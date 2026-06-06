<!--
Copyright 2026 SZL Holdings
SPDX-License-Identifier: Apache-2.0
-->

# `mesh/` — v0.4.0 interconnect resources

Declarative resources that implement the [mesh interconnect design](../docs/architecture/MESH_INTERCONNECT_DESIGN.md). Apply order is in the [runbook](../docs/architecture/MESH_DEPLOYMENT_RUNBOOK.md).

| Path | What it is |
|---|---|
| `namespaces.yaml` | Six namespaces labeled `istio-injection=enabled` + PSS-restricted. |
| `peerauth/peerauthentication-strict.yaml` | Per-namespace `PeerAuthentication: STRICT` (mTLS-only). |
| `authpolicies/allow-mesh-to-<module>.yaml` | One `AuthorizationPolicy` per callee encoding the 6×6 matrix (ALLOW + implicit deny). |
| `MATRIX.txt` | Generated human-readable matrix + per-pair rationale. |
| `_matrix_gen.py` | Design artifact: derives the matrix from the founder hierarchy rules. No cluster, no network I/O. |
| `_authpolicy_gen.py` | Design artifact: regenerates `authpolicies/` from the matrix. No cluster, no network I/O. |

Regenerate the policies deterministically:

```bash
cd mesh && python3 _authpolicy_gen.py && python3 _matrix_gen.py > MATRIX.txt
```

The five module UDS Package CRs live alongside in [`../packages/<module>/uds-package.yaml`](../packages/).
