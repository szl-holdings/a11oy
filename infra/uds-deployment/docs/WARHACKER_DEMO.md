# Warhacker 2026 — SZL Running Deployment Talk Track

**Event:** Warhacker, San Diego, June 16-20, 2026  
**Audience:** Andrew Greene (Defense Unicorns co-founder) + any adjacent DU technical staff  
**Format:** 5-minute live cluster demo (laptop, k3d, UDS CLI)  
**Stack:** k3d + uds-cli + uds-core slim-dev + szl-receipts Pepr policy  

---

## Prep (before the room)

```bash
# 1. Cluster running?
k3d cluster list | grep uds-szl-demo

# 2. Bundle deployed?
kubectl get pods -n szl-receipts

# 3. Dashboard reachable?
kubectl port-forward svc/szl-receipts-server 8443:8443 -n szl-receipts &
curl -s http://localhost:8443/health | python3 -m json.tool

# 4. Receipt feed empty? (expected — no workloads yet)
curl -s http://localhost:8443/receipts | python3 -c "import sys,json; r=json.load(sys.stdin); print(f'{len(r)} receipts')"
```

If anything is not running: `uds run start` (≈90 seconds from scratch).

---

## Minute 0 — Open (15 seconds)

> "Andrew said he wanted to see a running deployment — so here it is.
> This is not a USB demo. It's a live k3d cluster, uds-core slim-dev,
> and SZL governance receipts emitting from real Kubernetes workloads.
> Let me show you what that looks like."

_Open terminal. Show k3d cluster:_

```bash
k3d cluster list
# uds-szl-demo   1/1   1/1   running
```

_Open browser at http://localhost:8443 — empty receipt feed visible._

> "This is the SZL receipt dashboard. No receipts yet — because nothing has been deployed.
> Watch what happens when I push a workload."

---

## Minute 1 — Boot (if starting from scratch, 60–90 seconds)

> "The whole thing starts with one command:"

```bash
uds run start
```

_Walk through what the output shows:_

1. k3d cluster created
2. Zarf package built (images bundled — air-gap compatible)
3. UDS bundle deployed: init → uds-k3d-dev → core slim-dev → szl-receipts
4. Pepr policy webhook registered

> "UDS handles the bootstrapping. Our add-on is just another package in the bundle.
> No modifications to uds-core, no AGPL entanglement — it's a separate workload."

---

## Minute 2 — Dashboard (30 seconds)

_Browser is already open at http://localhost:8443._

> "Empty receipt feed. The Pepr policy is live — it's watching every Deployment
> and Job API call cluster-wide. The moment something lands in etcd,
> a receipt fires."

_Show the stats panel: Total 0, Verified 0._

> "These receipts are DSSE envelopes — Dead Simple Signing Envelopes.
> Same format used by sigstore and in-toto. HMAC-SHA-256 in demo mode,
> Ed25519 in production."

---

## Minute 3 — Trigger a workload (60 seconds)

```bash
uds run demo:workload
# OR:
kubectl apply -f scripts/demo_workload.yaml
```

_Watch the browser — receipt appears within ~5 seconds._

> "There it is. The Pepr admission webhook intercepted the Deployment API call,
> computed a SHA-256 of the workload spec, wrapped it in a DSSE envelope,
> posted it to the receipts server, and annotated the resource — all before
> the Deployment hit etcd."

_Show terminal:_

```bash
kubectl get deployment szl-demo-agent -n szl-demo-workload \
  -o jsonpath='{.metadata.annotations}' | python3 -m json.tool
```

Expected output:
```json
{
  "szl.receipt.id": "a3f2b1c4d5e6...",
  "szl.receipt.ts": "2026-06-16T14:23:01Z",
  "szl.receipt.key": "szl-dev-hmac-sha256-2026"
}
```

> "The annotation lives in Kubernetes metadata. Any auditor, any policy engine,
> any SIEM can query it. No side-channel required."

---

## Minute 4 — DSSE envelope + doctrine (60 seconds)

_Click the receipt in the dashboard to expand._

> "Here's the full DSSE envelope. Payload decodes to this:"

```json
{
  "_type":       "https://szlholdings.com/receipt/v1",
  "subject":     "szl-demo-workload/Deployment/szl-demo-agent",
  "specHash":    "b4c3a2...",
  "timestamp":   "2026-06-16T14:23:01Z",
  "admissionOp": "CREATE"
}
```

> "The specHash is the SHA-256 of the Deployment spec — the exact pod template,
> containers, resource limits. If someone mutates this Deployment later,
> the receipt hash won't match. That's your governance gate."

_Show the second receipt (from the Job):_

> "Two workloads, two receipts. One Deployment, one Job. Same pattern scales
> to every workload in the cluster — we're watching all of them."

---

## Minute 5 — Verify + UDS doctrine fit (30 seconds)

```bash
uds run demo:verify
# PASS  a3f2b1c4…  2026-06-16T14:23:01Z  op=CREATE  subject=szl-demo-workload/Deployment/szl-demo-agent
# PASS  b2c3d4e5…  2026-06-16T14:23:02Z  op=CREATE  subject=szl-demo-workload/Job/szl-demo-job
# Summary: 2 VERIFIED, 0 UNVERIFIED out of 2 receipts
```

> "Verification passes. In a production UDS deployment, this verification step
> becomes a UDS policy gate — a bundle can be configured to reject deployments
> that don't carry a valid receipt. That's the governance layer."

> "Where this fits in UDS doctrine: we're not replacing uds-core security policies.
> We're adding an audit trail that network-emits receipts. The receipt server
> is just another pod. The Pepr policy is contributable upstream.
> The bundle is air-gap-compatible — it runs completely offline."

_Pause._

> "That's the running deployment Andrew asked for. Any questions?"

---

## Objection Handling

**"This is just a demo key — how does it work in production?"**

> "In production, you replace HMAC-SHA-256 with an Ed25519 keypair.
> The public key lives in a ConfigMap; the private key is in a sealed secret
> or Vault. Cosign signs the Zarf package at build time.
> The DSSE format doesn't change — only the key type."

**"Does this affect admission latency?"**

> "The Pepr webhook runs asynchronously — the receipt POST is fire-and-forget.
> If the receipts server is unreachable, the policy is fail-open: the workload
> admits normally, and the annotation records an empty receipt ID.
> No workloads are blocked."

**"Can this integrate with our existing SIEM?"**

> "Yes. The receipts server exposes a Prometheus /metrics endpoint and a
> server-sent events /stream endpoint. Any log aggregator that can hit an
> HTTP endpoint (Loki, Vector, Fluentbit) can consume the receipt stream."

**"Is this AGPL? Can we use it?"**

> "The Pepr policy module is Apache-2.0. It's designed to be contributable
> to the Defense Unicorns ecosystem. The receipts server is also Apache-2.0.
> Nothing in this add-on touches the AGPL uds-core code."

---

## What This Is NOT

- Not a replacement for uds-core security policies (Falco, OPA, NetworkPolicies)
- Not a certified DoD package (that's Phase 2 — get an ATF assessment)
- Not production-hardened (cosign signing, Ed25519 keys, HA mode are all Phase 2)
- Not a modification of uds-core — it runs as a separate add-on with zero AGPL entanglement

---

*Last updated: 2026-06-09 | Doctrine v6 strict | Apache-2.0*
