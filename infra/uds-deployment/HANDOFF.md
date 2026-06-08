# HANDOFF — Start Here

> **Audience:** a human developer taking over SZL Holdings cold.
> **Compiled:** 2026-06-05 · verified live against the GitHub API this session.
> **This repo (`szl-uds-deployment`) is the anchor** — the live, signed UDS deployment.

## Honesty contract (read first — never overstate)
- **Λ (Lambda) = Conjecture 1.** Not a theorem. Do not claim proven.
- **Public formula count = 5** (the live API truth from a11oy `proved_count`). The Lean
  `lake` build may show more targets green, but the served set is 5 until `serve.py` is
  updated to read the proved set and redeployed.
- **SLSA L1 honest · L2 build-attested (Rekor) · L3+ roadmap = verified on 5/5 organ images.** True statement:
  *"SLSA L2 provenance attestation cryptographically verifies (cosign verify-attestation,
  keyless Fulcio+Rekor, strict per-organ identity) on all 5 organ images: a11oy, sentra,
  amaru, rosie, killinchu."* SLSA L1 holds on all. The **bundle**
  (`szl-uds-bundle:uds-v0.2.1`) is **signed** (cosign keyless, Fulcio+Rekor) **and carries a
  build-provenance attestation** produced via `actions/attest-build-provenance` — verify with
  `gh attestation verify oci://ghcr.io/szl-holdings/szl-uds-bundle:uds-v0.2.1 --owner szl-holdings`
  (run from a non-GHES host; the sandbox proxy is detected as GHES and `gh attestation` refuses).
- **No L3 / FedRAMP / Iron Bank / CMMC.** None of these are claimed or held.

---

## 1. What this is

SZL ships **governed-AI decision infrastructure**: five "organs" that each sign and
receipt every decision, composed into one deployable **UDS bundle** that runs on a
Kubernetes (k3d) cluster with a Pepr admission webhook emitting DSSE receipts.

The five organs:
| Organ | Role |
|-------|------|
| **a11oy** | policy + receipt substrate orchestrator (mediator) |
| **sentra** | cyber-resilience runtime — fail-closed safety gates |
| **amaru** | convergent data-sync + attestation / memory cortex |
| **killinchu** | receipt / transport courier (counter-UAS rule engine) |
| **rosie** | governed decision fabric + operator console |

---

## 2. Repo clone order (cold start)

```bash
# 1. The anchor — the live signed deployment (this repo)
git clone https://github.com/szl-holdings/szl-uds-deployment.git

# 2. The five organs (source of the signed images)
for r in a11oy sentra amaru rosie killinchu; do
  git clone https://github.com/szl-holdings/$r.git
done
# killinchu is PRIVATE — needs an authorized PAT.

# 3. Doctrine + org profile (Doctrine v11 source of truth)
git clone https://github.com/szl-holdings/szl-doctrine.git   # PRIVATE
git clone https://github.com/szl-holdings/.github.git

# 4. Math/papers (optional): lutar-lean (the real Lean kernel), lambda-bounty, szl-papers
```

> **Do NOT clone `platform`** unless you need it — it is a 641 MB monorepo. Inspect it
> with `gh repo view szl-holdings/platform` / `gh api` instead. It already contains
> company-grade docs (BILLING, API-SPEC, INCIDENT_RESPONSE, threat_model, KNOWN-GAPS…).

The full repo inventory (41 org + 13 user repos, with ACTIVE/ARCHIVE/DUP/STALE marks)
lives in `team/org_handoff.md` alongside this handoff effort.

---

## 3. Build & run

**Each organ** is a FastAPI app served by `serve.py`, containerized via its `Dockerfile`,
published to GHCR and a Hugging Face Space. Local boot test before any Space push:
```bash
cd <organ> && uvicorn serve:app --port 7860   # confirm it imports & boots
```

**The deployment (this repo):**
```bash
make quickstart          # k3d + uds-cli + Pepr receipt policy, cosign-verified
# or follow docs/OPERATOR_QUICKSTART.md / docs/INSTALL.md
```

---

## 4. Deploy order — the one-USB UDS command

The **real mesh bundle** is `szl-uds-bundle:uds-v0.2.1` (composes all 5 organ Zarf
packages; signed + build-provenance attested). One command for an air-gapped / single-USB deploy:

```bash
uds-cli bundle deploy oci://ghcr.io/szl-holdings/szl-uds-bundle:uds-v0.2.1 --confirm
```

Underlying layer order on a fresh cluster: **Zarf init → UDS Core (Istio/Pepr/Keycloak)
→ szl-receipts → organs** (amaru → a11oy → sentra → rosie; a11oy up first so the others
register to it).

> ⚠️ **Do NOT use `szl-warhacker` v0.4.0 as "the mesh."** It stages 4 organs OUT — only
> `szl-receipts` (+ upstream init/core) is deployable in it; the four organ entries are
> commented out (SBOM-only, no signed package at uds-v0.3.0).

---

## 5. Access model (how credentials work)

| Surface | How access works |
|---------|------------------|
| GitHub (read/write, incl. private repos) | Admin GitHub **PAT** routed through the `api.github.com` proxy. `gh`/`git` carry it. |
| Hugging Face (Space deploys, write) | HF write token routed through the `huggingface.co` proxy. |
| **`HF_TOKEN` org secret** | **OWNER ACTION.** The org-level `HF_TOKEN` secret must be set/fixed so org workflows can push to Spaces. Until then HF-sync CI cannot deploy. |

### Known drift to fix
- **HF Space repo vs GitHub repo drift:** merged GitHub code (new routes/tabs) has not
  always baked into the deployed Space image (PR branch not on the image, Dockerfile
  `COPY` omitted modules, or wrong Space repo). **Rule:** test `serve.py` boots locally
  (uvicorn import) before pushing to a Space, and confirm the Space's Dockerfile `COPY`s
  every module `serve.py` imports.

---

## 6. Where the important things live

| Thing | Location |
|-------|----------|
| Formulas (live count = 5) | a11oy `serve.py` `proved_count`; Lean source in `lutar-lean` |
| Receipts (DSSE) | `szl-receipts` server + Pepr admission webhook (`pepr/`); charts in `charts/szl-receipts/` |
| Λ (Conjecture 1) | `lambda-bounty` (bounty harness); papers in `puriq-preprint` / `szl-papers` |
| Replay / doctrine | `doctrine/manifest.json` (this repo); Doctrine v11 in `szl-doctrine` + `.github` |
| UDS bundles | `bundles/szl-uds-bundle/uds-bundle.yaml` (the real mesh), `bundles/szl-warhacker/`, root `uds-bundle.yaml` |
| Organ Zarf packages | `packages/<organ>/zarf.yaml` |

---

## 7. Honest status

- **Live:** all 5 Spaces UP (core routes). Mesh bundle `szl-uds-bundle:uds-v0.2.1` builds + publishes.
- **L1 cosign signatures:** present on all 6 packages (5 organs + the bundle).
- **L2 attestation:** ✅ 5/5 organs (cosign verify-attestation, strict identity). Bundle
  `uds-v0.2.1` is signed + carries a build-provenance attestation
  (`actions/attest-build-provenance`); verify with `gh attestation verify` from a non-GHES host.
- **Supply chain gap:** no `@sha256` digest pins anywhere — tag-only refs.
- **Front door:** GitHub Pages surfaces (developers/docs-site/szl-trust) return HTTP 000
  — Pages not enabled / no custom domain. Company public front door not live.
- **Zarf tag drift:** flagship `deploy/zarf.yaml` files reference unpublished tags
  (`uds-v0.3.1-rc.1`, `v1.0.0-alpha`); only `uds-v0.2.0` is live + signed.

---

## 8. GO / NO-GO

- **June 9 tower rehearsal: GO** — scoped to live core routes; deploy the real mesh
  bundle on the tower's real cluster (closes the k3d deploy-proof the sandbox couldn't).
- **June 16–19 Warhacker: NO-GO** until:
  1. one real end-to-end mesh transaction proven on a real cluster,
  2. CodeQL + Grype made **blocking** checks,
  3. bundle attestation independently re-verified (`gh attestation verify` from a non-GHES
     host — the `uds-v0.2.1` build published it; confirm the verify returns a provenance payload),
  4. HF Space drift resolved (new tabs baked into images).

---

## 9. OWNER-ONLY actions (cannot be done by an agent or non-admin)

1. **`HF_TOKEN` org secret** — set/repair so Space-deploy workflows authenticate.
2. **Bundle attestation re-verify** — the `szl-uds-bundle` GHCR package is linked to the
   **`uds-bundles`** repo (not this one), so the bundle build/publish/sign/attest runs from
   `uds-bundles` (`uds-bundle-publish.yml`); the `uds-v0.2.1` run completed SUCCESS (publish,
   cosign sign, `attest-build-provenance`). Final step is to run
   `gh attestation verify oci://ghcr.io/szl-holdings/szl-uds-bundle:uds-v0.2.1 --owner szl-holdings`
   from a non-GHES host (the sandbox proxy is detected as GHES and refuses). Do NOT claim the
   bundle is L2-attested in public copy until that verify returns a provenance payload.
3. **Zarf tag reconciliation** — flagship `deploy/zarf.yaml` files were repointed from
   unpublished `uds-v0.3.1-rc.1` / `v1.0.0-alpha` to the live signed `uds-v0.2.0`; publish the
   newer tags if/when they are intended to ship.
4. **GitHub Pages** — enable Pages / custom domain on developers, docs-site, szl-trust.

---

*Co-Authored-By: Claude*
*Sign-off: Stephen P. Lutar Jr. &lt;stephenlutar2@gmail.com&gt;*
