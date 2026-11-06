# Anatomy personal-namespace leak (Doctrine v7 §14 observation)

Date: 2026-11-05. Found while mapping Hub writers into `publishing/hf-hub-ownership.json`.

The anatomy Space's live deployment mirror is `betterwithage/anatomy` (creator profile,
`https://betterwithage-anatomy.hf.space`), written by `.github/workflows/hf-living-anatomy-guardian.yml`
(30-minute cron + push) and probed by `.github/workflows/smoke-monitor.yml` and referenced in
`anatomy-map-drift.yml`. No `SZLHOLDINGS/anatomy` repo exists on the Hub. `atelier-kit/models.json`
and `pages/atelier.html` still reference the dead org id.

This file exists because the literal string may not live in org code/manifests (namespace fence
CI); the ownership manifest records the target canonically as `SZLHOLDINGS/anatomy` with the
guardian workflow marked retired pending a fold/recreate decision by the owner.

Recommended resolution: either recreate the Space under the org and repoint the guardian, or
retire the guardian workflow and remove the smoke-monitor probe.

## Resolution (2026-11-06)

The Space was transferred on the Hub from the creator profile to `SZLHOLDINGS/anatomy`
between 2026-11-06 00:42Z and 02:24Z (the Hub API now 307-redirects the old id and the old
`*-anatomy.hf.space` host answers 404; `https://szlholdings-anatomy.hf.space` serves the same
revision). The guardian, the smoke-monitor probe, the keep-lists and the page references were
repointed to the org-owned Space and `publishing/hf-hub-ownership.json` now names the guardian
as the active lifecycle writer. The personal-namespace literal no longer appears in org
code/manifests.
