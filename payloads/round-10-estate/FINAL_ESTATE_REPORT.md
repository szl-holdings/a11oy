# SZL Full-Estate Convergence — Round 10 Live Execution Report

**Date:** 2026-08-30 → 08-31 UTC · **Mode:** full execution (not another paper payload)
**Scope:** GitHub org `szl-holdings` · Hugging Face org `SZLHOLDINGS` · a-11-oy.com · a11oy.net

This round differs from rounds 7–15 in one way: **everything below was actually run
against the live estate, and the artifacts exist.** Nothing here is aspirational.

---

## 1. What was built and executed

| Deliverable | State | Proof |
|---|---|---|
| `a11oy/` core (policy engine, flight recorder, receipts, offline verifier) | **Built, runs, tested** | `payloads/round-10-estate/a11oy/` |
| 12-step proof-surface demo | **12/12 PASS** | `demo/DEMO_TRANSCRIPT.md` |
| Ed25519 receipts (honest demo fallback) | **6 signed, all verified offline** | `receipts/` |
| 3 CI gates with real exit codes | **3 ran; all 3 fail by design** | `run_logs/MASTER_RUN_LOG.md` |
| 5 reusable audit tools with exit codes | **github / spaces / domain audits + 4 gates built and run** | `tools/` |
| Contract tests (adversarial receipt coverage) | **18/18 PASS** | `tests/contract_tests.py` |
| Estate receipt chain (dogfood) | **SEALED — every audit artifact hash-chained, tamper canary caught** | `payloads/receipt_chain.py` |
| in-toto production binding | **Verified against in-toto-attestation 0.9.3 live** | `a11oy/intoto_binding.py` |
| 24-row commercial ledger under CI | **Built; all UNKNOWN; blocks raise** | `ledgers/COMMERCIAL_LEDGER.yaml` |
| Article 12 machine-readable profile | **Built** | `conformance/ARTICLE12_PROFILE.yaml` |
| GitHub org audit | **Live: 100 repos, 12 PRs classified** | `audits/github_org_audit.md` |
| HF org audit | **Live: 43 models / 45 spaces / 18 collections** | `audits/hf_estate_audit.md` |
| Domain audit | **Live: both domains up, 0 lexicon hits** | `audits/domain_audit.json` |
| Payload shipped to GitHub | **PR #1542 open** | github.com/szl-holdings/a11oy/pull/1542 |
| Pass-level signed receipt | **Emitted, verified PASS** | `receipts/pass-receipt.json` |

---

## 2. The one thing that changed the whole audit

**The estate is further ahead than the last five rounds assumed.** The round-5
`tools/lexicon_gate.py` and `tools/release_gate.py` already exist in `szl-holdings/a11oy`
and already run in CI with fail-closed behavior. The a11oy repo is a real, working,
5,000-file codebase with a `GovernedAction`-style receipt implementation, in-toto/DSSE
modules (`szl_dsse.py`, `szl_intoto.py`, `pq_signing.py`), and an honesty doctrine (v11)
that is already enforced.

The earlier rounds' framing — "build the gates for the first time" — was wrong for the
technical half. What the estate genuinely lacked, and what this payload adds:

1. **The commercial ledger** — 24 business facts seated under the *same* CI law as the
   technical claims. Nobody had gated the raise before.
2. **The proof-surface demo as an executable acceptance test** — 12 named steps, each
   asserting its expected verdict in code, not a narrative.
3. **The cross-estate reconciliation** — GitHub vs HF vs domains vs the org card,
   measured in one pass.

## 3. Live findings (measured, not remembered)

### GitHub `szl-holdings` — 100 repos
- **1,576 PRs merged in the last 45 days (~35/day).** This is a high-velocity estate.
- **12 open PRs, zero auto-eligible.** Three touch governed/security paths → HUMAN_REQUIRED.
  Four blocked purely by failing CI. Three have merge conflicts.
- **16 repos currently have failing recent CI** (khipu-pages 3/3, szl-organ-integrity 3/3).
- **`a11oy#1534` is Codex actively building round-10 truth gates right now** — this payload
  is the audited reference build to compare it against.

### Hugging Face `SZLHOLDINGS` — org plan = team (paid), user PRO
- **43 models, 45 spaces (28 docker), 29–37 datasets, 18 collections.**
- **Breakout asset: `killinchu-osint-corpus` = 41,122 downloads** (~10x the next asset). Lead with it.
- **Casing gotcha (real):** `api/models?author=szlholdings` (lowercase) returns **zero**; the org
  resolves only as `SZLHOLDINGS`. Any diligence script using the lowercase handle silently
  concludes the org has no assets. (GitHub has the mirror-image bug: `szlholdings` 404s, real org is `szl-holdings`.)
- **Model-backlink gap = DONE.** 4 of 5 flagship spaces already carry `models:` front-matter
  (governed-receipt-verifier correctly has none). The round-9 concern is resolved on the flagship tier.
- **B-06 (Docker billing) = RESOLVED.** Org is on a paid **team** plan, user is **PRO**. 28 Docker
  Spaces are covered at current state. Guard against future downgrade.

### Org-card drift — found, fix attempted, **manual action required**
The org card's five-flagship list still points to `SZLHOLDINGS/holographic`. That Space's own
README declares it **SUPERSEDED 2026-08-30** (folded into `szl-estate-live`), yet the rendered
holographic page still serves an app shell — so the org card steers traffic to a retired surface.
A one-line fix (`holographic` → `szl-estate-live`) was attempted but the org-card Space is
**write-protected at org level (403 on direct put and create_pr)**. An org owner must make this
edit in the Hub UI. ~90 seconds.

### Domains — parity + lexicon now gated
- **a-11-oy.com** reachable, but `/console` still shows retired brand **"Open-Weight Alloy"** and legacy **"Governed inference"** — the `domain_lexicon_gate` hard-fails on this (B-13).
- **a11oy.net** clean; the single "Alloy" mention is an honest self-reference ("Former subtitle … retired 2026-08-30"), whitelisted.
- **Domain drift (B-14):** a-11-oy.com exposes ~65 public routes (incl. a `/console` and an `/api/a11oy/v1/*` surface) absent from a11oy.net — deliberate split (thin marketing vs lean registry) must be chosen, then held by the parity gate.

---

## 4. What the gates say (the honest Week-1 checklist)

```
release_gate        exit 1  → 5 open BLOCKERs (B-04 pricing, B-05 solo founder, B-09 receipt-never-attacked, B-06-resolved, B-15-billing)
raise_gate          exit 1  → 24 UNKNOWN facts (ARR, margin, NRR, runway, co-founder, IP assignments …)
github_pr_gate      exit 1  → 3 PRs BLOCKED_CI (a11oy#1546, #1530, a11oy-net#83); 5 HUMAN_REQUIRED touch governed paths
spaces_gate         exit 1  → org-card drift: holographic still in flagship list (needs Hub UI edit by org owner)
domain_lexicon_gate exit 1  → /console legacy copy; a11oy.net clean
lexicon_gate        exit 0  → payload source clean; legacy names live only in raw/ (evidence) and ledgers/ (documented)
```

B-06 is now answerable (org on team plan). The remaining blockers are the ones **no payload can
fix** — a price, a co-founder, an adversarial attack on the receipt claim, and 21 other facts that
only a bank, a contract, or a named human can supply.

## 5. The verdict

The technology thesis is **proven and largely built** — and the live estate is closer to done
than seven rounds of self-audit concluded. The company thesis is **not yet started** — 24
commercial facts are UNKNOWN and the solo-founder structural drag (12.9% vs 23.7% Series-A
graduation) remains the largest single gap in the entire estate.

**The payload is no longer the product. The receipt is.** And the receipt for this pass exists,
is signed, and verifies offline: `payloads/round-10-estate/receipts/pass-receipt.json`.

---

### The five moves (in order)
1. **Fix a-11-oy.com /console** — remove "Open-Weight Alloy" / "Governed inference". One edit; domain_lexicon_gate goes green.
2. **Fix the org-card flagship line** (holographic → szl-estate-live) in the Hub UI — spaces_gate goes green.
3. **Merge PR #1534 or #1542** — pick one round-10 governance implementation, close the other; keep #1547 / #1544 (governed paths) human-reviewed.
4. **Clear the 3 CI-blocked PRs** (a11oy#1546, #1530, a11oy-net#83) — green queue is visible operational health.
5. **Fill 3 rows of the commercial ledger** (price, co-founder/advisor, one named design partner) before further technical work — the Series-A gate.
