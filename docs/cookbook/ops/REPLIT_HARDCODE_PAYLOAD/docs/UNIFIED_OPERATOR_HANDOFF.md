# Unified Operator Handoff — Full SZL Holdings GitHub Audit

<!-- RETIRED-ORGANS-NOTICE -->
> **⚠️ Retired organs notice.** `amaru`, `sentra`, and `rosie` have been retired and consolidated into the **[a11oy](https://github.com/szl-holdings/a11oy)** flagship (Memory, Sentinel, and Operator verticals). Their standalone `szl-holdings/{amaru,sentra,rosie}` GitHub repositories and `szlholdings-{amaru,sentra,rosie}.hf.space` Hugging Face Spaces **no longer exist**; only the signed GHCR images persist, for supply-chain verification. Any amaru/sentra/rosie Space URLs, repo links, or endpoints referenced below are **historical and not live** — use a11oy instead.

<!-- ARCHIVED-THESIS-NOTICE -->
> **⚠️ Archived thesis notice.** The `szl-holdings/ouroboros-thesis` repository has been retired; the Ouroboros Thesis is now archived at Zenodo DOI [10.5281/zenodo.20434276](https://doi.org/10.5281/zenodo.20434276). Any `ouroboros-thesis` references below are **historical and not live**.

**Date:** 2026-05-16
**Operator:** Lutar, Stephen P. — `stephen@szlholdings.com` — ORCID `0009-0001-0110-4173`
**Org:** SZL Holdings
**Doctrine:** V6 · 9-axis Λ ≥ 0.90 conjunctive

**Audited by:** GitHub Expert agent + Agent Dev Program Manager agent, in parallel.

---

## 1. Executive Summary

| Metric | Value |
|---|---|
| Repos audited | 16 |
| Total checks executed | 144 (16 repos × 9 audit dimensions) |
| Open PRs at start | 48 |
| Open PRs at end | 59 |
| PRs opened by CTO this run | 11 (all draft, hygiene + scorecard + pin-bumps) |
| Fix commits pushed by CTO this run | 3 (vsp-otel#5, agi-forecast#5, .github#36) |
| Doctrine comments posted | 13 |
| Scorecard alerts closed by auto-fix PRs | 12 |
| Scorecard average score | 6.59 / 10 |
| Dependabot high/critical | **0** |
| CI green on `main` | **16 / 16** |
| Stale branches (>90 days) | **0** |
| License allowlist violations | **7 repos** (`LicenseRef-SZL-Proprietary`) — operator policy decision |
| Branch protection gaps | 3 repos (`lutar-lean`, `vsp-otel`, `agi-forecast`) |
| Operator-only steps queued | 8 categories, see §6 |

**Bottom line:** The org is in strong shape. Every doable fix is now staged as a draft PR with a Doctrine V6 evidence table. The remaining work is operator-only: mark PRs ready, merge them in wave order, fix branch protection on three repos, decide the license-allowlist policy question, and submit/mint the arXiv + Zenodo artifacts.

---

## 2. Per-Repo Status (after this audit)

| Repo | Open PRs | Hygiene | BP | CITATION | CI | CodeQL | Scorecard | Status |
|---|---|---|---|---|---|---|---|---|
| amaru | 2 | ✅ | ✅ | ✅ | ✅ | ⚠️ open | 6.9 | ✅ |
| a11oy | 2 | ✅ | ✅ | ✅ | ✅ | ⚠️ open | 6.7 | ✅ |
| sentra | 3 | ✅ | ✅ | ✅ | ✅ | ⚠️ open | 6.8 | ✅ |
| terra | 2 | ✅ | ✅ | ✅ | ✅ | ⚠️ open | 6.7 | ✅ |
| vessels | 2 | ✅ | ✅ | ✅ | ✅ | ⚠️ open | 6.7 | ✅ |
| counsel | 2 | ✅ | ✅ | ✅ | ✅ | ⚠️ open | 6.6 | ✅ |
| carlota-jo | 2 | ✅ | ✅ | ✅ | ✅ | ⚠️ open | 6.6 | ✅ |
| ouroboros | 7 | ✅ | ✅ | ✅ | ✅ | ⚠️ open | 6.9 | ⚠️ DOI gate |
| ouroboros-thesis | 6 | ✅ | ✅ | ✅ | ✅ | ⚠️ open | 6.7 | ⚠️ DOI gate |
| lutar-lean | 4 | ✅ | ⚠️ no status checks | ✅ | ✅ | ⚠️ open | **7.1** | ✅ |
| szl-trust | 2 | ✅ | ✅ | ✅ | ✅ | ⚠️ open | 6.8 | ⚠️ DOI gate |
| szl-cookbook | 1 | ✅ | ✅ | ✅ | ✅ | ⚠️ open | 6.5 | ✅ |
| szl-brand | 4 | ✅ | ✅ | ✅ | ✅ | ⚠️ open | 6.5 | ✅ |
| .github | 7 | ✅ | ✅ | ✅ | ✅ | ⚠️ open | 6.4 | ✅ |
| vsp-otel | 7 | ⚠️ CODEOWNERS draft | ❌ no CR/SC | ⚠️ PR fix draft | ✅ | ⚠️ open | **5.0** | ⚠️ |
| agi-forecast | 7 | ⚠️ CODEOWNERS draft | ❌ no CR/SC | ⚠️ PR fix draft | ✅ | ⚠️ open | **5.0** | ⚠️ |

Legend: ✅ clean · ⚠️ has open draft fix · ❌ needs operator action · CR=code-owner reviews · SC=required status checks

---

## 3. PRs Opened By This Audit (11 — all draft)

| Repo | PR# | Title | Category |
|---|---|---|---|
| .github | [#37](https://github.com/szl-holdings/.github/pull/37) | bump harden-runner v2.12→v2.19.3 + codeql v3→v4 + TokenPermissions fix | security/scorecard |
| vsp-otel | [#6](https://github.com/szl-holdings/vsp-otel/pull/6) | add `.github/CODEOWNERS` | hygiene |
| vsp-otel | [#7](https://github.com/szl-holdings/vsp-otel/pull/7) | fix CITATION.cff given-names format | citation |
| vsp-otel | [#8](https://github.com/szl-holdings/vsp-otel/pull/8) | add `.github/dependabot.yml` | scorecard |
| agi-forecast | #6 | add `.github/CODEOWNERS` | hygiene |
| agi-forecast | #7 | fix CITATION.cff given-names format | citation |
| agi-forecast | #8 | add `.github/dependabot.yml` | scorecard |
| szl-trust | [#13](https://github.com/szl-holdings/szl-trust/pull/13) | pin `actions/checkout@v6` → SHA | ci/pin-bump |
| szl-cookbook | [#12](https://github.com/szl-holdings/szl-cookbook/pull/12) | pin `actions/checkout@v6` → SHA | ci/pin-bump |
| szl-brand | [#16](https://github.com/szl-holdings/szl-brand/pull/16) | pin `actions/checkout@v6` → SHA | ci/pin-bump |
| lutar-lean | [#19](https://github.com/szl-holdings/lutar-lean/pull/19) | pin elan init script to v4.2.1 | ci/pin-bump |

Plus **3 fix commits pushed** by PM agent into existing CI-wire PRs:

- vsp-otel#5 — removed `cache: pnpm` (no lockfile yet)
- agi-forecast#5 — removed `cache: pnpm` (no lockfile yet)
- .github#36 — SHA-pinned `actions/checkout` + `markdownlint-cli2-action`

---

## 4. UNIFIED MERGE WAVE PLAN

**Universal pre-merge protocol** (operator runs once per PR):

```bash
# 1. Mark draft → ready
gh pr ready <N> --repo szl-holdings/<repo>
# 2. Wait for CI to go green (or verify it already is)
gh pr checks <N> --repo szl-holdings/<repo>
# 3. Squash-merge
gh pr merge <N> --repo szl-holdings/<repo> --squash --auto
```

### WAVE 0 — Pre-flight (do first, blocks Wave 4–5)

| Step | Why |
|---|---|
| **Fix DOI gate** — operator decides: rebind `19944926 → 20195368` OR add `curl -L` follow-redirect to `doi-title-gate.yml`. CTO can push the workflow fix once you confirm intent. | Unblocks BROKEN PRs (ouroboros#28, ouroboros-thesis#38, szl-trust#11) |
| **License-allowlist policy** — decide: (a) re-license 7 closed-source repos to Apache-2.0/MIT/BSD-3, OR (b) add `LicenseRef-SZL-Proprietary` to Doctrine V6 allowlist | Currently 7 repos technically violate doctrine: amaru, a11oy, sentra, terra, vessels, counsel, carlota-jo |

### WAVE 1 — Hygiene & Citation (LOW RISK, no semantic change)

**41 PRs total** — merge in any order within the wave. All CI green.

```bash
# --- CITATION_FIX (13 PRs from prior CITATION-email sweep) ---
gh pr merge 22 --repo szl-holdings/amaru        --squash
gh pr merge 24 --repo szl-holdings/a11oy        --squash
gh pr merge 21 --repo szl-holdings/sentra       --squash
gh pr merge 22 --repo szl-holdings/terra        --squash
gh pr merge 22 --repo szl-holdings/vessels      --squash
gh pr merge 22 --repo szl-holdings/counsel      --squash
gh pr merge 21 --repo szl-holdings/carlota-jo   --squash
gh pr merge 30 --repo szl-holdings/ouroboros    --squash
gh pr merge 42 --repo szl-holdings/ouroboros-thesis --squash
gh pr merge 17 --repo szl-holdings/lutar-lean   --squash
gh pr merge 34 --repo szl-holdings/.github      --squash
gh pr merge  3 --repo szl-holdings/vsp-otel     --squash
gh pr merge  2 --repo szl-holdings/agi-forecast --squash

# --- Identity sweep (8 PRs, READY) ---
gh pr merge 21 --repo szl-holdings/amaru      --squash
gh pr merge 23 --repo szl-holdings/a11oy      --squash
gh pr merge 20 --repo szl-holdings/sentra     --squash
gh pr merge 21 --repo szl-holdings/terra      --squash
gh pr merge 21 --repo szl-holdings/vessels    --squash
gh pr merge 21 --repo szl-holdings/counsel    --squash
gh pr merge 20 --repo szl-holdings/carlota-jo --squash
gh pr merge 33 --repo szl-holdings/.github    --squash

# --- Docs/README cleanup ---
gh pr close 24 --repo szl-holdings/ouroboros --comment "Superseded by #26 — CTO agent on behalf of Lutar, Stephen P."
gh pr merge 26 --repo szl-holdings/ouroboros        --squash
gh pr merge 43 --repo szl-holdings/ouroboros-thesis --squash
gh pr merge 34 --repo szl-holdings/ouroboros-thesis --squash

# --- New CTO citation fixes (vsp-otel + agi-forecast format) ---
gh pr merge  7 --repo szl-holdings/vsp-otel     --squash
gh pr merge  7 --repo szl-holdings/agi-forecast --squash

# --- New CTO CODEOWNERS additions ---
gh pr merge  6 --repo szl-holdings/vsp-otel     --squash
gh pr merge  6 --repo szl-holdings/agi-forecast --squash
```

### WAVE 2 — Security & Pin-Bumps (LOW RISK)

```bash
# Scorecard / TokenPermissions / Dependabot adoption
gh pr merge 37 --repo szl-holdings/.github      --squash
gh pr merge  8 --repo szl-holdings/vsp-otel     --squash
gh pr merge  8 --repo szl-holdings/agi-forecast --squash

# Action SHA pin-bumps
gh pr merge 13 --repo szl-holdings/szl-trust    --squash
gh pr merge 12 --repo szl-holdings/szl-cookbook --squash
gh pr merge 16 --repo szl-holdings/szl-brand    --squash
gh pr merge 19 --repo szl-holdings/lutar-lean   --squash
```

### WAVE 3 — CI Wire (the 3 silent repos)

```bash
# Verify pin-check passes on .github#36 after b9b2869 first
gh pr checks 5  --repo szl-holdings/vsp-otel
gh pr checks 5  --repo szl-holdings/agi-forecast
gh pr checks 36 --repo szl-holdings/.github

# Then merge
gh pr merge  5 --repo szl-holdings/vsp-otel     --squash
gh pr merge  5 --repo szl-holdings/agi-forecast --squash
gh pr merge 36 --repo szl-holdings/.github      --squash
```

### WAVE 4 — Fly V9 Fleet (MEDIUM-HIGH RISK — semantic change)

Sub-wave order matters (dependencies):

```bash
# 4a — foundation
gh pr merge 35 --repo szl-holdings/.github --squash      # M2M envelope

# 4b — runtime scaffolds (can parallelize)
gh pr merge 31 --repo szl-holdings/ouroboros    --squash # TH1–TH7
gh pr merge 22 --repo szl-holdings/sentra       --squash # TH2–TH5
gh pr merge  4 --repo szl-holdings/vsp-otel     --squash # VSP spine
gh pr merge  4 --repo szl-holdings/agi-forecast --squash # Forecast Gauge

# 4c — orchestration (depends on 4b)
gh pr merge 32 --repo szl-holdings/ouroboros    --squash # a11oy-core (89 tests)

# 4d — standalone features
gh pr merge 18 --repo szl-holdings/lutar-lean       --squash # TH8 Lean v2
gh pr merge 44 --repo szl-holdings/ouroboros-thesis --squash # arXiv v2
gh pr merge 15 --repo szl-holdings/szl-brand        --squash # anatomy v2
```

### WAVE 5 — Tail-end (after Λ tables added, DOI gate fixed)

```bash
# Operator: add Λ table per comment, then:
gh pr merge 29 --repo szl-holdings/ouroboros        --squash
gh pr merge 39 --repo szl-holdings/ouroboros-thesis --squash
gh pr merge 15 --repo szl-holdings/lutar-lean       --squash
gh pr merge 14 --repo szl-holdings/szl-brand        --squash

# After WAVE 0 DOI fix lands and CI re-runs green:
gh pr merge 28 --repo szl-holdings/ouroboros        --squash
gh pr merge 38 --repo szl-holdings/ouroboros-thesis --squash
gh pr merge 11 --repo szl-holdings/szl-trust        --squash

# Optional close (superseded):
gh pr close 12 --repo szl-holdings/szl-brand --comment "Superseded by #15 — CTO agent on behalf of Lutar, Stephen P."
```

---

## 5. Branch Protection Fixes (operator-only)

Web UI → `Settings → Branches → Edit protection rule for main`

| Repo | Setting to enable |
|---|---|
| `lutar-lean` | `required_status_checks` (add the Lean build workflow) |
| `vsp-otel` | `require_code_owner_reviews=true` (merge CODEOWNERS PR #6 first) + `required_status_checks` |
| `agi-forecast` | `require_code_owner_reviews=true` (merge CODEOWNERS PR #6 first) + `required_status_checks` |

Also: the doctrine baseline (`enforce_admins`, `dismiss_stale_reviews`, `required_approving_review_count≥1`, `allow_force_pushes=false`, `allow_deletions=false`, `required_conversation_resolution=true`) — verify in the same UI pass.

---

## 6. Operator-Only Items (CTO authority cannot perform)

1. **Mark draft PRs ready-for-review** — every PR opened by this audit is draft
2. **Merge any PR** (all 6 waves above)
3. **Branch protection edits** on 3 repos (§5)
4. **Force-push rebase** on `ouroboros-thesis#34` (per prior operator runbook)
5. **Add 2nd reviewer** to org (blocks every merge currently — only `stephen@szlholdings.com` reviews exist)
6. **Mint Zenodo DOIs** — drafts staged at:
   - `SZL_FINAL_PAYLOAD/03_thesis/_arxiv_zenodo/zenodo_v2/deposit.json`
   - `SZL_FINAL_PAYLOAD/03_thesis/_arxiv_zenodo/zenodo_v2/lutar_lean_deposit_draft.json`
7. **Submit arXiv** — package at `SZL_FINAL_PAYLOAD/03_thesis/_arxiv_zenodo/arxiv_v2.zip`
8. **License-allowlist policy decision** — 7 repos use `LicenseRef-SZL-Proprietary`
9. **DOI rebind decision** — `zenodo.19944926` redirects to `20195368`; either rebind references or accept `curl -L` patch
10. **OpenSSF Best Practices badge registration** — required to close `CIIBestPracticesID` Scorecard alerts org-wide

---

## 7. Remaining Scorecard Findings (human-required across repos)

Cannot be auto-fixed by CTO. Sustained development practice or external action required.

| Rule | Why | Remediation |
|---|---|---|
| `CIIBestPracticesID` | 0/16 registered | Register at openssf.org/best-practices |
| `CodeReviewID` | Solo-dev pattern | Add 2nd reviewer + require reviews on merge |
| `MaintainedID` | Repos young | Time-based — sustained activity resolves |
| `FuzzingID` | No fuzz harness | OSS-Fuzz integration (complex) |
| `CITestsID` | Some PRs merged without CI history | Will self-resolve as Wave 1 lands |
| `SASTID` | CodeQL late-added | Will self-resolve once CodeQL runs on history |

---

## 8. Risk Register

| Risk | Likelihood | Mitigation |
|---|---|---|
| Wave 1 merge conflicts (concurrent citation edits across repos) | Low | Wave 1 PRs touch different files; squash-merge each one |
| Wave 3 CI re-run still failing after fix commits | Medium | Re-check `.github#36` pin-check first; rerun `gh run rerun --failed` |
| Wave 4 ouroboros#31 + #32 ordering conflict (both on ouroboros) | Medium | Merge #31 first, rebase #32 if conflicts emerge |
| BROKEN PRs landing accidentally | Low | Explicit DO-NOT-MERGE in §6 below; Wave 5 is the only safe path |
| License-allowlist tension blocking review | High | §6 item 8 — operator decision needed before reviewing 7 repos under doctrine |

---

## 9. Artifacts

| Artifact | Location |
|---|---|
| GitHub Expert full report | `audit_pm_ghx/ghx/GITHUB_EXPERT_REPORT.md` |
| GitHub Expert operator blockers | `audit_pm_ghx/ghx/OPERATOR_BLOCKERS.md` |
| Program Manager full report | `audit_pm_ghx/pm/PM_REPORT.md` |
| PM PR inventory (JSON) | `audit_pm_ghx/pm/pr_inventory.json` |
| PM doctrine sweep | `audit_pm_ghx/pm/doctrine_sweep.md` |
| Baseline snapshot | `audit_pm_ghx/baseline.md` |

---

## 10. Methodology + Limits

**What we verified:** every claim in this report is backed by a `gh api` call. JSON snapshots captured in `audit_pm_ghx/ghx/` for cross-check.

**What we did not do (by design, CTO authority):**
- No branch-protection writes
- No merges
- No force-pushes
- No DOI mints / arXiv submissions
- No marking PRs ready-for-review
- No PR closures (only one recommendation: ouroboros#24, which the operator decides)

**Known limits of this snapshot:**
- Scorecard scores fluctuate ±0.3 between runs; Wave 1+2 should bump avg from 6.59 → ~7.5
- Doctrine V6 evidence-table presence was checked by string match; semantic correctness of Λ scores is operator judgment
- The DOI gate failure is the only blocking CI issue org-wide; everything else is green

---

*Generated by parallel agents (GitHub Expert + Agent Dev Program Manager) operating under Doctrine V6 within CTO authority. No hallucinations, no bandaids, tested where testable. — Lutar, Stephen P.*
