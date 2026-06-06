# Mesh interconnect — v0.4.0 roadmap (the nervous system)

**Status:** Draft / roadmap. Nothing here is shipped.
**Target release:** v0.4.0.
**Owner:** SZL Holdings Engineering.

## Problem statement (honest baseline)

Today the five SZL modules are **five isolated single-replica Deployments**, each in its own namespace, each exposing a `ClusterIP` on `:80 → :8080`, that **never reference one another**. There is:

- no service registry or discovery,
- no orchestrator endpoint that other modules call,
- no Kubernetes-DNS wiring between modules,
- no Istio `VirtualService` / `PeerAuthentication`,
- no mTLS configuration,
- no UDS `Package` CR on any module (so uds-core's default-deny network policy would block them).

A search for `svc.cluster.local|register|orchestrat|discovery|virtualservice|peerauthentication|mtls` across all five module `deploy/` dirs returns nothing. **Until modules actually call each other over the mesh, this is not a mesh — it is five Helm installs.** This document defines what would make it one.

## Anatomy mapping (the body this nervous system connects)

| Module | Role | Mesh function |
|--------|------|---------------|
| **rosie** | operator console | Human-facing command surface; issues commands into the mesh |
| **a11oy** | policy + receipt substrate | Orchestrator service the other organs register with and call |
| **amaru** | memory | Stateful organ behind the substrate |
| **sentra** | immune | Egress/tripwire organ |
| **vessels** | deployment fabric | Structural proving ground / app surface |

## Acceptance criteria (v0.4.0 — derived from PhD Systems review recommendation #2)

> *"If a mesh is the thesis, build an actual interconnect. Stand a11oy up as a real orchestrator service, give the other four a UDS `Package` CR each (so Istio injects sidecars and mTLS is automatic), and wire service discovery via Kubernetes DNS. Add `PeerAuthentication: STRICT` and AuthorizationPolicies so module-to-module traffic is mTLS-only and authservice-gated."*

A `v0.4.0` interconnect is **accepted** only when ALL of the following hold and are demonstrable on a uds-core slim-dev cluster:

1. **a11oy orchestrator service.** a11oy exposes a real orchestrator HTTP/gRPC endpoint (not a math library function). The other four modules register with it and route commands through it. rosie's console drives the mesh by calling a11oy, not by calling each module directly.

2. **UDS `Package` CR per module.** Each of rosie, a11oy, amaru, sentra, vessels ships an `apiVersion: uds.dev/v1alpha1, kind: Package` CR in its `deploy/`, following the `szl-receipts` pattern (SSO/authservice selector, Istio tenant/admin expose, NetworkPolicy allow-rules, OTLP egress). `grep 'kind: Package'` across all five `deploy/` dirs must be **non-empty**. This is what triggers Istio sidecar injection.

3. **Istio sidecar injection + automatic mTLS.** Every module pod runs with an injected Istio sidecar (verify: each pod has 2/2 containers). Traffic between modules is transparently mTLS-encrypted by Istio.

4. **Kubernetes-DNS service discovery.** Modules resolve each other by stable DNS names, e.g. `a11oy.a11oy.svc.cluster.local`. No hard-coded IPs; no out-of-band registry. amaru/sentra/vessels resolve and reach a11oy by DNS.

5. **`PeerAuthentication: STRICT`.** A `PeerAuthentication` resource (mesh-wide or per-namespace) sets `mtls.mode: STRICT`, so any non-mTLS (plaintext) module-to-module traffic is rejected. Verify by attempting a plaintext call and observing a connection reset.

6. **AuthorizationPolicies (authservice-gated).** `AuthorizationPolicy` resources restrict which source identities may call which module endpoints, so module-to-module traffic is mTLS-only **and** authorization-gated (not just encrypted). Default-deny with explicit allow-rules between known principals.

7. **Real cross-module traffic demonstrated.** An end-to-end path is exercised on a live cluster: rosie console → a11oy orchestrator → (amaru / sentra / vessels), with the call producing a verifiable receipt. Captured as evidence (Istio access logs / OTel trace showing the inter-pod hops over mTLS).

## Out of scope for v0.4.0 (later)

- Durable receipt storage (replace the single-replica `emptyDir` with a real volume/DB).
- Real DSSE signing (replace the checked-in HMAC demo key with cosign keyless / org KMS).
- Live OTLP trace emission from module code (today spans are a documented schema, not a live signal).
- HA uds-core (slim-dev is single-instance Keycloak/Pepr).

## Definition of done

`docs/roadmap/MESH_INTERCONNECT.md` criteria 1–7 are each backed by a merged PR and a reproducible verification command, demonstrated together on one slim-dev cluster, before the word "mesh" is used in any release note without qualification.

## References

- PhD Systems review recommendation #2 — internal `PhD_SYSTEMS_VERDICT.md` (mesh interconnect realism scored 1/10 at baseline).
- UDS Core Package CR integration pattern: https://uds.defenseunicorns.com/core/
- Istio `PeerAuthentication` (STRICT mTLS): https://istio.io/latest/docs/reference/config/security/peer_authentication/
- Istio `AuthorizationPolicy`: https://istio.io/latest/docs/reference/config/security/authorization-policy/
- Kubernetes DNS for Services: https://kubernetes.io/docs/concepts/services-networking/dns-pod-service/
- Reference correct integration: `szl-holdings/szl-uds-deployment` `charts/szl-receipts/templates/uds-package.yaml`.
