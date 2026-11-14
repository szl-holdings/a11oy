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
