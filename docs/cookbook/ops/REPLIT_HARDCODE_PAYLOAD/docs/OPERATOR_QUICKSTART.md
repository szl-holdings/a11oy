# Operator Quickstart

For Stephen P. Lutar Jr., once this payload is running on Replit.

## 30-second sanity check

```bash
./bootstrap.sh         # dashboard + prereq check
./scripts/verify_all.sh
```

If both exit 0, the org is in the state described in `data/cto_prs_opened_recent.json` and the doctrine sweep is clean.

## Daily ops

```bash
./scripts/pull_pr_state.sh        # refresh PR snapshot (cheap)
./scripts/check_ci_status.sh      # which PRs are red?
./scripts/check_doctrine.sh       # any V6 violations introduced?
```

## When you're ready to merge

The 5-wave plan is canonical: read `UNIFIED_OPERATOR_HANDOFF.md` first.

```bash
# Always dry-run first
./scripts/merge_wave.sh --wave 1 --i-am-the-operator

# Then execute when satisfied
./scripts/merge_wave.sh --wave 1 --i-am-the-operator --execute
```

Wave order:
1. **Hygiene** (41 PRs) — CODEOWNERS, dependabot, CITATION fixes, license headers
2. **Scorecard / security** (11 PRs) — harden-runner bumps, SHA pins, TokenPermissions
3. **CI wire** (3 PRs) — `.github/workflows/ci.yml` baseline on new repos
4. **Fly V9 fleet** (9 PRs) — the substantive feature work
5. **Tail-end** (6 PRs) — anatomy + DOI gate + thesis arxiv

## Before you call any wave done

```bash
./scripts/verify_all.sh
```

It re-pulls live state. If it's red, do not advance.

## Operator-only items still blocked (need your manual action)

1. Mark all draft PRs ready-for-review (CTO cannot)
2. Branch-protection upgrades on `lutar-lean`, `vsp-otel`, `agi-forecast`
3. Force-push rebase on `ouroboros-thesis#34`
4. Add a 2nd reviewer to unblock all merges
5. Mint Zenodo DOIs from `_arxiv_zenodo/zenodo_v2/{deposit,lutar_lean_deposit_draft}.json`
6. Submit arXiv from `_arxiv_zenodo/arxiv_v2.zip`
7. License-allowlist policy decision: 7 repos currently use `LicenseRef-SZL-Proprietary` (amaru, a11oy, sentra, terra, vessels, counsel, carlota-jo)
8. DOI rebind for `szl-trust#11` (concept `zenodo.19944926` → versioned `20195368`)
9. OpenSSF Best Practices badge registration

## If something goes wrong

- **gh auth expired:** `gh auth login --git-protocol https --web`
- **Rate-limited:** `gh api rate_limit` to confirm; wait, then re-run
- **Stale PR data:** `./scripts/pull_pr_state.sh` always re-fetches
- **Need to inspect a specific PR:** `gh pr view <N> --repo szl-holdings/<repo> --web`

## Where reports go

`./out/` — overwritten by each run.
- `verify_all_summary.md`
- `ci_status.md` + `ci_status.json`
- `doctrine_report.md`
- `anatomy_verify.md`
- `doi_gate_verify.md`
- `zenodo_doi_status.md`
