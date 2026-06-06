# SZL Vessels Demo — Deployment Operator Guide

**szl-uds-deployment** · Warhacker 2026 · Built with Zarf v0.77.0 + UDS + keyless Sigstore signing

---

## Prerequisites

| Tool | Minimum version | Install |
|---|---|---|
| Docker | 24.0 | https://docs.docker.com/engine/install/ |
| k3d | 5.6.0 | `brew install k3d` or https://k3d.io/v5.6.0/#installation |
| zarf | 0.77.0 | https://github.com/zarf-dev/zarf/releases/tag/v0.77.0 |
| kubectl | 1.29 | https://kubernetes.io/docs/tasks/tools/ |
| helm | 3.14 | https://helm.sh/docs/intro/install/ |
| cosign | 2.4.3 | `brew install cosign` or https://docs.sigstore.dev/system_config/installation/ |
| jq | 1.7 | `brew install jq` |
| curl | 7.88 | pre-installed on most systems |

Verify all tools are present:

```bash
for tool in docker k3d zarf kubectl helm cosign jq curl; do
  command -v "$tool" && $tool version 2>/dev/null | head -1 || echo "MISSING: $tool"
done
```

**Disk space**: ~4 GB free (Docker images + Zarf package cache)  
**RAM**: 8 GB minimum; 16 GB recommended for stable k3d operation  
**Network**: Required for first run (image pulls); subsequent runs use the Zarf internal registry  

---

## Single Command

```bash
make demo
```

This runs `demo/warhacker_demo.sh`, which executes all 7 steps end-to-end.

If `make` is unavailable:

```bash
chmod +x demo/warhacker_demo.sh
./demo/warhacker_demo.sh
```

Expected runtime: **45–60 seconds** with a warm Docker image cache.  
First run (cold): add 5–10 minutes for image pulls.

---

## Manual Step-by-Step

### Step 1 — Create k3d cluster

```bash
k3d cluster create szl-demo \
  --k3s-arg "--disable=traefik@server:0" \
  --port "8080:80@loadbalancer" \
  --wait \
  --timeout 120s

k3d kubeconfig merge szl-demo --kubeconfig-merge-default
kubectl config use-context k3d-szl-demo
```

### Step 2 — Zarf init (signed)

```bash
# Download Zarf init package
curl -fsSL https://github.com/zarf-dev/zarf/releases/download/v0.77.0/zarf-init-amd64-v0.77.0.tar.zst \
  -o zarf-init-amd64-v0.77.0.tar.zst

# Verify the init package signature (Zarf 0.77 keyless)
zarf package verify zarf-init-amd64-v0.77.0.tar.zst \
  --certificate-identity "https://github.com/zarf-dev/zarf/.github/workflows/release.yml@refs/tags/v0.77.0" \
  --certificate-oidc-issuer "https://token.actions.githubusercontent.com"

# Initialize
zarf init --components=git-server --confirm --no-progress \
  init-package zarf-init-amd64-v0.77.0.tar.zst
```

### Step 3 — Deploy vessels demo package

```bash
# Verify package signature (keyless cosign)
cosign verify-blob \
  --bundle zarf-package-szl-vessels-demo-amd64-0.3.1.tar.zst.cosign.bundle \
  --certificate-identity "https://github.com/szl-holdings/vessels/.github/workflows/uds-package-release.yml@refs/tags/v0.3.1" \
  --certificate-oidc-issuer "https://token.actions.githubusercontent.com" \
  zarf-package-szl-vessels-demo-amd64-0.3.1.tar.zst

# Deploy
zarf package deploy zarf-package-szl-vessels-demo-amd64-0.3.1.tar.zst \
  --confirm --no-progress --set DOMAIN=localhost
```

### Step 4 — Port-forward

```bash
kubectl rollout status deployment/vessels-web -n szl-vessels --timeout=120s
kubectl port-forward -n szl-vessels svc/vessels-web 8080:80 &
```

### Step 5 — Query the API

```bash
curl -s localhost:8080/api/check?imo=9999001 | jq '.'
```

Expected response structure:

```json
{
  "imo": "9999001",
  "sanctions_hit": false,
  "dark_vessel": false,
  "receipt": {
    "receipt_id": "<sha256>",
    "envelope": {
      "payload": "<base64>",
      "payloadType": "application/vnd.szl.receipt.v1+json",
      "signatures": [{ "keyid": "szl-vessels-demo-hmac-sha256-2026", "sig": "<base64>" }]
    },
    "sig_placeholder": "cosign verify-blob --bundle ..."
  }
}
```

### Step 6 — Verify receipt

```bash
# Check Kubernetes annotation on the Deployment
kubectl get deploy vessels-web -n szl-vessels \
  -o jsonpath='{.metadata.annotations}' | jq '.'

# Verify the Zarf package itself (the canonical supply-chain check)
zarf package verify zarf-package-szl-vessels-demo-amd64-0.3.1.tar.zst \
  --certificate-identity "https://github.com/szl-holdings/vessels/.github/workflows/uds-package-release.yml@refs/tags/v0.3.1" \
  --certificate-oidc-issuer "https://token.actions.githubusercontent.com"
```

### Step 7 — Cleanup

```bash
# Stop port-forward
kill %1 2>/dev/null || true
# Destroy cluster
k3d cluster delete szl-demo
```

---

## Verification

### Package signature (cosign keyless)

```bash
cosign verify-blob \
  --bundle <package>.cosign.bundle \
  --certificate-identity "https://github.com/szl-holdings/vessels/.github/workflows/uds-package-release.yml@refs/tags/v0.3.1" \
  --certificate-oidc-issuer "https://token.actions.githubusercontent.com" \
  <package>.tar.zst
```

Output on success: `Verified OK`

### SBOM attestation

```bash
cosign verify-blob-attestation \
  --bundle <package>.sbom.bundle \
  --certificate-identity "https://github.com/szl-holdings/vessels/.github/workflows/uds-package-release.yml@refs/tags/v0.3.1" \
  --certificate-oidc-issuer "https://token.actions.githubusercontent.com" \
  --type spdxjson \
  <package>.tar.zst
```

Output: SPDX JSON printed to stdout. Verify `spdxVersion` is `SPDX-2.3`.

### Zarf native verify (0.77.0+)

```bash
zarf package verify <package>.tar.zst \
  --certificate-identity "https://github.com/szl-holdings/vessels/.github/workflows/uds-package-release.yml@refs/tags/v0.3.1" \
  --certificate-oidc-issuer "https://token.actions.githubusercontent.com"
```

### Governance receipts in Kubernetes

```bash
# All resources annotated by Pepr governance-receipts controller
kubectl get deploy,job -A \
  -o json | jq '
    .items[]
    | select(.metadata.annotations["szl.receipt.id"] != null)
    | { resource: "\(.metadata.namespace)/\(.kind)/\(.metadata.name)",
        receipt_id: .metadata.annotations["szl.receipt.id"][0:16],
        ts: .metadata.annotations["szl.receipt.ts"] }'
```

---

## Troubleshooting

### Error 1: `zarf package verify` returns "certificate not found in Rekor"

**Cause**: The Rekor transparency log entry has not replicated yet, or the bundle was not downloaded with the package.

**Remediation**:
```bash
# Use the cosign bundle file instead of Rekor lookup
cosign verify-blob \
  --bundle <package>.cosign.bundle \
  --certificate-identity <cert-identity> \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  <package>.tar.zst
```

### Error 2: `k3d cluster create` fails with "port already in use"

**Cause**: Port 8080 (or 80/443) is bound by another process.

**Remediation**:
```bash
# Check what is using port 8080
lsof -i :8080
# Use a different local port
PORT_FWD_PORT=9090 ./demo/warhacker_demo.sh
```

### Error 3: `zarf init` times out waiting for registry

**Cause**: Docker is rate-limiting image pulls, or the internal registry pod is crash-looping.

**Remediation**:
```bash
# Check registry pod status
kubectl get pods -n zarf
kubectl describe pod -n zarf -l app=zarf-docker-registry

# Retry with increased timeout
zarf init --timeout 300s --confirm
```

### Error 4: `kubectl port-forward` exits immediately

**Cause**: The vessels-web pod is not yet running (Deployment rollout incomplete, or image pull failed).

**Remediation**:
```bash
# Check pod status
kubectl get pods -n szl-vessels
kubectl describe pod -n szl-vessels -l app.kubernetes.io/name=vessels-web

# Check events for image pull errors
kubectl get events -n szl-vessels --sort-by='.lastTimestamp' | tail -20

# Wait explicitly
kubectl rollout status deployment/vessels-web -n szl-vessels --timeout=180s
```

### Error 5: `cosign verify-blob` fails with "CERTIFICATE_VERIFY_FAILED"

**Cause**: The certificate identity or OIDC issuer string does not exactly match what was recorded during signing.

**Remediation**:
```bash
# Inspect the bundle to see the recorded identity
cat <package>.cosign.bundle | jq '.cert' | base64 -d | openssl x509 -noout -text \
  | grep -A2 "Subject Alternative Name"

# The SubjectAltName URI must match --certificate-identity exactly.
# Recheck the workflow file path and tag in the cert (look for the URI SAN).
```

If the identity does not match, the package was signed by a different workflow run.
Open an issue at https://github.com/szl-holdings/vessels/issues with the bundle output.

---

## Key file locations

| File | Purpose |
|---|---|
| `uds/zarf.yaml` | Zarf v0.77.0 package manifest |
| `uds/values.yaml` | Aggregate Helm values |
| `uds/charts/vessels/` | Helm chart for vessels-web |
| `uds/pepr/governance-receipts.ts` | Pepr admission controller |
| `demo/warhacker_demo.sh` | End-to-end demo script |
| `.github/workflows/uds-package-release.yml` | CI: build + sign + publish |

---

## References

- [Zarf v0.77.0 release notes](https://github.com/zarf-dev/zarf/releases/tag/v0.77.0) — keyless signing introduction
- [Sigstore keyless signing](https://docs.sigstore.dev/cosign/signing/keyless/)
- [Defense Unicorns UDS Core](https://github.com/defenseunicorns/uds-core)
- [Pepr admission controller framework](https://docs.pepr.dev)
- [DSSE envelope spec](https://github.com/secure-systems-lab/dsse)
- [vsp-otel OTLP exporter](https://github.com/szl-holdings/vsp-otel)
- [szl-uds-deployment architecture](https://github.com/szl-holdings/szl-uds-deployment/blob/main/docs/ARCHITECTURE.md)

---

*Defense Unicorns, Pepr, and UDS are trademarks of Defense Unicorns Inc. This project is an independent add-on and is not affiliated with or endorsed by Defense Unicorns.*
