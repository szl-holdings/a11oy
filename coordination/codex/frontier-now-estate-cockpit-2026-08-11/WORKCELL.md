<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Frontier Now Estate Cockpit Workcell

- Workcell ID: `frontier-now-estate-cockpit-2026-08-11`
- Repository: `szl-holdings/a11oy`
- Base: `main@19ae60fdf6f0f95ce3c2c2a7a3f3f9b9f5d3a2b1c`
- Branch: `agent/frontier-now-estate-cockpit-20260811`
- Tracking issue: `#1258` (W1 public truth and terminal-state runtime)
- Operating mode: `OBSERVE_ONLY`
- Initial state: `IN_PROGRESS_LOCAL`

## Objective

Ship one original, responsive frontend and one thin read-only backend projection that make the existing Series-A estate observer usable as the Frontier Now control surface. The slice must enumerate GitHub and Hugging Face capability coverage, expose unavailable capabilities instead of treating them as zero, keep GitHub source revision separate from Hugging Face overlay/runtime identity, and reuse the existing store, signer, receipts, events, and passport authority.

This workcell does not add a provider writer, a second database, a second signer, a new execution path, or a public claim that the estate is fully operational.

## Planned patch

- Add `routers/frontier_now_control_plane.py` with GET/HEAD-only projection routes.
- Add `routers/frontier_now_web/` with the version-bound HTML, CSS, and JavaScript UI.
- Register the additive slice through `routers/frontier_reads.py` before the SPA catch-all.
- Export the intentional module from `routers/__init__.py`.
- Add focused tests for route order, JSON content types, bounded queries, fail-closed labels, asset caching, and GET/HEAD side-effect freedom.
- Extend the demo-critical route guard for the new page and summary API.
- Record locally observed verification and every unavailable readback in an
  audit proof packet before commit.

## Collision exclusions

Do not modify files currently owned by open pull requests:

- `szl_frontier_index.py`
- `ops/frontier/v16_7/**`
- `.github/workflows/frontier-solo-qualification.yml`
- `.github/workflows/frontier-v16-7-exact-source-builder.yml`
- `.github/workflows/series-a-live-control-plane.yml` and the other workflow files
  owned by open draft PR #1254
- `coordination/codex/oro-operational-workstream/**`
- `web/console/package.json`
- `serve.py`, the front-door truth/mobile workflow, and related readiness files
  owned by open PR #1281
- `scripts/alert_channel_canary.py` and `tests/test_alert_channel_canary.py`
  owned by open PR #1279

Do not modify `routers/series_a_control_plane.py`; consume its existing service through `app.state.szl_series_a_service`.

## Success criteria

1. `/frontier-now` and `/now` render the same version-bound cockpit.
2. `/api/a11oy/v1/frontier-now/summary` returns a no-store JSON projection with explicit observation, enforcement, and identity states.
3. `/api/a11oy/v1/frontier-now/inventory` reports every supported provider capability and uses `UNAVAILABLE` for missing/unsupported evidence.
4. Repeated GET/HEAD requests do not append receipts, events, or snapshots.
5. The UI reaches a terminal state on timeout/error, uses text in addition to color, supports keyboard focus and reduced motion, and remains usable at mobile and desktop widths.
6. Focused tests, syntax checks, doctrine checks, route guards, and browser
   evidence are recorded exactly as observed. Screenshots are promoted only
   after a post-fix frame is directly witnessed.
7. Any remote branch or pull request is signed, DCO-compliant, protected, and reported separately from merge or deployment.

## Known hosted blockers

- Hugging Face admin/publication credentials are not available in this local lane.
- Several Hugging Face Spaces are currently paused; quota errors are fail-closed blockers.
- GitHub source SHA, Hugging Face repository SHA, and runtime-reported source SHA are distinct identities; exact overlay equivalence is currently unavailable.
- The existing immutable HF byte-parity check may reject source-ahead deployment files before the governed publisher runs. It must not be weakened or bypassed.

## Current verification state

- The local automated and browser evidence is recorded in `PROOF.md`.
- A MODELED local fixture exposed a 390px horizontal-overflow defect; the CSS
  cause was fixed and protected by a focused regression.
- The in-app browser then blocked the required localhost reload under its URL
  policy. Post-fix visual readback and screenshots are therefore `UNAVAILABLE`,
  not silently implied complete.
- The two pre-fix PNG captures and the local `work/` dependency/test artifacts
  are explicitly excluded from the candidate index and must not be committed.
