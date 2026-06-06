# szl-uds-deployment v0.4.0 — Warhacker meta-bundle

**Date:** 2026-05-30
**Bundle:** `szl-warhacker` (`bundles/szl-warhacker/uds-bundle.yaml`)
**Motivation:** Andrew Greene (Defense Unicorns) — *"It'd be awesome to see a running
deployment of what you've built"* — Option A endorsement. Target event: Warhacker
2026, San Diego, June 16–19.

## What's new

- New `szl-warhacker` UDS meta-bundle (`metadata.version: 0.4.0`) that bootstraps, in
  one `uds run start`: a `szl-warhacker` k3d cluster → Zarf init → uds-core slim-dev →
  szl-receipts (Pepr admission webhook + DSSE receipt server) → vessels-uds (optional).
- New `tasks.yaml`: `start`, `verify` (Doctrine §10 HTTP-200 evidence),
  `demo:scenario` (mirrors `docs/WARHACKER_DEMO.md`), `cleanup`.
- New `README.md` documenting honest artifact status and exact run/verify commands.

## Honest scope (Doctrine V7 §10)

This release does **not** claim "all 5 modules boot together." Verification on
2026-05-30 found that only **vessels** ships a signed Zarf package at `uds-v0.3.0`;
**amaru, a11oy, sentra, rosie** publish SBOM JSON only — no package, no image, no
`zarf.yaml`. Those four are referenced in the bundle as the target topology but are
**commented out / STAGED** so the bundle cannot misrepresent a non-existent artifact
as deployable. This matches the existing `bundles/szl-full-stack` convention and the
`docs/WARHACKER_DEMO.md` talk track (uds-core + szl-receipts).

### Known blockers carried into v0.4.0

- **FA-001** — module container images not yet pushed to `ghcr.io/szl-holdings/<module>`.
  Even vessels (signed package present) will `ImagePullBackOff` until its image is pushed.
- **Zarf packages missing** for amaru/a11oy/sentra/rosie (no `zarf.yaml` in those repos).
- **Bundle not cosign-signed** (Phase 2, org key U5). `cosign verify` on the bundle
  artifact will fail until the key is provisioned.

## To activate full 5-module orchestration

1. Push module images (FA-001). 2. Author + build Zarf packages for the four modules.
3. `zarf package publish` to `ghcr.io/szl-holdings/<module>-uds`. 4. Uncomment the
package blocks in `uds-bundle.yaml`; run `uds run start` + `uds run verify`.

## Verify this release

```bash
cd bundles/szl-warhacker
uds run start && uds run verify   # requires docker + k3d + uds + zarf + kubectl
```

## Licensing

szl-receipts (Pepr policy + receipt server): Apache-2.0 — contribution offer to
Defense Unicorns. No AGPL entanglement with uds-core.
