<!--
Copyright 2026 SZL Holdings
SPDX-License-Identifier: Apache-2.0
-->

# Mesh Acceptance Criteria — v0.4.0

How we know the [mesh interconnect](./MESH_INTERCONNECT_DESIGN.md) actually works. Five demonstrable criteria. Each is a single command (or short sequence) an engineer with cluster access runs after the [runbook](./MESH_DEPLOYMENT_RUNBOOK.md) completes. "Pass" is an objective, observable result — not a claim.

All five depend on FA-001 (the five module images existing and running). Criterion #5 additionally depends on the PhD SecOps signed-image PR landing. None of these are executed in this design PR; they are the v0.4.0 definition-of-done.

---

## AC-1 — mTLS allowed path: a11oy → amaru succeeds with a client cert

**Command**

```bash
kubectl exec -n szl-a11oy deploy/a11oy -c a11oy -- \
  curl -s -o /dev/null -w '%{http_code}\n' \
  http://amaru.szl-amaru.svc.cluster.local:8080/healthz
```

**Pass:** HTTP `200`, and the request is carried over mTLS. Evidence of mTLS is the `X-Forwarded-Client-Cert` (XFCC) header the receiving Istio sidecar adds to forwarded requests when the connection presented a client certificate — observable in amaru's access log or by echoing request headers at `/healthz`. The `a11oy → amaru` pair is ALLOW in the matrix, and `PeerAuthentication: STRICT` ([Istio PeerAuthentication](https://istio.io/latest/docs/reference/config/security/peer_authentication/)) requires the connection to be an mTLS tunnel, so a 200 here proves both the allow rule and mTLS.

> XFCC is the Envoy/Istio header populated only when a downstream client cert was presented; its presence on the server side is the standard signal that the hop was mTLS rather than plaintext. Cross-check with `istioctl x describe pod -n szl-amaru <amaru-pod>`, which reports the effective mTLS mode for the workload.

---

## AC-2 — mTLS denied path: amaru → vessels is rejected by AuthorizationPolicy

**Command**

```bash
kubectl exec -n szl-amaru deploy/amaru -c amaru -- \
  curl -s -o /dev/null -w '%{http_code}\n' \
  http://vessels.szl-vessels.svc.cluster.local:8080/healthz
```

**Pass:** HTTP `403` returned by the **vessels sidecar** (not by the app), with body `RBAC: access denied`. The `amaru → vessels` pair is DENY in the matrix (memory has no need to reach the skeleton). Because `allow-mesh-to-vessels` ([`mesh/authpolicies/allow-mesh-to-vessels.yaml`](../../mesh/authpolicies/allow-mesh-to-vessels.yaml)) only lists the `a11oy` and `sentra` principals, amaru's request is not matched by any ALLOW rule and is therefore denied by Istio's implicit-deny behavior ([Istio AuthorizationPolicy](https://istio.io/latest/docs/reference/config/security/authorization-policy/), [Istio security best practices](https://istio.io/latest/docs/ops/best-practices/security/)). A 403 here is the single clearest proof that the mesh enforces authorization rather than merely declaring it.

---

## AC-3 — Receipt POST reaches the chain authority with a verifiable Ed25519 signature

**Command (illustrative; exact path depends on module API)**

```bash
# Trigger a receipt-producing action (e.g., a11oy gate decision), then read it back:
kubectl exec -n szl-a11oy deploy/a11oy -c a11oy -- \
  curl -s http://szl-receipts.szl-receipts.svc.cluster.local:8080/receipts/latest \
  | tee /tmp/receipt.json

# Verify the Ed25519 signature against the published public key:
python3 - <<'PY'
import json, base64
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
r = json.load(open("/tmp/receipt.json"))
pub = Ed25519PublicKey.from_public_bytes(base64.b64decode(r["pubkey_b64"]))
pub.verify(base64.b64decode(r["sig_b64"]), r["payload_canonical"].encode())
print("Ed25519 signature VERIFIED")
PY
```

**Pass:** the receipt produced by any module is retrievable from `szl-receipts-server` and its **Ed25519** signature verifies against the published public key (signature verification raises on failure, so a clean exit is the pass). This closes PhD Systems Scope 3, which found the current receipt is HMAC-SHA-256 with a symmetric demo key checked into `values.yaml` — forgeable by any key-holder. Ed25519 is asymmetric: only the signer can produce a valid signature, and any party can verify it offline without the secret, which is also what makes it air-gap-safe.

> Dependency: the HMAC→Ed25519 migration in `szl-receipts-server` must land. This is the same hardening the PhD Systems "make one thing real" recommendation calls for.

---

## AC-4 — All six namespaces show injected sidecars

**Command**

```bash
istioctl proxy-status
```

**Pass:** `istioctl proxy-status` lists a proxy (one row per pod) for a workload in **all six** namespaces — `szl-rosie`, `szl-a11oy`, `szl-amaru`, `szl-sentra`, `szl-vessels`, `szl-receipts` — each with `SYNCED` status across CDS/LDS/EDS/RDS. This proves the `istio-injection=enabled` label ([Istio sidecar injection](https://istio.io/latest/docs/setup/additional-setup/sidecar-injection/)) took effect and pods were restarted so the `istio-proxy` sidecar was injected. A namespace missing from the list means its pods predate the label and still need a `kubectl rollout restart`.

Cross-check:

```bash
for ns in szl-rosie szl-a11oy szl-amaru szl-sentra szl-vessels szl-receipts; do
  echo -n "$ns: "; kubectl get ns "$ns" -o jsonpath='{.metadata.labels.istio-injection}{"\n"}'
done   # expect "enabled" for all six
```

---

## AC-5 — An unsigned image is denied at admission (depends on PhD SecOps PR)

**Command**

```bash
kubectl apply -n szl-a11oy -f - <<'YAML'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: unsigned-canary
spec:
  replicas: 1
  selector: { matchLabels: { app: unsigned-canary } }
  template:
    metadata: { labels: { app: unsigned-canary } }
    spec:
      containers:
        - name: c
          image: docker.io/library/busybox:latest   # unsigned, no provenance
YAML
```

**Pass:** the `kubectl apply` is **rejected at admission** (the webhook returns a denial; the Deployment is not created), via the Pepr Validate path that enforces image signature/provenance. Today the Pepr `szl-receipts` controller is `.Mutate`-only and `FAIL_OPEN=true` (audit-only, PhD Systems Scope 3) — it does **not** block. This criterion therefore depends on the PhD SecOps PR that adds a `.Validate` capability enforcing signed images. Until that lands, AC-5 is expected to **not** pass, and that gap is tracked explicitly rather than hidden.

> When the SecOps Validate path is present, a signed image (e.g. a cosign-signed `ghcr.io/szl-holdings/a11oy@sha256:...`) must conversely be **admitted**, proving the gate allows good images and denies bad ones.

---

## Summary

| AC | Proves | Hard dependency |
|---|---|---|
| AC-1 | mTLS allow path works (a11oy→amaru, XFCC present) | FA-001 images |
| AC-2 | Authorization deny works (amaru→vessels → 403) | FA-001 images |
| AC-3 | Receipt chain is real + Ed25519-verifiable | FA-001 images + HMAC→Ed25519 migration |
| AC-4 | Sidecars injected in all 6 namespaces | FA-001 images |
| AC-5 | Unsigned image denied at admission | PhD SecOps Validate PR |

AC-1, AC-2, and AC-4 are pure mesh criteria and pass as soon as FA-001 images run and the runbook completes. AC-3 and AC-5 carry one additional dependency each, called out above so reviewers see exactly what is and is not gated by this design.

---

## References

- Istio PeerAuthentication: https://istio.io/latest/docs/reference/config/security/peer_authentication/
- Istio AuthorizationPolicy: https://istio.io/latest/docs/reference/config/security/authorization-policy/
- Istio security best practices: https://istio.io/latest/docs/ops/best-practices/security/
- Istio sidecar injection: https://istio.io/latest/docs/setup/additional-setup/sidecar-injection/
- UDS Package CR (v1alpha1): https://uds.defenseunicorns.com/reference/configuration/custom-resources/packages-v1alpha1-cr/
