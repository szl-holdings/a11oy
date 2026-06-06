# CTO Authority Boundary

The agents that produced this payload operate under **Doctrine V6 CTO authority**. This file is the canonical authority table — if a script attempts something not on the CAN list, it should refuse.

## CAN (CTO authority)

- Open **draft** PRs
- Commit + push to feature branches
- Comment on PRs and issues
- Close superseded PRs with a comment linking the superseder
- Add labels
- Request CI re-runs via `gh api /repos/{}/{}/actions/runs/{}/rerun`
- Verify checksums + Λ tables in PR bodies
- Run any read-only API (`gh api GET …`)

## CANNOT (operator-only)

- Force-push (rebase, amend on shared branches)
- Edit branch protection
- Mark draft PRs as ready-for-review
- Merge anything
- Mint Zenodo DOIs (operator approval required for permanent identifiers)
- Submit to arXiv
- Publish npm / publish releases
- Delete branches, PRs, repos, or releases
- Change org / profile / scheduled tasks (crons)
- Spend money
- Hand out credentials
- Modify SPDX license headers without operator sign-off
- Change canonical author / email / ORCID

## How `merge_wave.sh` enforces this

The script's first check is:

```bash
if [ "$OPERATOR" -ne 1 ]; then
  err "Refusing to run. CTO authority does not include merging."
  exit 1
fi
```

Even with `--i-am-the-operator`, it defaults to **dry-run** unless `--execute` is also passed.

## Canonical identity (immutable)

```
Author name : Stephen P. Lutar Jr.
Author email: stephen@szlholdings.com
ORCID       : 0009-0001-0110-4173
Org         : SZL Holdings
GitHub login: stephenlutar2-hash
```

Doctrine note: "Jr." appears **only** in the git author field. In prose, the canonical form is "Stephen P. Lutar." Forbidden variants: "Stephen Paul" (anywhere), "Lutar Jr." (in prose), "anonymous."

## Forbidden patterns (V6)

These must not appear in any PR title, body, commit message, or pushed file:

```
AlloyScape
Glass Wing
Glasswing
Mythos
Stephen Paul
Perplexity Computer
anonymous
```

`check_doctrine.sh` scans for these case-insensitively across `title + body + commits[].messageHeadline + diff`.
