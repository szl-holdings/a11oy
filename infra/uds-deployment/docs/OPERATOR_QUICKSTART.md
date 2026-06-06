# SZL UDS Deployment — Operator Quickstart

**Stack:** k3d + uds-cli + uds-core slim-dev + szl-receipts Pepr policy
**Target operator:** SZL engineering, DU partner technical staff, Warhacker demo runner
**Time to running cluster:** ~5 minutes from zero
**Doctrine:** v6 (strict) — all commands verified, no fake capability claims

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [5-Minute Setup](#5-minute-setup)
3. [Port-Forward and Verify Receipts](#port-forward-and-verify-receipts)
4. [Air-Gap Option: USB Stick Deployment](#air-gap-option-usb-stick-deployment)
5. [Troubleshooting (Top 10 Errors)](#troubleshooting-top-10-errors)
6. [Doctrine v6 Compliance Verification](#doctrine-v6-compliance-verification)

---

## Prerequisites

### Required tools

```bash
# Check versions — minimum required versions listed
k3d version          # >= 5.6.0
uds version          # >= 0.15.0 (Defense Unicorns uds-cli)
kubectl version      # >= 1.28
zarf version         # >= 0.39.0
docker version       # >= 24.0 (or podman 4.x)
```

### Install if missing

```bash
# k3d
curl -s https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash

# uds-cli (Defense Unicorns)
brew install defenseunicorns/tap/uds
# OR
curl -Lo uds https://github.com/defenseunicorns/uds-cli/releases/latest/download/uds-linux-amd64
chmod +x uds && sudo mv uds /usr/local/bin/

# zarf
brew install defenseunicorns/tap/zarf
# OR
curl -Lo zarf https://github.com/defenseunicorns/zarf/releases/latest/download/zarf-linux-amd64
chmod +x zarf && sudo mv zarf /usr/local/bin/
```

### System requirements

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| RAM | 4 GB free | 8 GB free |
| CPU | 2 cores | 4 cores |
| Disk | 10 GB free | 20 GB free |
| OS | Linux / macOS | Linux amd64 |

---

## 5-Minute Setup

### Step 1: Clone the repo

```bash
git clone https://github.com/szl-holdings/szl-uds-deployment.git
cd szl-uds-deployment
```

### Step 2: Start the full stack

```bash
uds run demo:start
```

This single command:
1. Creates a `k3d` cluster named `uds-szl-demo`
2. Deploys `uds-k3d-dev` (k3d-compatible UDS dev environment)
3. Deploys `uds-core` slim-dev (Istio, Pepr, monitoring)
4. Deploys `szl-receipts` Zarf package (SZL governance receipt server + Pepr policy webhook)

Expected output (≈90 seconds):

```
✓ Creating k3d cluster: uds-szl-demo
✓ Deploying uds-k3d-dev...
✓ Deploying uds-core slim-dev...
✓ Deploying szl-receipts...
✓ Demo stack ready — receipts at http://localhost:8443
```

### Step 3: Verify cluster health

```bash
k3d cluster list
# Expected: uds-szl-demo   1/1   1/1   running

kubectl get pods -n szl-receipts
# Expected: szl-receipts-* pods in Running state

kubectl get pods -n pepr-system
# Expected: pepr-* pods Running (Pepr policy webhook)
```

### Step 4: Trigger a demo workload

```bash
uds run demo:workload
# OR
kubectl apply -f scripts/demo_workload.yaml
```

### Step 5: Stop when done

```bash
uds run demo:stop
# OR
k3d cluster delete uds-szl-demo
```

---

## Port-Forward and Verify Receipts

### Open the receipt dashboard

```bash
kubectl port-forward svc/szl-receipts-server 8443:8443 -n szl-receipts &
```

### Health check

```bash
curl -s http://localhost:8443/health | python3 -m json.tool
# Expected: {"status": "ok", "version": "0.3.x"}
```

### Check receipt count

```bash
curl -s http://localhost:8443/receipts | python3 -c "
import sys, json
r = json.load(sys.stdin)
print(f'{len(r)} receipts in feed')
"
# Before demo:workload: 0 receipts
# After demo:workload: 1+ receipts
```

### Inspect a receipt (DSSE envelope)

```bash
curl -s http://localhost:8443/receipts | python3 -c "
import sys, json, base64
receipts = json.load(sys.stdin)
if receipts:
    r = receipts[0]
    print('payload type:', r.get('payloadType'))
    payload = json.loads(base64.b64decode(r.get('payload', '')))
    print('subject:', payload.get('subject', {}).get('name'))
    print('sha256:', payload.get('subject', {}).get('digest', {}).get('sha256', '')[:16] + '...')
else:
    print('No receipts yet — run: uds run demo:workload')
"
```

### Verify receipt HMAC (demo mode)

```bash
# The receipt server in demo mode uses HMAC-SHA256
# Production mode uses Ed25519 (requires cosign keys — pending FA-001)
curl -s http://localhost:8443/receipts | python3 -c "
import sys, json
receipts = json.load(sys.stdin)
for r in receipts:
    sigs = r.get('signatures', [])
    print(f'Receipt: {r.get(\"payloadType\",\"?\")} | sigs: {len(sigs)} | keyid: {sigs[0][\"keyid\"] if sigs else \"none\"}')
"
```

---

## Air-Gap Option: USB Stick Deployment

For disconnected environments (e.g., classified networks, ship-board):

### 1. Pre-pull all images (connected machine)

```bash
# On an internet-connected machine:
cd szl-uds-deployment
uds run air-gap:bundle
# Creates: dist/szl-full-stack-bundle-0.3.1.tar.zst (~500 MB)
```

### 2. Copy to USB

```bash
cp dist/szl-full-stack-bundle-0.3.1.tar.zst /media/usb/
cp dist/szl-full-stack-bundle-0.3.1.tar.zst.sha256 /media/usb/
```

### 3. Deploy on air-gapped machine

```bash
# On the air-gapped machine (USB mounted at /media/usb):
cd /media/usb

# Verify integrity
sha256sum -c szl-full-stack-bundle-0.3.1.tar.zst.sha256

# Deploy (no internet required)
uds deploy szl-full-stack-bundle-0.3.1.tar.zst --confirm
```

**Note:** Air-gap bundle packaging is contingent on `zarf package create` completing for all component packages. As of v0.3.0, only `szl-receipts` is Zarf-packaged. Full air-gap support is **[STAGED: awaiting Zarf packages for a11oy, sentra, amaru, rosie per FA-001]**.

---

## Troubleshooting (Top 10 Errors)

### Error 1: `k3d cluster create` fails — "address already in use"

```bash
# Port conflict — check what's using the port
lsof -i :6550
# Kill or remap:
k3d cluster create uds-szl-demo --api-port 6551
```

### Error 2: `ImagePullBackOff` for szl-receipts pods

```bash
kubectl describe pod -n szl-receipts <pod-name>
# If "unauthorized" → container not yet in GHCR
# Status: awaiting FA-001 push of ghcr.io/szl-holdings/vessels:uds-v0.3.1
# Workaround: use local image via zarf
zarf package create . --set IMAGE_TAG=uds-v0.3.1
```

### Error 3: `pepr-* pods` CrashLoopBackOff

```bash
kubectl logs -n pepr-system deploy/pepr-szl-receipts --previous
# Usually: webhook certificate not yet issued
# Fix: wait 30 seconds, then:
kubectl rollout restart deploy/pepr-szl-receipts -n pepr-system
```

### Error 4: `http://localhost:8443/health` — connection refused

```bash
# Port-forward not running
kubectl port-forward svc/szl-receipts-server 8443:8443 -n szl-receipts &
# Verify pod is Running first:
kubectl get pods -n szl-receipts
```

### Error 5: `uds run demo:start` — "tasks.yaml not found"

```bash
# Run from repo root
pwd  # Must be szl-uds-deployment/
ls tasks.yaml  # Must exist
```

### Error 6: `zarf package create` fails — "registry not found"

```bash
# Registry needs to be reachable within k3d
kubectl get svc -n zarf
# If no zarf registry, initialize:
uds run zarf:init
```

### Error 7: "No space left on device" during bundle deploy

```bash
df -h
# Free space or use --tmpdir flag:
uds deploy bundle.tar.zst --tmpdir /data/tmp
```

### Error 8: `cosign verify-blob` fails — "no signature found"

```bash
# Expected behavior for v0.3.0 — signed assets not yet attached (FA-001 pending)
# Verify sha256 instead (available now):
sha256sum <tarball>
# Use the sha256 from the HF mirror metadata
```

### Error 9: `kubectl get pods` — "unable to connect to the server"

```bash
# kubeconfig context not set
kubectl config get-contexts
k3d kubeconfig merge uds-szl-demo --kubeconfig-merge-default
kubectl config use-context k3d-uds-szl-demo
```

### Error 10: Receipt feed empty after `demo:workload`

```bash
# Check Pepr webhook is registered
kubectl get mutatingwebhookconfigurations | grep szl
# Check webhook is receiving events
kubectl logs -n pepr-system deploy/pepr-szl-receipts | tail -20
# Manually trigger a watched resource type:
kubectl run test-workload --image=nginx --restart=Never -n default
curl -s http://localhost:8443/receipts | python3 -c "import sys,json; print(len(json.load(sys.stdin)), 'receipts')"
```

---

## Doctrine v6 Compliance Verification

Run this grep to check any file for banned superlatives or false capability claims:

```bash
# Doctrine v6 banned patterns
grep -rn \
  -e "fully compliant" \
  -e "production-ready" \
  -e "enterprise-grade" \
  -e "catalog accepted" \
  -e "officially endorsed" \
  -e "Defense Unicorns product" \
  -e "trademark cleared" \
  -e "SBOM attached" \
  -e "signed assets available" \
  docs/ bundles/ charts/ catalog-submission/ 2>/dev/null

# Expected output: 0 matches
# Any match = doctrine violation requiring patch
```

### Honest capability matrix (as of 2026-05-29)

| Capability | Status |
|-----------|--------|
| Live k3d cluster deployment | ✓ Available |
| Pepr policy webhook receipts | ✓ Available |
| DSSE receipt envelopes (HMAC) | ✓ Available |
| SBOM (via `sbom.yml` CI) | ✓ Available |
| sha256-verified source tarballs on HF | ✓ Available |
| Cosign-signed binary assets on GH | [STAGED: awaiting FA-001] |
| Ed25519 production receipt signing | [STAGED: awaiting FA-001] |
| Container at ghcr.io | [STAGED: awaiting FA-001] |
| Full Zarf package (all components) | [STAGED: awaiting container push] |
| UDS Catalog acceptance | [STAGED: awaiting AG sponsor + container + cosign] |
| BFT multi-signer quorum | [STAGED: architecture pending] |

---

*Generated: 2026-05-29 | szl-uds-deployment docs/OPERATOR_QUICKSTART.md | Doctrine v6 strict*
