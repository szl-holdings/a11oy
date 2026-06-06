<!--
Copyright 2026 SZL Holdings
SPDX-License-Identifier: Apache-2.0
-->

# Mesh Interconnect Design — v0.4.0

**Status:** Design (implementable in ~2 days once FA-001 images exist — see [Implementation estimate](#implementation-estimate)).
**Scope:** Addresses PhD Systems verdict dimension **C. Mesh interconnect realism (1/10)** — *"There is no interconnect. Five isolated single-pod deployments in five namespaces with no cross-references, no service discovery, no mTLS, no orchestrator."* This document specifies the real interconnect: a11oy as an orchestrator service, a UDS Package CR per module, Kubernetes-DNS service discovery, `PeerAuthentication: STRICT` mTLS, and a full `AuthorizationPolicy` matrix.
**Non-goal:** This is design only. No images run yet (FA-001). Nothing here is executed against a cluster.

This is the v0.4.0 thesis: until the modules actually call each other over the mesh with mTLS and authorization, it is not a mesh. The design below makes that real.

---

## 1. Hierarchy

Per the founder's standing rule (2026-05-30 — rosie is the operator console; A11OY_NON_NEGOTIABLES forbids any other name), the stack is, top to bottom:

| Tier | Module | Role | Internal DNS |
|---|---|---|---|
| 1 (top, human-facing) | **rosie** | operator console (Gradio, 6 tabs). The voice/face/command surface the human principal talks to. Not an organ — sits outside the body like a console wired in. | `rosie.szl-rosie.svc.cluster.local:7860` |
| 2 (substrate) | **a11oy** | Policy + receipt substrate and the **orchestrator**. Contains 9 of 14 Inca-named organs (YUYAY heart, YAWAR emission, HATUN seal, HATUN-RAID orchestrator, Quantum Mind, R0513 Overwatch, RIMAY proposer, KALLPA substrate, doctrine v7). | `a11oy.szl-a11oy.svc.cluster.local:8080` |
| 3 (organ) | **amaru** | Memory cortex a11oy queries (YACHAY retrieval + MUSQUY simulation + AMARU shell). | `amaru.szl-amaru.svc.cluster.local:8080` |
| 3 (organ) | **sentra** | Immune system a11oy delegates security verdicts to (HUKLLA 10 tripwires + SENTRA egress inspector). | `sentra.szl-sentra.svc.cluster.local:8080` |
| 3 (organ) | **vessels** | Skeleton / structural deployment fabric where the organism runs. Downstream of a11oy. | `vessels.szl-vessels.svc.cluster.local:8080` |
| cross-cutting | **mcp-receipts-server** + **szl-receipts** | RAWI tool surface (17 MCP tools, already live) and the **YAWAR receipt chain authority**. Every module POSTs receipts here. | `szl-receipts.szl-receipts.svc.cluster.local:8080` |

```
                        ┌──────────────────────────┐
   human principal ───► │  rosie (operator console)   │  szl-rosie : 7860
                        └────────────┬─────────────┘
                          commands   │   ▲ events
                                     ▼   │
                        ┌──────────────────────────┐
                        │  a11oy (orchestrator +    │  szl-a11oy : 8080
                        │  policy + receipt subst.) │
                        └──┬─────────┬─────────┬────┘
              query memory │ delegate│         │ command
                           ▼   verdicts        ▼
              ┌────────────────┐ ┌────────────┐ ┌────────────────┐
              │ amaru (memory) │ │ sentra     │ │ vessels        │
              │ szl-amaru:8080 │ │ (immune)   │ │ (skeleton)     │
              └───────┬────────┘ │ szl-sentra │ │ szl-vessels    │
                      │          │ :8080      │ │ :8080          │
                      │          └─────┬──────┘ └───────┬────────┘
                      │  (sentra may inspect ANY module)│
                      ▼                ▼                ▼
              ┌─────────────────────────────────────────────────┐
              │  szl-receipts-server — YAWAR chain authority     │  szl-receipts : 8080
              │  (all 5 modules POST receipts here; Ed25519)     │
              └─────────────────────────────────────────────────┘
```

The defining property the audit said was missing: **edges exist**. rosie→a11oy, a11oy→{amaru,sentra,vessels}, organs→a11oy, all→szl-receipts. Each edge is a Kubernetes Service call over an mTLS tunnel, gated by an `AuthorizationPolicy`.

---

## 2. Service discovery (Kubernetes DNS)

Every module is reachable by a stable in-cluster DNS name of the form `<service>.<namespace>.svc.cluster.local:<port>`, which is the standard Kubernetes DNS-for-Services contract ([Kubernetes DNS for Services and Pods](https://kubernetes.io/docs/concepts/services-networking/dns-pod-service/)).

| Module | Service | Internal DNS endpoint |
|---|---|---|
| rosie | `rosie` | `rosie.szl-rosie.svc.cluster.local:7860` |
| a11oy | `a11oy` | `a11oy.szl-a11oy.svc.cluster.local:8080` |
| amaru | `amaru` | `amaru.szl-amaru.svc.cluster.local:8080` |
| sentra | `sentra` | `sentra.szl-sentra.svc.cluster.local:8080` |
| vessels | `vessels` | `vessels.szl-vessels.svc.cluster.local:8080` |
| szl-receipts | `szl-receipts` | `szl-receipts.szl-receipts.svc.cluster.local:8080` |

No bespoke service registry, no orchestrator-maintained endpoint table. a11oy resolves `amaru.szl-amaru.svc.cluster.local` through cluster DNS exactly as the PhD Systems third recommendation prescribed. The `network.allow` egress rule in each Package CR also grants DNS resolution via `remoteGenerated: KubeAPI` ([UDS Package CR — network.allow fields](https://uds.defenseunicorns.com/reference/configuration/custom-resources/packages-v1alpha1-cr/)).

---

## 3. mTLS — `PeerAuthentication: STRICT` per namespace

Each of the six namespaces gets a namespace-wide `PeerAuthentication` named `default` with `mtls.mode: STRICT`. In Istio, `STRICT` means *"Connection is an mTLS tunnel (TLS with client cert must be presented)"* ([Istio PeerAuthentication — Mode](https://istio.io/latest/docs/reference/config/security/peer_authentication/)). The namespace-wide policy is conventionally named `default` ([Istio authentication policy task](https://istio.io/latest/docs/tasks/security/authentication/authn-policy/)).

STRICT mTLS is the substrate the authorization layer depends on: `AuthorizationPolicy` `source.principals` are *"derived from the peer certificate"* and *"require[] mTLS enabled"* ([Istio AuthorizationPolicy — from.source](https://istio.io/latest/docs/reference/config/security/authorization-policy/)). Without STRICT mTLS, principal identity is unprovable and the matrix below is unenforceable.

File: [`mesh/peerauth/peerauthentication-strict.yaml`](../../mesh/peerauth/peerauthentication-strict.yaml). Per-namespace shape:

```yaml
apiVersion: security.istio.io/v1
kind: PeerAuthentication
metadata:
  name: default
  namespace: szl-a11oy        # repeated for szl-rosie, szl-amaru, szl-sentra, szl-vessels, szl-receipts
spec:
  mtls:
    mode: STRICT
```

> **Ordering constraint.** STRICT must be applied **after** sidecars exist in every namespace (see [§6 Pepr admission injection](#6-pepr-admission-injection-sidecars)). Applying STRICT to a namespace whose pods have no sidecar would reject all plaintext traffic and wedge the module. The [runbook](./MESH_DEPLOYMENT_RUNBOOK.md) sequences label → restart → STRICT.

---

## 4. AuthorizationPolicies — the deny rules

### 4.1 Authorization model

UDS Core / Istio enforce authorization with `AuthorizationPolicy` (`security.istio.io/v1`). The chosen model is **ALLOW-with-implicit-deny**: per Istio semantics, when at least one `ALLOW` policy selects a workload, any request to that workload that is *not* matched by an ALLOW rule is denied ([Istio AuthorizationPolicy — spec.rules](https://istio.io/latest/docs/reference/config/security/authorization-policy/), [Istio security best practices](https://istio.io/latest/docs/ops/best-practices/security/)). So one `ALLOW` policy per callee, listing the permitted caller SPIFFE principals, fully encodes the matrix without writing explicit `DENY` rules — the deny is the absence of an allow.

Caller identity is the SPIFFE principal `cluster.local/ns/<namespace>/sa/<serviceAccount>` ([Istio AuthorizationPolicy — principals](https://istio.io/latest/docs/reference/config/security/authorization-policy/)):

| Module | ServiceAccount | SPIFFE principal |
|---|---|---|
| rosie | `rosie` | `cluster.local/ns/szl-rosie/sa/rosie` |
| a11oy | `a11oy` | `cluster.local/ns/szl-a11oy/sa/a11oy` |
| amaru | `amaru` | `cluster.local/ns/szl-amaru/sa/amaru` |
| sentra | `sentra` | `cluster.local/ns/szl-sentra/sa/sentra` |
| vessels | `vessels` | `cluster.local/ns/szl-vessels/sa/vessels` |
| szl-receipts | `szl-receipts-server` | `cluster.local/ns/szl-receipts/sa/szl-receipts-server` |

### 4.2 The full 6×6 matrix

Rows = caller, columns = callee. Self-traffic (diagonal) is implicitly ALLOW (intra-namespace). 36 ordered pair-states total: 6 self-ALLOW + 16 cross-ALLOW + 14 cross-DENY.

| caller \ callee | rosie | a11oy | amaru | sentra | vessels | receipts |
|---|---|---|---|---|---|---|
| **rosie** | ALLOW | **ALLOW** | DENY | DENY | DENY | ALLOW |
| **a11oy** | **ALLOW** | ALLOW | **ALLOW** | **ALLOW** | **ALLOW** | ALLOW |
| **amaru** | DENY | **ALLOW** | ALLOW | DENY | DENY | ALLOW |
| **sentra** | ALLOW | ALLOW | ALLOW | ALLOW | ALLOW | ALLOW |
| **vessels** | DENY | **ALLOW** | DENY | DENY | ALLOW | ALLOW |
| **receipts** | DENY | DENY | DENY | DENY | DENY | ALLOW |

Per-pair rationale (the 30 cross-pairs):

| Pair | Verdict | Rationale |
|---|---|---|
| rosie → a11oy | ALLOW | rosie commands a11oy (operator → policy substrate) |
| rosie → amaru | DENY | operator commands route through a11oy, never direct to organs |
| rosie → sentra | DENY | operator commands route through a11oy, never direct to organs |
| rosie → vessels | DENY | operator commands route through a11oy, never direct to organs |
| rosie → receipts | ALLOW | receipt fan-out: rosie emits human-confirmation receipts |
| a11oy → rosie | ALLOW | a11oy emits events to rosie for human display |
| a11oy → amaru | ALLOW | a11oy queries memory |
| a11oy → sentra | ALLOW | a11oy delegates security checks |
| a11oy → vessels | ALLOW | a11oy commands the deployment fabric |
| a11oy → receipts | ALLOW | receipt fan-out: a11oy emits gate accept/deny receipts |
| amaru → rosie | DENY | memory has no need to reach the operator |
| amaru → a11oy | ALLOW | amaru responds to a11oy memory queries |
| amaru → sentra | DENY | memory doesn't need to talk to the immune system |
| amaru → vessels | DENY | memory doesn't need to talk to the skeleton |
| amaru → receipts | ALLOW | receipt fan-out: amaru emits memory-write receipts |
| sentra → rosie | ALLOW | sentra is the immune system; may inspect all traffic |
| sentra → a11oy | ALLOW | immune verdicts + inspection |
| sentra → amaru | ALLOW | immune inspection |
| sentra → vessels | ALLOW | immune inspection |
| sentra → receipts | ALLOW | receipt fan-out: sentra emits egress accept/deny receipts |
| vessels → rosie | DENY | deployment fabric is downstream; no operator calls |
| vessels → a11oy | ALLOW | vessels reports deployment status up to a11oy |
| vessels → amaru | DENY | deployment fabric has no need to reach memory |
| vessels → sentra | DENY | deployment fabric has no need to reach the immune system |
| vessels → receipts | ALLOW | receipt fan-out: vessels emits deployment-event receipts |
| receipts → rosie | DENY | receipts-server is a sink; never initiates calls |
| receipts → a11oy | DENY | receipts-server is a sink; never initiates calls |
| receipts → amaru | DENY | receipts-server is a sink; never initiates calls |
| receipts → sentra | DENY | receipts-server is a sink; never initiates calls |
| receipts → vessels | DENY | receipts-server is a sink; never initiates calls |

Two policy invariants make this auditable:
- **sentra row is all-ALLOW** — the immune system may reach every module to inspect traffic (founder rule: *"sentra → ANY: ALLOW"*).
- **receipts column is all-ALLOW, receipts row is all-DENY** — every module emits to the chain authority; the chain authority never calls back (it is a sink).
- **vessels is downstream** — inbound only from a11oy (commands) and sentra (inspection); outbound only to a11oy (status) and receipts.

### 4.3 YAML resources

Six `AuthorizationPolicy` resources, one per callee workload, in [`mesh/authpolicies/`](../../mesh/authpolicies/). Each is generated deterministically from the matrix by [`mesh/_authpolicy_gen.py`](../../mesh/_authpolicy_gen.py). Representative example — who may call **a11oy** (rosie, amaru, sentra, vessels — i.e., everyone except receipts):

```yaml
apiVersion: security.istio.io/v1
kind: AuthorizationPolicy
metadata:
  name: allow-mesh-to-a11oy
  namespace: szl-a11oy
spec:
  selector:
    matchLabels:
      app: a11oy
  action: ALLOW
  rules:
    - from:
        - source:
            principals:
              - "cluster.local/ns/szl-rosie/sa/rosie"
              - "cluster.local/ns/szl-amaru/sa/amaru"
              - "cluster.local/ns/szl-sentra/sa/sentra"
              - "cluster.local/ns/szl-vessels/sa/vessels"
      to:
        - operation:
            ports: ["8080", "7860", "8443"]
```

The callee that is *most* restricted is **amaru** (only a11oy and sentra may reach it) and **vessels** (only a11oy and sentra). **receipts** accepts from all five modules. The `to.operation.ports` list constrains the matched ports ([Istio AuthorizationPolicy — to.operation](https://istio.io/latest/docs/reference/config/security/authorization-policy/)).

> **authservice gating.** rosie and vessels expose human UIs and are additionally gated by the authservice sidecar via their Package CR `sso.enableAuthserviceSelector`, so module-to-module traffic is mTLS-gated *and* human traffic is OIDC-gated. See [§5](#5-uds-package-cr-per-module).

---

## 5. UDS Package CR per module

Today only `szl-receipts` ships a `Package` CR; the five modules ship raw Deployment+Service+PVC+Namespace with zero UDS integration (PhD Systems Scope 4/5/8). v0.4.0 adds one `Package` CR (`uds.dev/v1alpha1`) per module. The UDS Operator (Pepr) consumes each CR and generates the Istio `VirtualService`, Kubernetes `NetworkPolicy` set, Keycloak client, authservice protection, and Prometheus `ServiceMonitor`.

Every field used is documented in the [UDS Package CR (v1alpha1) reference](https://uds.defenseunicorns.com/reference/configuration/custom-resources/packages-v1alpha1-cr/):

- **`spec.sso`** — `clientId`, `redirectUris`, `enableAuthserviceSelector`, `groups.anyOf`, `serviceAccountsEnabled`, `standardFlowEnabled` (reference §"sso fields").
- **`spec.network.expose`** — `service`, `selector`, `gateway` (one of `tenant` / `admin` / `passthrough`), `host`, `port`, `targetPort`, `description` (reference §"network.expose fields").
- **`spec.network.allow`** — `direction` (Ingress/Egress), `selector`, `remoteNamespace`, `remoteSelector`, `remoteGenerated` (e.g. `KubeAPI`), `port`, `description` (reference §"network.allow fields"). `remoteNamespace: "*"` allows all namespaces (same section).
- **`spec.monitor`** — `portName`, `selector`, `targetPort`, `path`, `kind` (`ServiceMonitor` / `PodMonitor`), `description` (reference §"monitor fields").

| Module | Package CR | expose | sso | network.allow (egress / ingress) | monitor |
|---|---|---|---|---|---|
| rosie | [`packages/rosie/uds-package.yaml`](../../packages/rosie/uds-package.yaml) | tenant gateway `rosie` :7860 | authservice, group `/szl/operators` | egress→a11oy, receipts; ingress←a11oy, sentra | :7860 `/metrics` |
| a11oy | [`packages/a11oy/uds-package.yaml`](../../packages/a11oy/uds-package.yaml) | none (internal) | machine client (`serviceAccountsEnabled`) | egress→amaru, sentra, vessels, rosie, receipts; ingress←rosie, amaru, sentra, vessels | :8080 `/metrics` |
| amaru | [`packages/amaru/uds-package.yaml`](../../packages/amaru/uds-package.yaml) | none (internal) | machine client | egress→a11oy, receipts; ingress←a11oy, sentra | :8080 `/metrics` |
| sentra | [`packages/sentra/uds-package.yaml`](../../packages/sentra/uds-package.yaml) | none (internal) | machine client | egress→a11oy, amaru, vessels, rosie, receipts; ingress←a11oy | :8080 `/metrics` |
| vessels | [`packages/vessels/uds-package.yaml`](../../packages/vessels/uds-package.yaml) | tenant gateway `vessels` :8080 (read-only) | authservice, group `/szl/operators` | egress→a11oy, receipts; ingress←a11oy, sentra | :8080 `/metrics` |

The `network.allow` block in each Package CR mirrors the §4.2 matrix exactly: an egress allow exists iff the matrix says caller→callee is ALLOW, and an ingress allow exists iff some caller→this-module is ALLOW. The `Package`-generated `NetworkPolicy` is the L3/L4 defense-in-depth layer; the `AuthorizationPolicy` is the L7 mTLS-identity layer. Both must agree, and they do by construction.

> **Why both NetworkPolicy and AuthorizationPolicy?** The reference `szl-receipts` chart already pairs UDS-generated policy with hand-written `NetworkPolicy` for defense-in-depth ([`charts/szl-receipts/templates/networkpolicy.yaml`](../../charts/szl-receipts/templates/networkpolicy.yaml)). v0.4.0 keeps that pattern: NetworkPolicy blocks the packet, AuthorizationPolicy blocks the request even if a packet slips through (e.g., a shared L3 path), and STRICT mTLS proves the identity the AuthorizationPolicy trusts.

---

## 6. Pepr admission injection (sidecars)

Istio sidecar injection is triggered by the namespace label `istio-injection=enabled`: *"When you set the `istio-injection=enabled` label on a namespace ... any new pods that are created in that namespace will automatically have a sidecar added to them"* ([Istio sidecar injection](https://istio.io/latest/docs/setup/additional-setup/sidecar-injection/)). UDS Core's Pepr-based operator already manages the `szl-receipts` namespace correctly; the gap (PhD Systems Scope 4) is that the five module namespaces lack the label, so no sidecar is injected, so there is no mTLS and no enforceable identity.

Migration (codified in [`mesh/namespaces.yaml`](../../mesh/namespaces.yaml) and the [runbook](./MESH_DEPLOYMENT_RUNBOOK.md)):

1. **Add the label** to each module namespace: `kubectl label namespace szl-<m> istio-injection=enabled --overwrite`.
2. **Restart pods** — injection occurs only *"at pod creation time"*, so existing pods must be recreated: `kubectl rollout restart deployment -n szl-<m>` (or delete the pods). The same doc shows the kill-and-recreate flow ([Istio sidecar injection](https://istio.io/latest/docs/setup/additional-setup/sidecar-injection/)).
3. **Sidecars get injected** — each new pod comes up with the `istio-proxy` container (verify with `kubectl describe pod`).
4. **mTLS auto-negotiates** — once both ends have sidecars, the `PeerAuthentication: STRICT` from §3 forces every inbound connection to be an mTLS tunnel; certificates are issued and rotated by istiod automatically.

The Pepr `szl-receipts` admission controller ([`pepr/policies/szl-receipt-on-deploy.ts`](../../pepr/policies/szl-receipt-on-deploy.ts)) is unchanged by this work — it remains the audit-only `.Mutate` path that fires a receipt on every Deployment/Job admission. v0.4.0 does not alter its fail-open posture.

---

## 7. Receipt fan-out (YAWAR bus)

YAWAR is the cross-cutting append-only receipt bus (anatomy: *"blood — append-only receipt bus, SHA-256 chain ... a11oy emits, all 5 consume"*). In v0.4.0 every module is a producer and `szl-receipts-server` is the single **chain authority** (consumer-of-record). The receipts column in the §4.2 matrix is therefore all-ALLOW.

| Producer | Emits at | Receipt event | Destination |
|---|---|---|---|
| a11oy | decision time | gate accept / deny (YUYAY 13-axis verdict) | `szl-receipts.szl-receipts.svc.cluster.local:8080` |
| amaru | memory write | memory-write attestation | same |
| sentra | egress decision | egress accept / deny (HUKLLA tripwire) | same |
| vessels | deployment event | deploy / rollback event | same |
| rosie | human action | human-confirmation action | same |

Routing properties:
- **Single sink, fan-in topology.** All producers POST to one Service DNS name; the server appends to the SHA-256 (→ Ed25519, see below) chain and is the only writer of chain order. No producer-to-producer receipt traffic.
- **mTLS-authenticated producers.** Each POST carries the producer's SPIFFE identity (STRICT mTLS), so the server can attribute every receipt to a verified module without trusting a body field.
- **AuthorizationPolicy-gated.** `allow-mesh-to-receipts` ([`mesh/authpolicies/allow-mesh-to-receipts.yaml`](../../mesh/authpolicies/allow-mesh-to-receipts.yaml)) permits exactly the five module principals to POST; nothing else can write to the chain.
- **Signature.** The PhD Systems Scope 3 finding is that the current "DSSE" receipt is HMAC-SHA-256 with a symmetric demo key in `values.yaml` (forgeable). v0.4.0 acceptance criterion #3 requires an **Ed25519** signature so each receipt is asymmetrically verifiable; the migration from HMAC to Ed25519 is tracked as a dependency (see [acceptance criteria](./MESH_ACCEPTANCE_CRITERIA.md)).

The receipt bus is the one place where the mesh's value is provable end-to-end: a single operator action in rosie produces a chain of attributed, signed receipts (rosie human-confirm → a11oy gate → amaru memory-write / sentra egress / vessels deploy), all landing in one verifiable chain.

---

## Implementation estimate

See [`MESH_DEPLOYMENT_RUNBOOK.md`](./MESH_DEPLOYMENT_RUNBOOK.md) for the install sequence and [`MESH_ACCEPTANCE_CRITERIA.md`](./MESH_ACCEPTANCE_CRITERIA.md) for the five demonstrable acceptance criteria. The 2-day estimate (defended in the summary deliverable) assumes the five FA-001 images exist and uds-core slim-dev is running; the mesh wiring itself — labels, Package CRs, PeerAuthentication, AuthorizationPolicies — is declarative and lands in well under a day, with the remaining time on per-module `/healthz` + receipt-emission code and acceptance verification.

---

## References

- UDS Package CR (v1alpha1): https://uds.defenseunicorns.com/reference/configuration/custom-resources/packages-v1alpha1-cr/
- UDS Core overview: https://uds.defenseunicorns.com/reference/uds-core/overview/
- Istio PeerAuthentication: https://istio.io/latest/docs/reference/config/security/peer_authentication/
- Istio AuthorizationPolicy: https://istio.io/latest/docs/reference/config/security/authorization-policy/
- Istio security best practices (ALLOW ⇒ implicit deny): https://istio.io/latest/docs/ops/best-practices/security/
- Istio sidecar injection: https://istio.io/latest/docs/setup/additional-setup/sidecar-injection/
- Istio authentication policy task: https://istio.io/latest/docs/tasks/security/authentication/authn-policy/
- Kubernetes DNS for Services and Pods: https://kubernetes.io/docs/concepts/services-networking/dns-pod-service/
- Kubernetes Pod Security Standards: https://kubernetes.io/docs/concepts/security/pod-security-standards/
