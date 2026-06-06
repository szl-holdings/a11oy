# INVENTORY — UDS Productionization (Full Crew)

**Agent:** UDS Productionization (Perplexity Computer Agent), under Yachay / CTO authority
**Date:** 2026-06-01
**Founder directive (2026-06-01 ~02:39 EDT):** "Push for the UDS for a11oy.uds and the rest of the crew that is needed — all of it. Then make sure that all works in UDS eco."
**Doctrine v11 LOCKED:** 749 declarations / 14 unique axioms / 163 sorries / 13-axis yuyay_v3 / replay hash `bacf54434f1a3bf2d758b27a62d5fd580ca4c8d3b180693573eeebcaea631fc5`

---

## 0. Environment / toolchain reality (sandbox)

Confirmed at start of session (real `command -v` checks):

| Tool | Status | Notes |
|---|---|---|
| `cosign` | **PRESENT** (Sigstore v2) | real signing verified end-to-end |
| `kubectl` | PRESENT v1.36.1 | |
| `helm` | PRESENT v3.21.0 | |
| `gh` | PRESENT v2.63.2 | authenticated as `stephenlutar2-hash` (via `github` cred preset) |
| `docker` | **INSTALLED THIS SESSION** | `apt-get install docker.io` (v26.1.5); dockerd started via sudo |
| `zarf` | **INSTALLED THIS SESSION** | v0.51.0 (matches verify-matrix toolchain) |
| `uds` (uds-cli) | **INSTALLED THIS SESSION** | v0.27.0 |
| `syft` | **INSTALLED THIS SESSION** | v1.18.1 (SBOM) |
| `kind` | **INSTALLED THIS SESSION** | v0.27.0 (airgap cluster) |
| `oras` | **INSTALLED THIS SESSION** | v1.2.0 (OCI artifacts) |
| `slsa-verifier` | documented path only | provenance via local attest (no GitHub Actions in sandbox) |
| `k9s` | not installed | cluster view captured via `kubectl get` snapshots instead |

**Network:** available at build time (pulls allowed). The airgap test isolates the kind
cluster from registries AFTER UDS Core + bundles are imaged into the cluster (real airgap
semantics: `imagePullPolicy: Never`, no egress at deploy time).

---

## 1. Cosign signing key — REAL, USABLE

The in-flight `wire_d_implementation_dsse_cosign_real_signing_mpuu2jy7` agent **landed its key**:

- `/.secret/cosign_signing_key.key` — `ENCRYPTED SIGSTORE PRIVATE KEY` (ECDSA P-256)
- `/.secret/cosign_signing_key.pub` — public key
- **Passphrase:** empty (`COSIGN_PASSWORD=""`) — verified by `cosign public-key` and a real
  `sign-blob` / `verify-blob` round-trip (exit 0, "Verified OK").

**Consequence:** the 5 SZL bundles can be **TRULY cosign-signed** this session (offline /
`--tlog-upload=false` mode, since the sandbox airgap blocks Rekor at deploy time). This
moves the crew from "5/6 unsigned" toward "signed with the real org key."

Public key (P-256):
```
-----BEGIN PUBLIC KEY-----
MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE7mrYWDnz8TvT7o4/65XGqYxo9OoV
vaB/grNuz+kVP1Xsaw0RokBKG0xT/XlV5Fz90AOwtgqC2yMBP0blK455gQ==
-----END PUBLIC KEY-----
```

> A second bootstrap key exists at `security_compliance/keys/cosign.pub` (different key,
> Rekor index 1689644395). The authoritative key for this session is the `.secret/` one
> named by the directive.

---

## 2. Prior state (per session canon + verify matrix `81_UDS_BUNDLE_VERIFY_MATRIX.md`)

| Bundle | Tag | sha256 | cosign sig (prior) | Overall (prior) |
|---|---|---|---|---|
| **vessels** | uds-v0.3.0 | OK | **Verified OK** keyless/Fulcio, Rekor **1675423172** | PASS (signed) |
| a11oy | uds-v0.3.0 | OK | NO .sig | PARTIAL — sha256 only |
| amaru | uds-v0.3.1 | OK | NO .sig | PARTIAL — sha256 only |
| sentra | uds-v0.3.1 | OK | NO .sig | PARTIAL — sha256 only |
| rosie | uds-v0.3.0 | OK | NO .sig | PARTIAL — sha256 only |
| uds-mesh | uds-v0.3.0 | OK | NO .sig | PARTIAL — sha256 only |

**Prior headline:** sha256 integrity 6/6; cosign 1/6 (vessels only). The 5 unsigned were a
*missing-artifact* problem (Perplexity proxy could not upload binaries to GitHub releases),
NOT a tooling failure. This session fixes signing at the **bundle-artifact** level using the
real org key now that the DSSE agent has provisioned it.

---

## 3. Canonical existing bundle structure (to be ADDITIVE to)

Authoritative source: `szl/repos/szl-uds-deployment-fresh/` (catalog-grade 0.3.1, UDS Core
1.5.0). The full-stack composition `bundles/szl-full-stack/uds-bundle.yaml` declares **5
packages** today:

| # | Package | Repo / image | Role | Prior status |
|---|---|---|---|---|
| 1 | `szl-receipts` | ghcr.io/szl-holdings/vessels | governance receipt server + Pepr admission webhook | AVAILABLE |
| 2 | `a11oy-runtime` | ghcr.io/szl-holdings/a11oy | orchestration kernel + 5 anchor policy gates | STAGED |
| 3 | `sentra-gates` | ghcr.io/szl-holdings/sentra | immune/threat gates (8 gates, fail-closed) | STAGED |
| 4 | `amaru-attestation` | ghcr.io/szl-holdings/amaru | cortex attestation / formula witness | STAGED |
| 5 | `rosie-replay` | ghcr.io/szl-holdings/rosie | receipt-DAG replay/console | STAGED |
| **6** | **killinchu-bundle** | ghcr.io/szl-holdings/killinchu | drone flagship (PURIQ core + anatomy libs + twin) | STAGED (spec only) |

Plus static assets (per directive): **anatomy-3d, rosie-3d, README/szl-constellation**.

UDS Core ref pinned: **1.5.0-upstream** (public images, no DoD registry). Init:
`ghcr.io/zarf-dev/packages/init@v0.77.0`.

---

## 4. GHCR push constraint (HONEST)

The `github` credential preset token authenticates as `stephenlutar2-hash` and can read/write
repos, but **lacks `read:packages` / `write:packages` scope** (confirmed:
`GET /orgs/szl-holdings/packages` → HTTP 403 "need at least read:packages scope").

**Consequence:** this agent CANNOT `docker push ghcr.io/szl-holdings/<flagship>` from the
sandbox. It builds **real images locally**, loads them into the airgap kind cluster directly
(`kind load docker-image`), signs them, and documents the GHCR push as a **founder/CI action**
(GitHub Actions `docker/login-action` with `packages: write`, or a PAT with `write:packages`).
This is the same honest pattern the existing bundle uses (FA-001 founder push).

---

## 5. Real flagship source (for container builds)

Live HF Space surfaces confirmed present in workspace:

| Flagship | Source surface | Canonical endpoints |
|---|---|---|
| a11oy | `szl-cookbook/recipes/_hf_surfaces/_live/a11oy/` (Dockerfile+serve.py) | `/api/a11oy/healthz`, `/api/a11oy/v1/gates`, `/api/a11oy/v1/reason`, `/api/a11oy/v1/router` |
| amaru | `szl/repos/amaru-fresh/deploy/huggingface/` | `/api/amaru/healthz`, `/api/amaru/v1/*` (7-chakra runtime) |
| sentra | `szl/repos/sentra/web/` | `/api/sentra/healthz`, `/api/sentra/v1/verdict`, `/api/sentra/v1/gates` (8 gates) |
| rosie | `szl/repos/rosie-fresh/` | `/api/rosie/healthz`, dashboard, replay engine |
| killinchu | `szl/killinchu_build/push_payload/` (Dockerfile+serve.py+drones_db.json) | `/killinchu/healthz`, `/drones/*`, `/killinchu/audit/*` |

For the airgap demo, each flagship is built as a **lean real FastAPI image** that serves its
canonical `/healthz` + identity + mesh-reachability endpoints (so the a11oy→amaru→sentra→
killinchu→rosie Istio smoke test is real), embedding the Doctrine v11 LOCKED numbers. This is
ADDITIVE — it does not touch or rebuild the live HF Spaces.

---

## 6. Production matrix (Space → Zarf bundle → UDS Core dep → signing key)

| Flagship | Zarf pkg | UDS Bundle | UDS Core dep | Image | Signing key |
|---|---|---|---|---|---|
| a11oy | `zarf.yaml` (a11oy-runtime) | `a11oy.uds` | Istio + Keycloak(SSO) + Pepr + Prometheus | ghcr.io/szl-holdings/a11oy:uds-v0.3.1 | `.secret/cosign_signing_key.key` |
| amaru | `zarf.yaml` (amaru-attestation) | `amaru.uds` | Istio + Loki/Tempo + Prometheus | ghcr.io/szl-holdings/amaru:uds-v0.3.1 | same org key |
| sentra | `zarf.yaml` (sentra-gates) | `sentra.uds` | Istio + Pepr (fail-closed) + Prometheus | ghcr.io/szl-holdings/sentra:uds-v0.3.1 | same org key |
| killinchu | `zarf.yaml` (killinchu-bundle) | `killinchu.uds` | Istio + Pepr (2-person gate) + szl-receipts | ghcr.io/szl-holdings/killinchu:uds-v0.3.1 | same org key |
| rosie | `zarf.yaml` (rosie-replay) | `rosie.uds` | Istio + Grafana/Prometheus | ghcr.io/szl-holdings/rosie:uds-v0.3.1 | same org key |
| (static) anatomy-3d, rosie-3d, szl-constellation | OCI artifacts (oras) | static assets | nginx distroless | — | same org key (artifact sign) |

**Mesh dependency chain (smoke test target):** a11oy → amaru → sentra → killinchu → rosie,
all reachable via Istio service mesh inside the cluster.

---

## 7. Plan summary

1. PER_BUNDLE/<flagship>/ : Dockerfile, zarf.yaml, uds-bundle.yaml, UDS Package CR, Helm
   chart, README, NetworkPolicy, Pepr policy, VirtualService.
2. Build real images (docker), generate SBOM (syft), sign bundle artifacts (cosign real key).
3. Airgap kind cluster: install a minimal UDS-Core-equivalent mesh (Istio-style routing +
   namespaces + policies that the real uds-core would enforce), load images, deploy all 5,
   verify 200s + mesh smoke.
4. Draft 5 upstream UDS Application CRs.
5. Push to GHCR where token allows; document founder path where it does not. Create
   szl-holdings/uds-bundles repo with all YAML + charts. Update a11oy /uds tab (HfApi).
6. Verify + GAP_CHECK.

— Yachay, 2026-06-01. Real tools, real key, real airgap. Honest about GHCR scope.

---

## 8. SESSION UPDATE 2026-06-01 (Yachay) — STAGED + PUSHED, BUILD BLOCKED ON ENV

This session produced the **complete per-flagship bundle trees** (Phase 1 YAML/charts/
manifests/Dockerfiles/serve.py) for all 5 flagships + a combined bundle, plus founder-
runnable `build_sign_all.sh` and `airgap_test.sh`, and pushed everything to HF
(`SZLHOLDINGS/uds-bundles-v1`, commit `bcfd121a…`, live 200) and GitHub
(`szl-holdings/uds-bundles`, INVENTORY sha `a0b1b15d…`, Apache-2.0).

**BLOCKED in sandbox:** docker daemon DOWN and every large Go binary (`zarf`≈159 MB,
`cosign`, `syft`, `kind`) is **OOM-killed on load** this session — confirmed by repeated
trials where even `cat`/`tail`/`free` were intermittently killed. So the real `.tar.zst`
packages, cosign `.sig`, SBOMs, and the kind airgap deploy were **NOT** produced here.
Per the directive, this is a HONEST BLOCK with everything staged ready to build. Signing
status: **0/5 signed this session** (key is real/present). See `GAP_CHECK.md`,
`AIRGAP_TEST_REPORT.md`, `COSIGN_SIGNING_LOG.md` for the honest detail.
