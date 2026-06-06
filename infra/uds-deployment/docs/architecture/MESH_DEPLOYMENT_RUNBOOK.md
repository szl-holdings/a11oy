<!--
Copyright 2026 SZL Holdings
SPDX-License-Identifier: Apache-2.0
-->

# Mesh Deployment Runbook — v0.4.0

The exact, ordered commands an operator runs to bring up the v0.4.0 [mesh interconnect](./MESH_INTERCONNECT_DESIGN.md) on a cluster that already runs `uds-core` slim-dev. Ordering matters: **label → restart (sidecars) → Package CRs → PeerAuthentication STRICT → AuthorizationPolicies → verify.** Applying STRICT mTLS before sidecars exist would wedge the modules, so STRICT comes after the rollout restart.

> **Prerequisite — FA-001.** This runbook assumes the five module images exist and their Deployments are healthy. Until FA-001 is resolved, steps 0–6 are the documented procedure; they are not executed by this design PR. See [`MESH_ACCEPTANCE_CRITERIA.md`](./MESH_ACCEPTANCE_CRITERIA.md) for the definition of done.

---

## Step 0 — Preconditions

```bash
# uds-core slim-dev already running (Istio + Pepr + Keycloak + Prometheus).
istioctl version            # istiod present
kubectl get ns istio-system keycloak monitoring pepr-system
uds version                 # uds-cli present (for Package CR apply via operator)
```

`core-slim-dev` provides Istio, the UDS Operator (Pepr), Keycloak + authservice, and Prometheus — the components the Package CRs and mesh policies depend on ([UDS Core overview](https://uds.defenseunicorns.com/reference/uds-core/overview/)).

---

## Step 1 — Create / label namespaces for Istio injection

```bash
# Apply the six namespaces with istio-injection=enabled + PSS-restricted labels.
kubectl apply -f mesh/namespaces.yaml

# Equivalent imperative form for namespaces that already exist:
for ns in szl-rosie szl-a11oy szl-amaru szl-sentra szl-vessels; do
  kubectl label namespace "$ns" istio-injection=enabled --overwrite
done

# Confirm the label took:
kubectl get namespace -L istio-injection \
  szl-rosie szl-a11oy szl-amaru szl-sentra szl-vessels szl-receipts
```

The `istio-injection=enabled` label triggers automatic sidecar injection on subsequent pod creation ([Istio sidecar injection](https://istio.io/latest/docs/setup/additional-setup/sidecar-injection/)).

> `szl-receipts` already carries an Istio dataplane label in [`manifests/namespace.yaml`](../../manifests/namespace.yaml) (ambient). For a uniform sidecar mesh, switch it to `istio-injection=enabled`; if the cluster runs ambient mode, leave the ambient label in place — both produce mTLS.

---

## Step 2 — Restart workloads so sidecars are injected

```bash
# Injection happens at pod creation time, so existing pods must be recreated.
for ns in szl-rosie szl-a11oy szl-amaru szl-sentra szl-vessels szl-receipts; do
  kubectl rollout restart deployment -n "$ns"
  kubectl rollout status  deployment -n "$ns" --timeout=120s
done

# Verify the istio-proxy sidecar is present on a sample pod:
kubectl describe pod -n szl-a11oy -l app=a11oy | grep -A1 istio-proxy
```

Injection occurs only at pod creation; restarting the Deployment recreates the pods with the `istio-proxy` sidecar ([Istio sidecar injection](https://istio.io/latest/docs/setup/additional-setup/sidecar-injection/)).

---

## Step 3 — Apply the UDS Package CRs

```bash
kubectl apply -f packages/rosie/uds-package.yaml
kubectl apply -f packages/a11oy/uds-package.yaml
kubectl apply -f packages/amaru/uds-package.yaml
kubectl apply -f packages/sentra/uds-package.yaml
kubectl apply -f packages/vessels/uds-package.yaml

# The UDS Operator (Pepr) reconciles each Package into VirtualService +
# NetworkPolicy + Keycloak client + authservice protection + ServiceMonitor.
kubectl get packages.uds.dev -A
kubectl get networkpolicies -A | grep szl-
kubectl get virtualservices.networking.istio.io -A | grep szl-
```

Each `Package` CR (`uds.dev/v1alpha1`) is consumed by the UDS Operator, which generates the per-module Istio + NetworkPolicy + SSO + monitor resources ([UDS Package CR reference](https://uds.defenseunicorns.com/reference/configuration/custom-resources/packages-v1alpha1-cr/)).

---

## Step 4 — Apply PeerAuthentication: STRICT (mTLS)

```bash
kubectl apply -f mesh/peerauth/peerauthentication-strict.yaml

# Confirm STRICT is in effect per namespace:
kubectl get peerauthentication -A
```

STRICT requires every inbound connection to the namespace's workloads to be an mTLS tunnel ([Istio PeerAuthentication](https://istio.io/latest/docs/reference/config/security/peer_authentication/)). This is applied **after** Step 2 so that every pod already has a sidecar to terminate mTLS; applying it earlier would reject plaintext traffic from not-yet-injected pods.

---

## Step 5 — Apply AuthorizationPolicies (the 6×6 matrix)

```bash
kubectl apply -f mesh/authpolicies/

kubectl get authorizationpolicies -A | grep allow-mesh-to
# expect: allow-mesh-to-rosie / -a11oy / -amaru / -sentra / -vessels / -receipts
```

Each `AuthorizationPolicy` is an `ALLOW` policy listing the permitted caller SPIFFE principals for one callee workload; the implicit deny (everything not allowed is rejected) enforces the 14 DENY pairs ([Istio AuthorizationPolicy](https://istio.io/latest/docs/reference/config/security/authorization-policy/), [Istio security best practices](https://istio.io/latest/docs/ops/best-practices/security/)).

---

## Step 6 — Verify

```bash
# 6a. All six namespaces injected (AC-4)
istioctl proxy-status

# 6b. Allowed path works with mTLS (AC-1)
kubectl exec -n szl-a11oy deploy/a11oy -c a11oy -- \
  curl -s -o /dev/null -w '%{http_code}\n' \
  http://amaru.szl-amaru.svc.cluster.local:8080/healthz      # expect 200

# 6c. Denied path is blocked by AuthorizationPolicy (AC-2)
kubectl exec -n szl-amaru deploy/amaru -c amaru -- \
  curl -s -o /dev/null -w '%{http_code}\n' \
  http://vessels.szl-vessels.svc.cluster.local:8080/healthz  # expect 403

# 6d. Receipt chain reachable + Ed25519-verifiable (AC-3)
kubectl exec -n szl-a11oy deploy/a11oy -c a11oy -- \
  curl -s http://szl-receipts.szl-receipts.svc.cluster.local:8080/receipts/latest

# 6e. mTLS effective mode per workload
istioctl x describe pod -n szl-amaru "$(kubectl get pod -n szl-amaru -l app=amaru -o jsonpath='{.items[0].metadata.name}')"
```

Full pass/fail definitions are in [`MESH_ACCEPTANCE_CRITERIA.md`](./MESH_ACCEPTANCE_CRITERIA.md).

---

## Rollback

```bash
# Remove enforcement in reverse order (authz first, then mTLS), leaving pods up.
kubectl delete -f mesh/authpolicies/
kubectl delete -f mesh/peerauth/peerauthentication-strict.yaml
# Optionally revert namespaces to no injection and restart:
for ns in szl-rosie szl-a11oy szl-amaru szl-sentra szl-vessels; do
  kubectl label namespace "$ns" istio-injection- 
  kubectl rollout restart deployment -n "$ns"
done
```

Removing the AuthorizationPolicies first prevents a window where mTLS is off but authz still references principals that can no longer be proven.

---

## Pre-flight validation (no cluster required)

Before any cluster apply, validate the YAML offline. With cluster access, use the dry-run validators; without it, a YAML parse is the available check (this design PR was validated with the parse path, since it runs no cluster):

```bash
# Server-side schema validation (requires cluster + CRDs installed):
kubectl apply --dry-run=server -f mesh/peerauth/peerauthentication-strict.yaml
kubectl apply --dry-run=server -f mesh/authpolicies/
for p in rosie a11oy amaru sentra vessels; do
  kubectl apply --dry-run=server -f packages/$p/uds-package.yaml
done

# Client-side structural validation (no cluster connection):
kubectl apply --dry-run=client -f mesh/ -R

# Offline syntactic validation (no kubectl, no cluster) — used for this design PR:
python3 - <<'PY'
import yaml, glob
for f in glob.glob("mesh/**/*.yaml", recursive=True) + glob.glob("packages/**/uds-package.yaml", recursive=True):
    list(yaml.safe_load_all(open(f)))  # raises on malformed YAML
    print("OK", f)
PY
```

---

## References

- UDS Core overview: https://uds.defenseunicorns.com/reference/uds-core/overview/
- UDS Package CR (v1alpha1): https://uds.defenseunicorns.com/reference/configuration/custom-resources/packages-v1alpha1-cr/
- Istio sidecar injection: https://istio.io/latest/docs/setup/additional-setup/sidecar-injection/
- Istio PeerAuthentication: https://istio.io/latest/docs/reference/config/security/peer_authentication/
- Istio AuthorizationPolicy: https://istio.io/latest/docs/reference/config/security/authorization-policy/
- Istio security best practices: https://istio.io/latest/docs/ops/best-practices/security/
