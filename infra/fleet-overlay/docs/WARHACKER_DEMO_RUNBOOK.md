# WARHACKER DEMO RUNBOOK
## SZL Holdings — k3d Demo Cluster · June 9–19 2026

**Version:** 1.0.0  
**Doctrine:** v11 LOCKED 749/14/163 @ c7c0ba17 · Λ = Conjecture 1 · SLSA L1  
**Section 889:** 5 vendors excluded (Huawei, ZTE, Hytera, Hikvision, Dahua)  
**NO Iron Bank / FedRAMP / CMMC / SWFT / Mission Owner**

Signed-off-by: Yachay <yachay@szlholdings.ai>  
Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>

---

## 1. Prerequisites

### 1.1 Hardware Minimum

| Item | Minimum | Recommended |
|------|---------|-------------|
| RAM | 8 GB | **16 GB** |
| CPU | 4 cores | 8 cores (RTX tower or modern laptop) |
| Disk free | **20 GB** | 30 GB+ |
| OS | Linux amd64 / macOS (x86 or Apple Silicon) | Ubuntu 22.04 LTS |
| GPU | Not required | RTX 4060 Ti (local LLM optional) |

> **Demo tower at Warhacker:** RTX 4060 Ti, 32 GB RAM — all evals should pass comfortably.

### 1.2 Software Prerequisites

Install all tools before the demo day (not on demo day):

```bash
# 1. Docker Desktop (macOS) or Docker Engine (Linux)
#    https://docs.docker.com/engine/install/
docker --version          # need ≥ 24.0

# 2. k3d (via mise — Defense Unicorns standard)
curl https://mise.run | sh
mise use k3d@5.8.3
k3d version               # need v5.8.x

# 3. kubectl
mise use kubectl@1.30
kubectl version --client  # need v1.30.x

# 4. UDS CLI (bundles Zarf v0.77.0). The Linux release asset is a RAW binary,
#    NOT a .tar.gz — download it directly (do not pipe through tar).
UDS_VERSION="0.32.0"
curl -fSL "https://github.com/defenseunicorns/uds-cli/releases/download/v${UDS_VERSION}/uds-cli_v${UDS_VERSION}_Linux_amd64" \
  -o /usr/local/bin/uds
chmod +x /usr/local/bin/uds
uds version               # need 0.32.0

# 5. Python 3 (usually already installed)
python3 --version         # need ≥ 3.9

# 6. helm (for manifest lint)
mise use helm@3.16
helm version
```

### 1.3 inotify Limits (Linux only)

k3d with Istio sidecars requires high inotify limits. Set once (persists across reboots):

```bash
sudo sysctl fs.inotify.max_user_watches=1048576
sudo sysctl fs.inotify.max_user_instances=8192

# To persist across reboots:
echo "fs.inotify.max_user_watches=1048576" | sudo tee -a /etc/sysctl.conf
echo "fs.inotify.max_user_instances=8192"  | sudo tee -a /etc/sysctl.conf
```

### 1.4 Internet Access (Day-1 only)

The first `make demo-up` pulls ~8-10 GB of container images. Subsequent runs reuse Docker layer cache. For a fully air-gapped demo, see [Section 5: Air-Gap Mode](#5-air-gap-mode).

---

## 2. Step-by-Step: git clone → demo-up → 5 Flagships Green

### Step 1 — Clone the repository

```bash
git clone https://github.com/szl-holdings/szl-fleet-overlay.git
cd szl-fleet-overlay
```

### Step 2 — Run the preflight check

```bash
bash scripts/preflight.sh
```

**Expected output:**

```
=== SZL Demo Cluster — Preflight Check ===
1. Docker
  ✅  PASS  Docker daemon running — version 26.1.4
  ✅  PASS  Docker version ≥ 24.0
2. k3d
  ✅  PASS  k3d found — v5.8.3
  ✅  PASS  k3d version ≥ v5.8.x
3. kubectl
  ✅  PASS  kubectl found — v1.30.x
4. uds CLI
  ✅  PASS  uds CLI found — 0.32.0
5. Port availability (80, 443, 6550)
  ✅  PASS  Port 80 is free
  ✅  PASS  Port 443 is free
  ✅  PASS  Port 6550 is free
...
✅  PREFLIGHT PASSED — TOWER IS DEMO-READY
```

If any `⛔  FAIL` lines appear, fix them before proceeding. See [Section 4: Failure Modes](#4-failure-modes) below.

### Step 3 — Launch the demo cluster

```bash
make demo-up
```

This single command runs the full sequence:

| Phase | What it does | Typical duration |
|-------|-------------|-----------------|
| `preflight` | Runs scripts/preflight.sh | < 30 sec |
| `cluster-create` | Creates k3d cluster `szl-demo` | 1–2 min |
| `uds-init` | Deploys Zarf init package | 2–3 min |
| `uds-core-deploy` | Deploys UDS Core (Istio, Keycloak, MetalLB) | 5–8 min |
| `flagships-deploy` | Applies 5 Package CRs + Deployments | 2–3 min |
| `szl-mesh-deploy` | Applies peat mesh node configs | < 30 sec |
| `seed-receipts` | Generates 20 demo receipts | < 5 sec |
| **Total** | | **~10–20 min** |

### Step 4 — Confirm all 5 flagships are green

```bash
make demo-status
```

**Expected output:**

```
=== SZL Demo — Flagship Status ===

Cluster nodes:
  k3d-szl-demo-server-0   Ready    control-plane   8m

Package CR status:
  ✅  szl-a11oy     phase=Ready
  ✅  szl-sentra    phase=Ready
  ✅  szl-amaru     phase=Ready
  ✅  szl-rosie     phase=Ready
  ✅  szl-killinchu phase=Ready

Live HF Space health (internet fallback):
  ✅  a11oy.hf.space    HTTP 200
  ✅  sentra.hf.space   HTTP 200
  ✅  amaru.hf.space    HTTP 200
  ✅  rosie.hf.space    HTTP 200
  ✅  killinchu.hf.space HTTP 200

Receipt chain:
  Checksums: 8 files
  Signature: receipts/checksums.txt.sig present

Doctrine pin:
  v11 LOCKED 749/14/163 @ c7c0ba17 · Λ = Conjecture 1 · SLSA L1
```

### Step 5 — View the receipt chain

```bash
make demo-receipts
```

Shows the last 10 receipts from the local seed file + live audit logs from sentra and amaru.

### Step 6 (Post-demo) — Clean up

```bash
make demo-tear-down
```

---

## 3. The 3-Minute Demo Script

This is the script for the Warhacker live demo. Practice this verbatim before June 9.

---

### Opening (15 sec)

> "SZL Holdings is the only company shipping **per-decision cryptographic receipts** for agentic AI on the same open-source toolchain — Zarf, Pepr, UDS — that the DoD is standardizing on. Let me show you how it works."

---

### Beat 1 — Policy gate enforcement (60 sec)

> "First, the Λ-gate. Every agentic action runs through a policy evaluator. Here's a capital-class action — deploying to production — with confidence below the 0.95 threshold:"

```bash
curl -s -X POST https://szlholdings-a11oy.hf.space/api/a11oy/v1/policy/evaluate \
  -H "Content-Type: application/json" \
  -d '{"action":"deploy_to_production","confidence":0.89,"attested_witnesses":2,"severity":"capital"}' \
  | python3 -m json.tool
```

**Expected (pass the demo):**
```json
{
  "allow": false,
  "reason": "confidence_below_threshold",
  "threshold": 0.95,
  "required_witnesses": 3
}
```

> "Gate fires. Action denied. The receipt is written to the chain immediately."

```bash
curl -s https://szlholdings-a11oy.hf.space/api/a11oy/v1/ledger/verify | python3 -m json.tool
```

**Expected:**
```json
{"ok": true, "depth": 10, "broken_at": null}
```

> "Ten receipts in the chain. Each one SHA3-256 linked. Tamper-evident."

---

### Beat 2 — Immune system deny + audit (45 sec)

> "Now sentra's 8-gate immune system. Here's a prompt injection attempt:"

```bash
curl -s -X POST https://szlholdings-sentra.hf.space/api/sentra/v1/verdict \
  -H "Content-Type: application/json" \
  -d '{"action":"eval(malicious_code)","agent_id":"demo"}' \
  | python3 -m json.tool
```

**Expected:**
```json
{
  "decision": "DENY",
  "reason": "threat_signature_match",
  "gates_fired": ["dual_use_check", "injection_detection"],
  "receipt_hash": "..."
}
```

> "Denied. The receipt hash is the chain link. Now let's see the audit log:"

```bash
curl -s https://szlholdings-sentra.hf.space/api/sentra/v1/audit-log \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print(f\"Entries: {len(d.get('entries',d))}\")"
```

> "Every verdict is in the log. Deny-by-default. Eight gates. No exceptions."

---

### Beat 3 — Receipt chain verification (45 sec)

> "The receipt chain is doctrine-pinned: v11, 749 declarations, 14 axioms, 163 open sorries — we're honest about what's a theorem and what's a conjecture."

```bash
curl -s https://szlholdings-amaru.hf.space/api/health | python3 -m json.tool
```

**Expected:**
```json
{
  "status": "healthy",
  "doctrine": "v11",
  "declarations": 749,
  "axioms": 14,
  "sorries": 163,
  "lambda_status": "Conjecture 1"
}
```

> "Λ is Conjecture 1. Not a theorem — we're 70 lines of Lean away from closing it. That honest disclosure is itself the differentiator. Defense evaluators can verify this claim against our Zenodo DOI right now."

```bash
# Show the local receipt chain we seeded
make demo-receipts
```

> "20 receipts across 5 flagships, chained. This is the air-gap-compatible proof-of-governance that the DoD Agentic AI guidance requires."

---

### Close (15 sec)

> "Defense Unicorns signs packages. SZL signs decisions. That's the governance gap we fill — and it's the only commercial implementation of the DoD's April 2026 guidance. We're raising $2M seed extension at $8M pre-money to close the Lean conjecture and get to a paid DoD pilot."

---

## 4. Failure Modes and Recovery

### 4.1 Ports 80/443 Already In Use

**Symptom:** `make demo-up` fails at cluster-create; k3d errors mention port binding.

**Fix:**
```bash
# Find what's on port 80
sudo lsof -i :80
# Stop the conflicting service (e.g., nginx, apache)
sudo systemctl stop nginx
# Retry
make demo-up
```

**Alternative:** Use non-standard ports (for testing only, not for Warhacker demo):
```bash
k3d cluster create szl-demo -p "8080:80@server:*" -p "8443:443@server:*" ...
```

---

### 4.2 Docker Ulimit / inotify Exhaustion

**Symptom:** Pods crash with "too many open files" or "inotify: no space left on device".

**Fix:**
```bash
sudo sysctl fs.inotify.max_user_watches=1048576
sudo sysctl fs.inotify.max_user_instances=8192
# Then tear down and restart:
make demo-tear-down
make demo-up
```

---

### 4.3 Image Pull Failures (Rate Limiting / Network)

**Symptom:** `kubectl get pods` shows `ImagePullBackOff` or `ErrImagePull`.

**Diagnosis:**
```bash
export KUBECONFIG=/tmp/szl-demo-kubeconfig.yaml
kubectl describe pod -n szl-a11oy -l app=szl-a11oy | grep -A5 Events
```

**Fix options:**
1. Log in to GHCR: `echo $GITHUB_TOKEN | docker login ghcr.io -u szl-holdings --password-stdin`
2. Wait for rate limit to clear (1 hour)
3. Pre-pull images: `docker pull ghcr.io/szl-holdings/a11oy:uds-v0.2.0`
4. For air-gap: see Section 5

---

### 4.4 HF Space Cold Start (HTTP 503 / 500)

**Symptom:** `make demo-status` shows HF Space health = ERR or HTTP 503.

**Context:** HF Spaces free tier "sleeps" after 30 minutes of no traffic. Cold start takes 30–90 seconds.

**Fix:**
```bash
# Wake all 5 spaces (hit them once each):
for app in a11oy sentra amaru rosie killinchu; do
  curl -sf https://szlholdings-$app.hf.space/api/health -o /dev/null && echo "$app awake" || echo "$app sleeping..."
done
# Wait 90 seconds, retry
sleep 90
make demo-status
```

**Prevention:** Hit the spaces 5 minutes before the demo to ensure they're warm.

---

### 4.5 UDS Core Deploy Timeout

**Symptom:** `uds-core-deploy` step times out waiting for Keycloak to be ready.

**Context:** UDS Core installs Istio, Keycloak, MetalLB. On slow machines this can take 12+ minutes.

**Fix:**
```bash
export KUBECONFIG=/tmp/szl-demo-kubeconfig.yaml
# Check what's stuck
kubectl get pods -A | grep -v Running | grep -v Completed
# Check events
kubectl get events -A --sort-by=.lastTimestamp | tail -20
# Manually wait for all pods
kubectl wait --for=condition=Ready pods --all -A --timeout=600s
```

If Keycloak specifically is stuck:
```bash
kubectl rollout restart deployment/keycloak -n keycloak
```

---

### 4.6 Package CR Not Reaching Ready Phase

**Symptom:** `make demo-status` shows `szl-a11oy phase=Pending` or `NotFound`.

**Context:** The UDS Operator (part of UDS Core) must be running before Package CRs can be processed.

**Fix:**
```bash
export KUBECONFIG=/tmp/szl-demo-kubeconfig.yaml
# Check UDS Operator
kubectl get pods -n uds-system
# If UDS Operator is not running, UDS Core may not have fully deployed
kubectl logs -n uds-system -l app=uds-operator --tail=50
# Re-apply packages
kubectl apply -f configs/packages/
```

---

### 4.7 Cluster Already Exists

**Symptom:** `cluster-create` says cluster already exists and errors out.

**Fix:**
```bash
make demo-tear-down
make demo-up
```

---

### 4.8 DSSE Signatures are PLACEHOLDER

**Context:** The `receipts/checksums.txt.sig` is a PLACEHOLDER when `COSIGN_KEY_PATH` is not set. This is documented in `HONEST_DISCLOSURE.md` and `DSSE_FIX_PLAN.md`.

**What it means for the demo:** The receipt chain structure is correct and chain-linked. The cryptographic signature is not verifiable against Rekor/Sigstore without the key.

**Honest disclosure to evaluators (use this verbatim):**
> "The receipt envelope structure is correct DSSE. The signature value is a PLACEHOLDER — inject the ECDSA-P256 key and it will produce verifiable Sigstore attestations. DSSE_FIX_PLAN.md has the exact implementation path."

---

## 5. Air-Gap Mode

For demos with no internet (e.g., classified environment, conference network):

### 5.1 Pre-pull all required images (do this at home with internet)

```bash
# Pull and save k3s image
docker pull ghcr.io/defenseunicorns/uds-k3d/k3s:v1.35.4-k3s1
docker save ghcr.io/defenseunicorns/uds-k3d/k3s:v1.35.4-k3s1 > /media/usb/k3s-image.tar

# Pull and save UDS Core images (large - ~4GB)
# uds-core packs its images into the Zarf package
uds zarf package pull oci://ghcr.io/defenseunicorns/packages/uds/core:0.42.0-upstream-amd64
# Copy the resulting .tar.zst to USB

# Pull and save flagship images
for app in a11oy sentra amaru rosie killinchu; do
  docker pull ghcr.io/szl-holdings/${app}:uds-v0.2.0
  docker save ghcr.io/szl-holdings/${app}:uds-v0.2.0 > /media/usb/${app}-image.tar
done
```

### 5.2 Air-gap deploy

```bash
# Load images from USB
docker load < /media/usb/k3s-image.tar
for app in a11oy sentra amaru rosie killinchu; do
  docker load < /media/usb/${app}-image.tar
done

# Create cluster (k3s image already in Docker cache — no pull needed)
make cluster-create

# Deploy from local .tar.zst files
uds zarf init --confirm
uds deploy /path/to/uds-core-0.42.0-upstream-amd64.tar.zst --confirm

# Deploy flagships (images already loaded, k3d will find them)
make flagships-deploy szl-mesh-deploy seed-receipts
```

---

## 6. Doctrine and Honesty Disclosures

The following items **must be disclosed proactively** at the demo. This is not weakness — it is the SZL differentiator (honest governance).

| Item | Honest Statement |
|------|-----------------|
| Λ is Conjecture 1 | "Λ is Conjecture 1, not a proven theorem. We have 163 open sorries. The completion path is ~70 lines of Lean. We will NOT claim machine-verification until Lean CI is green." |
| DSSE signatures | "DSSE signatures are PLACEHOLDER when cosign key is not injected. Envelope structure is correct. Key injection is the remaining step per DSSE_FIX_PLAN.md." |
| SLSA level | "SLSA L1 honest. NOT higher levels (higher levels not yet achieved — deferred)." |
| Section 889 | "5 vendors explicitly excluded: Huawei, ZTE, Hytera, Hikvision, Dahua. Exact count — no vague statements." |
| No Iron Bank | "We make zero Iron Bank claims. No FedRAMP ATO. CMMC self-assessment only (not C3PAO certified)." |

---

## 7. Quick Reference Commands

```bash
# Full lifecycle
make demo-up           # spin up everything
make demo-status       # check all flagships
make demo-receipts     # view receipt chain
make demo-tear-down    # clean up

# Cluster-only operations
export KUBECONFIG=/tmp/szl-demo-kubeconfig.yaml
kubectl get nodes
kubectl get pods -A
kubectl get packages -A

# Wake HF Spaces
for app in a11oy sentra amaru rosie killinchu; do
  curl -sf https://szlholdings-$app.hf.space/api/health -o /dev/null && echo "$app: awake"
done

# Quick receipt check
curl -s https://szlholdings-amaru.hf.space/api/health | python3 -m json.tool

# Sentra verdict
curl -s -X POST https://szlholdings-sentra.hf.space/api/sentra/v1/verdict \
  -H "Content-Type: application/json" \
  -d '{"action":"test","agent_id":"demo"}' | python3 -m json.tool

# Regenerate receipts
python3 scripts/seed-receipts.py
```

---

*WARHACKER_DEMO_RUNBOOK.md v1.0.0*  
*Doctrine v11 LOCKED 749/14/163 @ c7c0ba17 · Λ = Conjecture 1 · SLSA L1*  
*Signed-off-by: Yachay <yachay@szlholdings.ai>*  
*Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>*
