# Sentra — Deploy Guide

**Doctrine v11 LOCKED** · 749/14/163 @ c7c0ba17  
**SLSA L1 honest** (cosign-signed GitHub Actions image; L2 build-provenance attestation roadmap via Wire D — not yet earned) · Λ = Conjecture 1 (NOT a theorem)  
**No FedRAMP / Iron Bank / CMMC** — not pursued.

---

## 1. Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| `zarf` | ≥ 0.32.0 | Package build + deploy |
| `uds-cli` | ≥ 0.10.0 | Bundle deploy (full mesh) |
| `cosign` | ≥ 2.0 | SLSA L1 signature verify (`cosign verify`) |
| Docker / Podman | any | Local image build |
| `kubectl` | ≥ 1.28 | Cluster management |

---

## 2. SLSA L1 Verify (before deploy)

```bash
# L1 (earned today): verify the cosign keyless signature on the image
cosign verify \
  --certificate-identity-regexp '^https://github.com/szl-holdings/' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  ghcr.io/szl-holdings/sentra:uds-v0.2.0
```

Expected: `Verified OK` — cosign claims validated, Rekor inclusion verified.

```bash
# L2 (roadmap via Wire D — NOT yet earned): once an attestation is pushed, this
# returns the SLSA provenance. Today it returns "no matching attestations".
cosign verify-attestation \
  --type slsaprovenance \
  --certificate-identity-regexp '^https://github.com/szl-holdings/' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  ghcr.io/szl-holdings/sentra:uds-v0.2.0
```

**Honest ceiling:** SLSA L1 (cosign-signed image, verifiable via `cosign verify`). L2 (attested build-service provenance) is roadmap via Wire D — NOT yet earned. L3 (hardened builder with separate build service) is roadmap, NOT claimed.

---

## 3. Standalone Zarf Package

### Build

```bash
zarf package create deploy/ --confirm
# → zarf-package-sentra-amd64-uds-v0.2.0.tar.zst
```

### Deploy

```bash
zarf package deploy zarf-package-sentra-amd64-uds-v0.2.0.tar.zst --confirm
```

### Verify

```bash
kubectl get pods -n sentra
kubectl logs -n sentra deploy/sentra | head -50
curl http://localhost:7860/api/sentra/healthz
# → {"status":"ok","organ":"sentra","doctrine":"v11","lock":"749/14/163"}
```

---

## 4. Full SZL Mesh Bundle (recommended for Warhacker demo)

The sentra package is composed into the `szl-mesh-v0.4.0` bundle alongside a11oy, amaru, rosie, killinchu.

```bash
# Deploy the full mesh bundle
uds-cli bundle deploy szl-mesh-v0.4.0.tar.zst --confirm

# Or from GHCR (OCI)
uds-cli bundle deploy oci://ghcr.io/szl-holdings/szl-uds-bundle:0.4.0 --confirm
```

The mesh invariant: `receipts.in ≡ receipts.out` — audit-fiber continuity. Every sentra verdict emits a DSSE-signed receipt that propagates through the mesh.

---

## 5. UDS Package Reference

| Field | Value |
|-------|-------|
| Image | `ghcr.io/szl-holdings/sentra:uds-v0.2.0` |
| Namespace | `sentra` |
| Service port | `7860` |
| Healthz | `GET /api/sentra/healthz` |
| Wire B | `POST /api/sentra/v1/verdict` |
| Docs | `GET /api/sentra/docs` |
| UDS Package CR | `deploy/uds-package.yaml` |
| Zarf manifest | `deploy/zarf.yaml` |

---

## 6. Environment Variables

| Var | Required | Purpose |
|-----|----------|---------|
| `SZL_SENTRA_ED25519_SEED` | Optional | Persistent Ed25519 DSSE key. If absent, ephemeral key generated at startup (receipts real but key rotates on restart). |
| `SZL_COSIGN_PRIVATE_PEM` | Optional | Cosign private key for receipt re-signing (SLSA L1). |
| `SZL_LLM_API_KEY` | Optional | Wire LLM API calls through the 5-tier router. If absent, honest stub is returned with real tier selection. |
| `HF_TOKEN` | HF Space | Required for HuggingFace Space deployment. CTO holds this. |

---

## 7. HuggingFace Space Sync

The CTO must sync the following files to rebuild the HF Space (`SZLHOLDINGS/sentra`):

| File | Change | Critical |
|------|--------|---------|
| `sentra_elite.py` | **NEW** — 13-tab backend (12 real endpoints) | Yes |
| `serve.py` | **MODIFIED** — elite registration block appended | Yes |
| `Dockerfile` | **MODIFIED** — COPY sentra_elite.py + console/ | Yes |
| `console/index.html` | **MODIFIED** — 13-tab elite UI (894 lines) | Yes |
| `deploy/zarf.yaml` | **MODIFIED** — SLSA L1 honest, DEPLOY.md ref | No |
| `DEPLOY.md` | **NEW** — this file | No |

```bash
# Push to HF Space (requires SZLHOLDINGS org token)
cd sentra
git remote add hf https://SZLHOLDINGS:${HF_WRITE_TOKEN}@huggingface.co/spaces/SZLHOLDINGS/sentra
git push hf main
```

---

## 8. Post-Deploy Verification

```bash
BASE=https://szlholdings-sentra.hf.space/api/sentra/v1

# Existing endpoints (should be live already)
curl $BASE/gates
curl $BASE/audit-log
curl -X POST $BASE/verdict -H "Content-Type: application/json" \
  -d '{"agent":"test","action":"read_config","severity":"low","confidence":0.9,"witnesses":[{"id":"w1","attested":true}]}'

# New elite endpoints
curl $BASE/verdict/feed
curl $BASE/elite/mesh-crosscut
curl $BASE/elite/gate-slo
curl $BASE/elite/threat-ingest
curl $BASE/elite/compliance
curl $BASE/llm/hub
curl $BASE/puriq/formulas
curl $BASE/anatomy
curl $BASE/slsa/verify

# LLM route
curl -X POST $BASE/llm/route/elite \
  -H "Content-Type: application/json" \
  -d '{"prompt":"evaluate immune gate","max_tier":4,"task_hint":"immune"}'

# Compliance export
curl -X POST $BASE/elite/compliance \
  -H "Content-Type: application/json" \
  -d '{"framework":"eu-ai-act"}'

# Threat ingest
curl -X POST $BASE/elite/threat-ingest \
  -H "Content-Type: application/json" \
  -d '{"indicators":[{"type":"indicator","name":"test-sig","pattern":"[test:pattern = true]"}],"source":"curl-test"}'
```

All should return HTTP 200 with `doctrine: "v11"` and `schema: "szl.sentra.*"`.

---

## 9. Honest Disclosures

- **SLSA L1 honest**: cosign-signed GitHub Actions image. L2 build-provenance attestation roadmap via Wire D (not yet earned). L3 (hardened builder) is roadmap.
- **Λ = Conjecture 1**: NOT a closed theorem. Open CAUCHY_ND sorry at `Uniqueness.lean:120`.
- **PROVED** = {F1, F11, F12, F18, F19}. F23 = Conjecture 1. All others: Roadmap.
- **Audit log**: In-memory ring (maxlen=200). Resets on Space restart.
- **DSSE signing**: Real Ed25519. Key is ephemeral if `SZL_SENTRA_ED25519_SEED` not set.
- **LLM responses**: Honest stub until `SZL_LLM_API_KEY` wired. Tier selection is real math.
- **No FedRAMP / Iron Bank / CMMC**: Not pursued.

---

*Doctrine v11 LOCKED — HONESTY OVER CHECKLIST.*  
*Signed-off-by: stephenlutar2-hash <stephenlutar2@gmail.com>*
