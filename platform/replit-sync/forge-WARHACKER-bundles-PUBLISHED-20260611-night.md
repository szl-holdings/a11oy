# FORGE ORDER — UDS bundles are PUBLISHED + SIGNED (correction + remaining gated items)
**From:** CTO/PM agent (founder green-lit, autonomous) · **To:** Forge · June 11 2026, ~10:40 PM EDT, T-5.

## CORRECTION — the bundles were ALREADY published + cosign-signed
My earlier order said "PENDING PUBLISH." That was WRONG. I verified against the GHCR Packages API — all three bundles are real, pullable, and keyless cosign-signed (GitHub OIDC):

| Bundle | Tag | Manifest digest | Signature | Attestation |
|---|---|---|---|---|
| `szl-uds-bundle` (unified mesh) | `uds-v0.2.0` (+0.2.0,+latest) | `sha256:cdc1010e…1f18` | ✓ `.sig` | ✓ `.att` (SBOM) |
| `a11oy-bundle` | `0.5.0` (+latest) | `sha256:d801f8e4…4b51` | ✓ `.sig` | — |
| `killinchu-bundle` | `0.5.0` (+latest) | `sha256:e59921332…426f` | ✓ `.sig` | — |

The live a11oy **Deploy Posture** endpoint (`/v1/deploy/posture`) already reads this LIVE from GHCR on each click and returns `published=True, sig=yes, digest_matches_expected=True, status=200` for all three. That surface was correct; the static deploy-timeline *badges* in `pages/console.html` (a11oy) and `killinchu_elite_console.py` (killinchu) carried a stale "PENDING PUBLISH / NOT yet published / not yet cosign-signed" claim.

## DONE this session (live, byte-identical, CI/doctrine/drift green)
- killinchu `killinchu_elite_console.py` (commit 4d733f52, HF ec0e7993, byte-identical 9f02121b): stale badge → **"PUBLISHED + SIGNED"** with real digest `e599…426f`, signature-tag note, and a copy-paste `cosign verify` command. Live `/elite` now shows PUBLISHED+SIGNED, zero "PENDING PUBLISH."
- a11oy `pages/console.html` (commit 0184554a, HF af1cb9ef, byte-identical 2a768b30): same flip with digest `d801f8e4…4b51`. (Note: `pages/console.html` is the legacy mirror; the SERVED `/console` SPA Deploy Posture tab was already correct/live-green.)
- All 46 shared modules byte-identical; a11oy 24/24 + killinchu 13/13 CI green; doctrine/drift/banned-token all green; 3 Spaces RUNNING.

## STILL FOUNDER-GATED (NOT auto-done — your call)
These are genuine HARD-LIMIT items; none are blocking for Warhacker since the bundles are already published+signed:
1. **`szl-uds-bundle` re-sign / version bump to uds-v0.3.0** — only if you want the unified mesh bundle re-cut at 0.3.0 (organ images are already at uds-v0.3.0 on a11oy; the bundle metadata is 0.2.0). Triggered by pushing a `uds-v0.3.0` tag (runs UDS Bundle Publish + cosign + Prove Bundle Install). Say the word and I'll cut the tag.
2. **Rekor transparency-log** explicit entry / public verify in the offline-deploy proof.
3. **End-to-end offline (air-gap) deploy proof on the tower** — the one honest gap the UI itself names: `uds pull → uds deploy <tarball>` with the cable pulled. This is the single highest-value Day-3 demo artifact. Needs the UDS/zarf toolchain + a k3d/k3s node — Forge-env, not a browser task. **Recommend Forge runs `Prove Bundle Install` (workflow_dispatch, organ=all) and captures the cosign-verify + deploy-Available output as the outbrief evidence clip.**
4. warn→enforce policy transition; MAJOR dep bumps.

## OUTBRIEF LEAD (unchanged)
Lead with **L6 chain-of-title** (`chain`/`l6chain`): one offline-verifiable receipt unifying software (cosign+Rekor+in-toto/SLSA) ∧ science (Zenodo DOI) ∧ math (lake-verified Lean). Now back it with the live Deploy Posture tab proving the signed bundle is real and pullable on a public registry.
