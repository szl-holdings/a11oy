# External Audit — 2026-09-09

**Scope:** all externally reachable estate surfaces, the Hub estate, the GitHub issue board, and the frontier research stack. **Method:** live HTTPS probes, Hub API reads, issue-thread archaeology. No tokens, secrets, or internal endpoints accessed. Transport blind spots are declared, not worked around. Auditor: Perplexity session, owner-directed. Related receipt: #1919 comment (2026-09-09).

## Verified green (live evidence)

| Surface | Evidence |
|---|---|
| `a-11-oy.com` apex | `/api/build-info` 200; revision `bb065e8c`; python 3.12.13; `receipt_minted: false` (honest) |
| `SZLHOLDINGS/a11oy` Space | Hub badge RUNNING (2026-09-09) |
| `SZLHOLDINGS/killinchu` | Live, serving the counter-UAS field surface; www.a11oy.net pattern healthy |
| `SZLHOLDINGS/chaski-r2` | `proposal-only` tag present (2026-09-08) |
| Frontier stack | Contracts #2047/#2059/#2060/#2063, harness #2061/#2067, runbook #2062, lockstep #2069 — all merged; head `e14af70d` |

## Findings

### F1 — Canonical publisher not firing for recent merges (highest priority)
`#2010` evidence (2026-09-08 readback): protected main advanced, runtime reports older source (`8d59d6c`); `GITHUB_DEFAULT_BRANCH_DRIFTS_FROM_RUNTIME_REPORTED_REVISION`; claim gate FAILED_CLOSED, public claim HELD. No `Sync and Relock Canonical Hugging Face Space` run exists for current main. Live Space revision `bb065e8c` predates eight merged PRs. The honesty machinery is holding correctly — parity is not claimed. **Repair (owner, one click):** Actions → hf-sync workflow → Run on exact main; require deploy/source-bind/readiness/relock gates to finish. Do not repair via chat-plane Hub writes or manual parity stamps. **Diagnose first:** if the workflow cannot be dispatched or is suppressed, inspect Actions enablement and whether automated merges (token-cascade suppression) starve the trigger.

### F2 — www.a-11-oy.com unresolved (INC-05)
No DNS record. Credential-blocked across all paths (connector 6103 ×10; repo secret invalid since 2026-08-31; Codex sandbox had no CF token). Sole path: dashboard CNAME `www` → `a-11-oy.com` (proxied) + 301 Redirect Rule to apex — mirrors the working `www.a11oy.net` pattern. ~2 minutes, owner-only.

### F3 — Constellation: deprecation, not breakage
`#1675` records RUNTIME_ERROR with factory reboot completed and source still failing; STATUS.md lists the Space as deprecated (replaced by `anatomy-3d`); the consolidation lattice folds it `into: a11oy`. A fold leaves nothing to boot — no restart can succeed (Codex's 2026-09-08 restart attempt registered on the Hub timestamp and did not recover it, consistent with this). **Contradiction to reconcile:** the public-estate contract still lists the Space as a laboratory surface. Owner decision: formal retirement (estate has retirement workflows) vs. contract amendment.

### F4 — Energy ledger fork (#1878)
`chain.ok=false`, first break at indices 39→40, twenty discontinuities; process-local `threading.Lock` cannot serialize writers across a rolling-restart overlap. Requires cross-process writer serialization + forensic rotation of the forked generation. `serve.py` is 985.9KB; safe repair needs full file access and adversarial tests — sized for a coding agent with quota, not a blind edit.

### F5 — Four verticals down (#1824)
Lyte, finance, terra, counsel received v4 commits and never came back (build-queue condition, pins verified on PyPI). Owner restarts in the HF UI, then per-Space verification comments.

### F6 — Flagship Space ships the monorepo (#1836)
~450+ root entries in the public tree; Dockerfile 46.7KB; serve.py 985.9KB; `_vendor_blobs.py` 2.6MB. Publish allowlist per the vertical-services pattern; target Dockerfile <100 lines. Recorded, not urgent.

### F7 — Canary pin stale (#1359)
Issue closed-completed but the last recorded run predates the 45px CTA fix; protected-source pin reads `ac64ab8e`. Next scheduled/dispatched run against current source closes the question; no action unless it reopens.

## Codex payload reconstruction (evidence-based)

The closure payload ran with a working HF token and a dead/absent CF token; `gh` unauthenticated in the sandbox. HF-backed steps landed (tag, Space restarts registered); CF/gh-backed steps failed or skipped. Fail-closed step isolation produced partial success with no false green — the design held.

## Frontier steady state

Radar on cadence (TAK lane parked by its second-artifact rule; amx probe candidate stable at 48h check; specdec contract hardened to v1.2 against the thc1006 long-horizon divergence finding). All lanes contracted, all contracts CPU-lab executable, all runs receipt-bound. The program waits on lab physics and the repair queue above — not on further design work.

## Repair queue (owner/executor)

1. Dispatch hf-sync on exact main (F1) — one click
2. Cloudflare dashboard www fix (F2) — two minutes
3. Constellation retirement decision (F3) — one decision
4. Vertical restarts (F5) — four clicks
5. Ledger writer repair (F4) — coding-agent task when quota returns
6. Publish allowlist (F6) — scheduled engineering
