# FORGE ORDER — Warhacker Readiness (June 11 2026, night, T-5)
**From:** CTO/PM agent · **To:** Forge (Replit build env) · **Event:** Defense Unicorns Warhacker, June 16–19 2026, San Diego.

## DONE THIS SESSION (already live, byte-identical, CI/doctrine green — DO NOT redo)
A CTO/PM audit + 2 Opus 4.8 devs hardened the whole estate tab-by-tab against the Warhacker BUILD/PACKAGE/DEPLOY/DELIVER + UDS Core packaging criteria. 11 fixes shipped:

**a11oy** (served `/console`, SPA = `console/index.html`):
1. `command`↔`udsMesh` health contradiction reconciled — honest "1/5 external organ services on HF demo; in-image capability mesh 6/6" label. (Dev A `console.html` e6b97e9b/432a77c0)
2. `deploy` PACKAGE chain now names OCI artifact `ghcr.io/szl-holdings/a11oy-bundle:0.5.0` (PENDING PUBLISH) + organ image `uds-v0.2.0` digest `45fa2365…`.
3. Deploy-target legend: Cloud (HF) LIVE / Hetzner a11oy.net 167.233.50.75 LIVE / edge·airgap ROADMAP.
4. KaTeX 0-CDN fonts — all 18 probed (woff2/woff/ttf) now 200 via `_vendor_blobs.py` (was 404 for woff/ttf).
5. **Stale "Only 5 formulas" → honest "Only 8 formulas are formally proven (locked)" in the served `console/index.html` honesty panel (line 648).** Commit `5d0e4307`, HF `04dfff1f`, byte-identical `eefe9d59`, live-verified.

**killinchu** (served `/elite`):
6. **Stale "Only 5" → "Only 8 … {F1,F4,F7,F11,F12,F18,F19,F22} @ c7c0ba17"** on `honest` + `u_about` (eabad801). The biggest readiness defect — honesty surface now matches canonical locked-8.
7. Null-safe `seal-0` guards (sovereignty + neuro no longer throw; shared `dag3d()` filters dangling links) — feef396e.
8. Vendored 60 KaTeX 0.16.9 fonts to `static/vendor/fonts/` (58fe45ac) — 0-CDN/air-gap.
9. warboard/u_warhacker demo count 25→27 (25 baseline + 2 novel) — e0dec44d.
10. anatomy body copy v3→v4 (935afbce).
11. killinchu `deploy`/`uds_package` edge/airgap deploy-target + OCI `killinchu-bundle:0.5.0` PENDING PUBLISH card (d5d1349d).

**Drift repair:** a11oy's corpus commit (`127a2a8a`, "publish signed receipts to public HF dataset") added a try/except-guarded `szl_corpus_publish` hook to `szl_dsse.py` on a11oy only → drift guard went red. Resolved by syncing killinchu `szl_dsse.py` to a11oy canonical bytes (`6caa040b`, HF `26b43336`, blob `4feec2c8` both sides). All 46 shared modules byte-identical; drift guard green both apps.

## GATED ITEMS NEEDING FOUNDER APPROVAL (NOT auto-done — HARD LIMIT)
These are the only things between us and a fully-published PACKAGE story. Each requires the founder's explicit go:
1. **Publish + cosign-sign the UDS bundles** `a11oy-bundle:0.5.0` and `killinchu-bundle:0.5.0` to `oci://ghcr.io/szl-holdings/...` via the `uds-bundle-publish` workflow. CI token lacks `attestations:write`; bundle-level provenance = the cosign signature. Currently honestly labeled PENDING PUBLISH in-app. **This is the single highest-value pre-Warhacker action** — turns "PENDING PUBLISH" into a pullable, signed, offline-verifiable artifact the judges can `cosign verify`.
2. **Rekor transparency-log** entry for the signed bundles.
3. **uds-v0.3.0 re-sign** (bundle version bump).
4. **warn→enforce** policy transition (currently warn).
5. MAJOR dep bumps (none auto-merged).

## OPTIONAL ENHANCEMENT (low priority, not gated)
- Bring `szl_corpus_publish.py` to killinchu so the new DSSE corpus-publish hook is active there too (currently absent on killinchu; the hook is try/except-guarded so killinchu is safe without it — the receipts just aren't published from killinchu's khipu surface). Only do this if corpus-publishing from killinchu is desired; it writes to the public HF dataset.

## OUTBRIEF LEAD (DELIVER)
Lead the Day-3 outbrief with **L6 chain-of-title** (`chain`/`l6chain` tab): one offline-verifiable receipt unifying software (cosign+Rekor+in-toto/SLSA) ∧ science (Zenodo DOI) ∧ math (lake-verified Lean). Industry stops at L1–L5; nobody else operationalizes L6. That is the "why us."
