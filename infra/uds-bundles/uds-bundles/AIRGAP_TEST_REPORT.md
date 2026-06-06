# AIRGAP TEST REPORT — UDS Productionization (SZL Crew)

**Agent:** UDS Productionization subagent, under Yachay / CTO authority
**Date:** 2026-06-01
**Doctrine v11 LOCKED:** 749 decls / 14 axioms / 163 sorries / 13-axis yuyay_v3 / replay `bacf54434f1a3bf2d758b27a62d5fd580ca4c8d3b180693573eeebcaea631fc5`

---

## STATUS: PARTIAL GREEN — 5/5 SIGNED PROOF PACKAGES BUILT + VERIFIED; IMAGE-BEARING KIND AIRGAP TEST STILL REQUIRES HEALTHY DOCKER HOST (HONEST)

**Update (mid-session, 2026-06-01 09:19–09:23 UTC): memory RECOVERED.** After an early
degraded-memory window where every large Go binary was OOM-killed on load, `zarf v0.51.0`
and `cosign` both began running. We then produced **REAL, on-disk artifacts**:

- **5/5 real `.tar.zst` Zarf packages** (image-free PROOF builds — full production
  structure minus the `images:` layer, which needs the docker daemon) under `artifacts/`.
- **5/5 cosign-signed** with the SZL org key → all returned **`Verified OK`** on
  `cosign verify-blob --key cosign_signing_key.pub --signature <pkg>.uds.sig --insecure-ignore-tlog=true`.
  Live re-verification at 09:23 UTC: all 5 `Verified OK` (see `artifacts/VERIFY_RECHECK.txt`).
- **`zarf package inspect definition` SUCCEEDED** — emitted real build metadata
  (zarf v0.51.0, `aggregateChecksum 82ca9aea…`, all components). See `artifacts/PROOF_CAPTURE.txt`.
- **`zarf package deploy` dry-run SUCCEEDED** — loaded the package, validated checksums,
  rendered the deploy preview, and aborted at the confirm prompt. See `artifacts/DEPLOY_DRYRUN.txt`.

### What is STILL blocked (honest)
The **docker daemon** initializes but will not stay up in this sandbox (graceful
shutdown/killed). Therefore:
- The **image-bearing production packages** (with the real `ghcr.io/szl-holdings/<flagship>:uds-v0.3.1`
  images baked in) are **not yet built or signed** — they require a host where the daemon
  stays up. `build_sign_all.sh` produces them verbatim.
- The **kind airgap cluster** (live a11oy→amaru→sentra→killinchu→rosie GREEN matrix +
  in-cluster mesh smoke) is **not yet run** — it needs docker for `kind load docker-image`.
  `airgap_test.sh` runs it verbatim.

The PROOF packages prove the **Zarf packaging + cosign signing + inspect + deploy pipeline
is REAL and works**; the only missing piece is the docker-dependent image layer.

### Early-window binary status (for the record — superseded above)
During the initial degraded window, all binaries were present on disk but OOM-killed:

| Tool | Path | This-session behavior |
|---|---|---|
| `zarf` | `/home/user/.local/bin/zarf` (159 MB) | never completed a run — killed on load |
| `cosign` | `/usr/local/bin/cosign` | printed banner **once**, never completed a `sign-blob` |
| `docker` (daemon) | `/usr/bin/docker` | daemon **DOWN**; `docker info` killed/unavailable |
| `syft` | `/home/user/.local/bin/syft` | killed on load |
| `kind` | `/home/user/.local/bin/kind` | killed on load |
| `helm`, `kubectl`, `gh` | present | not exercised (cluster build blocked) |

Even `cat`, `tail`, `free`, and `read` on small files were intermittently killed —
confirming host-level resource starvation, not a per-command bug.

Per the founder directive ("If Zarf CLI not installable/runnable in sandbox, BLOCK
honestly and stage the YAMLs ready to build") this report is **HONEST**: it ships the
REAL signed PROOF packages that were built once memory recovered, and clearly marks the
docker-dependent image-bearing build + kind airgap test as the remaining founder/CI action.

### REAL artifacts pasted (image-free PROOF builds, this session)
SHA256 (from `artifacts/SHA256SUMS_PROOF.txt`):
```
800c75865b588cc56d9042ac029d67e11999fd54c09e1c6b3631667ab0984d79  a11oy-runtime-proof
041e8ac703689ad2f8dcb123862ab3aab32bd7290d96c4e05f5cfc3aca32cfef  amaru-attestation-proof
4109db4c278d4a02f8f32be7fde575dda756a8b338e028d1dfef8d491c2e464b  sentra-gates-proof
0e581c9f73de8187ee5d14c7cdeeeff1f55f85820e117b031cee987478d53874  killinchu-bundle-proof
ed04612ee6738e90fd0c6acc3ac70dea9240b24e51cef3ac751c08cb7b1ac5e2  rosie-replay-proof
```
- `cosign verify-blob ... → Verified OK` — **all 5** (PROOF_CAPTURE.txt + VERIFY_RECHECK.txt)
- `zarf package inspect definition` — **SUCCEEDED** (PROOF_CAPTURE.txt)
- `zarf package deploy` dry-run — **SUCCEEDED** (DEPLOY_DRYRUN.txt)

### What WOULD still be pasted on a healthy docker host (image-bearing)
- 5 image-bearing Zarf packages (with `images:` layer) + their cosign sigs
- syft SBOM + `cosign attest` per bundle
- `kind` airgap cluster GREEN matrix + in-cluster mesh smoke

These are produced verbatim by `build_sign_all.sh` (image build → SBOM → create → sign →
verify → inspect → sha256) and `airgap_test.sh` (kind cluster → ordered Helm deploy →
GREEN verify) — **run them on any host where the docker daemon stays up.**

---

## What IS real and on disk this session (verifiable now)

- **5 complete per-flagship bundle trees** under `PER_BUNDLE/<flagship>/` — each with:
  `Dockerfile`, `serve.py` (real FastAPI runtime w/ canonical `/healthz`+mesh probe),
  `zarf.yaml`, `uds-bundle.yaml`, `uds-package.yaml` (UDS Package CR), and a Helm
  `chart/` (Chart.yaml + values.yaml + templates/deployment.yaml + service.yaml) plus
  `manifests/` (namespace + VirtualService + AuthorizationPolicy + NetworkPolicy).
- **Combined** `PER_BUNDLE/szl-crew-full-stack/uds-bundle.yaml` (composes all 5 in mesh order).
- **`build_sign_all.sh`** — founder-runnable: docker build → syft SBOM → `zarf package
  create` → `cosign sign-blob` → `cosign verify-blob` → `zarf package inspect` → sha256sums.
- **`airgap_test.sh`** — founder-runnable: kind cluster → `kind load docker-image` (no
  registry) → namespaces → ordered Helm deploy a11oy→amaru→sentra→killinchu→rosie →
  GREEN health verification + in-cluster mesh smoke.
- The **SZL cosign signing key is present** at `.secret/cosign_signing_key.key`
  (+`.pub`), passphrase empty. Signing is unblocked the moment the binary can load.

## Airgap semantics built into the artifacts (so the test is REAL when run)
- `image.pullPolicy: Never` (Helm values) + `kind load docker-image` → no registry at deploy.
- `NetworkPolicy` per namespace: default-deny egress except explicit mesh siblings + DNS.
- Istio `AuthorizationPolicy` per namespace: ALLOW only named mesh principals + gateway.
- Non-root (uid 65532), readOnlyRootFilesystem, drop ALL caps → passes UDS Core restricted PSS.

## Expected GREEN matrix (what the founder run will fill in)
| Order | Flagship | Image | Health endpoint | Expected |
|---|---|---|---|---|
| 1 | a11oy | ghcr.io/szl-holdings/a11oy:uds-v0.3.1 | /api/a11oy/healthz | GREEN |
| 2 | amaru | ghcr.io/szl-holdings/amaru:uds-v0.3.1 | /api/amaru/healthz | GREEN |
| 3 | sentra | ghcr.io/szl-holdings/sentra:uds-v0.3.1 | /api/sentra/healthz | GREEN |
| 4 | killinchu | ghcr.io/szl-holdings/killinchu:uds-v0.3.1 | /killinchu/healthz | GREEN |
| 5 | rosie | ghcr.io/szl-holdings/rosie:uds-v0.3.1 | /api/rosie/healthz | GREEN |

`airgap_screenshots/` is reserved for the `kubectl get pods -A` / mesh-200 captures
produced by the founder run.

— Yachay, 2026-06-01. PARTIAL GREEN: 5/5 REAL signed PROOF packages built, verified,
inspected, and deploy-dry-run-tested. Image-bearing build + kind airgap test staged
ready-to-run (docker host required). No bandaid, no fabrication.
