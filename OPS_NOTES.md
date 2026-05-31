# OPS_NOTES.md — a11oy operational notes

Authored for SZL Holdings. Signed-off per repository DCO.
Doctrine v7 compliant — no fake-green labels, no marketing superlatives.

---

## Base image disclosure — Iron Bank gap

**Current base images are vanilla (not Iron Bank-approved):**

| Stage   | Image           | Notes                                      |
|---------|----------------|--------------------------------------------|
| builder | `node:22-alpine` | Official Docker Hub Node.js Alpine image   |
| runtime | `node:22-alpine` | Same — minimal Alpine; not hardened        |

Iron Bank-approved base images (e.g., `registry1.dso.mil/ironbank/opensource/nodejs/nodejs22`)
are **not** currently used. This is an honest gap, not a configuration oversight.

Iron Bank hardening is a Warhacker hardening item tracked in:
**[szl-holdings/a11oy#164 — chore(hardening): migrate to Iron Bank-approved base images](https://github.com/szl-holdings/a11oy/issues/164)**

Until that issue is resolved and the Dockerfile updated, do **not** label this image as
Iron Bank-compliant or DoD IL-approved. Claims of IL-5/IL-6 suitability require the
Iron Bank base plus a Platform One Continuous Authority to Operate (cATO) review.

---

## Serve mode (HTTP API)

The `serve` subcommand starts an HTTP API on `A11OY_PORT` (default `8080`).
It is implemented by `packages/receipt-substrate/src/server.ts` (serve-BE PR, pending merge).
Until that PR lands, the entrypoint exits with a clear error if `serve` is invoked and the
server module is absent — no silent hang, no fake-green probe response.

Probes:
- `GET /healthz` — liveness: returns `{"status":"ok"}` once the process is up.
- `GET /readyz`  — readiness: returns `{"status":"ready"}` after full initialisation.

---

## Container image registry

Production images: `ghcr.io/szl-holdings/a11oy`

Tagging strategy:
- `sha-<7-hex>` — every push to `main` (continuous delivery tag).
- `<semver>` + `latest` — published GitHub Releases only.
- `pr-<7-hex>` — pull-request builds (local daemon only; not pushed to GHCR).

---

## SLSA posture

Current level: **SLSA L1 (honest)** — source + build provenance documented via
`slsa-provenance.yml`. L2/L3 require Sigstore + isolated builders (roadmap item).

---

## Known gaps (tracked)

| Gap | Tracking |
|-----|----------|
| Iron Bank base images | [#164](https://github.com/szl-holdings/a11oy/issues/164) |
| `serve` subcommand server module | serve-BE PR (pending) |
| SPA routes wired to real data | SPA-repair PR (pending) |
| SLSA L2/L3 isolated builder | ROADMAP.md |
