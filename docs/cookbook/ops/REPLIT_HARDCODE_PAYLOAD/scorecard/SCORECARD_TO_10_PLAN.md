# OpenSSF Scorecard → 10/10 Plan

**Operator:** Stephen P. Lutar Jr. — `stephen@szlholdings.com` — ORCID `0009-0001-0110-4173` — SZL Holdings
**Date:** 2026-05-16
**Scope:** 14 public szl-holdings repos
**Baseline:** avg 6.78/10 (range: .github 6.5 → lutar-lean 7.1)

---

## The 9 rules and what closes them (honest)

| Rule | Severity | Org-wide count | Authority needed | What actually closes it |
|------|----------|----------------|------------------|-------------------------|
| MaintainedID | high | 14/14 | **time** | Repos created <90 days ago. **Self-resolves** when repos cross 90-day age (most repos by mid-2026). |
| CodeReviewID | high | 14/14 | **operator + team** | "0/23 approved changesets" — needs second reviewer on every PR. CTO cannot self-approve. |
| FuzzingID | medium | 14/14 | **CTO + operator decision** | Add `.github/workflows/fuzzing.yml` (ClusterFuzzLite). Only meaningful for code-bearing repos. For doc-only repos (szl-brand, szl-cookbook, ouroboros-thesis, .github), the honest answer is to document N/A in SECURITY.md. |
| SASTID | medium | 13/14 | **CTO** | "SAST tool detected but not run on all commits — 12 of 18". Resolves as new commits trigger CodeQL. **Self-resolves with merge activity.** |
| CIIBestPracticesID | low | 14/14 | **operator-only** | Register each repo at <https://www.bestpractices.coreinfrastructure.org/>. Manual web form per repo. CTO has no API for this. |
| BranchProtectionID | high | 10/14 | **operator-only** | Need to: (a) enable `enforce_admins`, (b) raise required_approving_review_count to 2, (c) enable last_push_approval, (d) require up-to-date branches. CTO does not have admin BP authority. |
| CITestsID | low | 9/14 | **CTO + time** | "16 out of 18 merged PRs checked by CI". Self-resolves as more PRs flow through with passing CI. |
| PinnedDependenciesID | low | 8/14 | **CTO** | Already has 4 open scorecard-fix PRs (lutar-lean#19, szl-trust#13, szl-cookbook#12, szl-brand#16). Operator needs to merge them. |
| TokenPermissionsID | low | 5/14 | **CTO** | Already addressed in `.github` PR #37 (harden-runner bump). Operator needs to merge. |

---

## What gets you to 10/10 (operator path)

For each of the 14 repos:

1. **Register OpenSSF Best Practices badge** → <https://www.bestpractices.coreinfrastructure.org/>. 14 separate registrations. Each one is ~10 minutes of form-filling. Closes CIIBestPracticesID instantly.

2. **Branch protection upgrade** (operator-only authority):
   ```bash
   gh api -X PUT /repos/szl-holdings/$repo/branches/main/protection \
     -f required_status_checks.strict=true \
     -F enforce_admins=true \
     -F required_pull_request_reviews.required_approving_review_count=2 \
     -F required_pull_request_reviews.dismiss_stale_reviews=true \
     -F required_pull_request_reviews.require_code_owner_reviews=true \
     -F required_pull_request_reviews.require_last_push_approval=true \
     -F allow_force_pushes=false \
     -F allow_deletions=false \
     -F required_conversation_resolution=true
   ```
   Closes BranchProtectionID.

3. **Merge the 4 open PinnedDependenciesID PRs**:
   - lutar-lean#19, szl-trust#13, szl-cookbook#12, szl-brand#16

4. **Merge .github#37** (TokenPermissions + harden-runner bump). This is the biggest single lever — the `.github` repo's reusable workflows cascade to all 14 repos.

5. **Add fuzzing only where it makes sense** (3 repos with substantive TS code):
   - ouroboros (the runtime)
   - sentra (when implemented)
   - a11oy (when implemented)

   For the other 11 repos, add a SECURITY.md note marking fuzzing N/A (e.g., docs-only, brand assets, schema-only).

6. **Time-based** (no action needed):
   - MaintainedID self-resolves at 90 days
   - SASTID self-resolves with CI activity
   - CITestsID self-resolves with passing PRs

---

## Projected score after operator actions

| Repo | Now | After badge | After BP | After pin-PRs merged | After .github#37 merged | Target |
|------|-----|-------------|----------|----------------------|-------------------------|--------|
| amaru | 6.8 | 7.8 | 8.8 | — | 9.3 | **9.3** |
| a11oy | 6.8 | 7.8 | 8.8 | — | 9.3 | **9.3** |
| sentra | 6.8 | 7.8 | 8.8 | — | 9.3 | **9.3** |
| terra | 6.8 | 7.8 | 8.8 | — | 9.3 | **9.3** |
| vessels | 6.8 | 7.8 | 8.8 | — | 9.3 | **9.3** |
| counsel | 6.8 | 7.8 | 8.8 | — | 9.3 | **9.3** |
| carlota-jo | 6.8 | 7.8 | 8.8 | — | 9.3 | **9.3** |
| ouroboros | 6.8 | 7.8 | 8.8 | — | 9.3 | **9.3** |
| ouroboros-thesis | 6.7 | 7.7 | 8.7 | — | 9.2 | **9.2** |
| lutar-lean | 7.1 | 8.1 | 9.1 | 9.5 | 9.7 | **9.7** |
| szl-trust | 6.9 | 7.9 | 8.9 | 9.3 | 9.5 | **9.5** |
| szl-cookbook | 6.9 | 7.9 | 8.9 | 9.3 | 9.5 | **9.5** |
| szl-brand | 6.9 | 7.9 | 8.9 | 9.3 | 9.5 | **9.5** |
| .github | 6.5 | 7.5 | 8.5 | — | 9.0 | **9.0** |

Org average target: **~9.4/10** with operator actions; remaining 0.6 requires time-based items to resolve (MaintainedID at 90 days, SASTID/CITestsID with merge activity).

**Pure 10/10** requires all of the above PLUS fuzzing in code-bearing repos PLUS sustained code-review velocity over many PRs (CodeReviewID needs the merged-PR ratio to climb).

---

## What the CTO did do (Doctrine V6 sweep 2)

- Captured Scorecard baseline for all 14 repos
- Built per-rule alert inventory (`scorecard_alerts_by_rule.csv`)
- Inventoried 36 existing `scorecard-fix/*` branches (created by Scorecard Remediate cron but empty — need real commits)
- Confirmed scanners are 100% **OpenSSF Scorecard**, not external attackers
- Confirmed 0 critical alerts, 0 Dependabot high/critical, 0 secret-scan alerts across all 14 repos

## Scanner identity verification

Every code-scanning alert across the org is from `Scorecard` (OpenSSF). This is **your own configured workflow**, not external traffic. Cross-verified: BP is `Y` on all 14 repos, secret scanning is clean, Dependabot is clean. The "scans" you saw are normal supply-chain auditing from your own CI.

---

## TL;DR for the operator

**Stop reading. Do these 4 things, in order:**

1. Merge **`.github#37`** (closes TokenPermissionsID across many repos via reusable workflows)
2. Merge **4 pin-bump PRs** (lutar-lean#19, szl-trust#13, szl-cookbook#12, szl-brand#16)
3. Run the branch-protection script above for all 14 repos (one-time, ~5 min)
4. Register 14 OpenSSF Best Practices badges (~2 hours total, manual web forms)

After step 4, expected org avg = **9.4/10**. Pure 10/10 requires sustained merge activity over the next 60 days for the time-based rules to converge.

Author: Stephen P. Lutar Jr. — `stephen@szlholdings.com` — SZL Holdings
