# Demo-Freeze Hotfix Procedure — a11oy

> Author: Yachay <yachay@szlholdings.dev> · Doctrine v11 LOCKED (749/14/163) · cosign keyid: szlholdings-cosign
> Freeze window: **2026-06-09 .. 2026-06-20 (UTC)**. During this window the
> `demo-freeze` CI gate REJECTS any push/PR whose branch is not `hotfix/*`.

## The only permitted write path during the freeze

```bash
# 1. branch off main with a hotfix/ prefix (CI gate only allows hotfix/*)
git checkout main && git pull
git checkout -b hotfix/<short-issue-slug>

# 2. make the smallest possible fix, then ONE signed commit.
#    The commit message MUST contain the literal tag [demo-hotfix] AND an issue ref.
git add -p
git commit -s -m "fix(a11oy): <one-line summary> [demo-hotfix]

Fixes #<issue-number>.
<why this is demo-critical, in one or two lines>"

# 3. open a PR into main. Two checks must pass:
#      demo-freeze / guard            -> branch is hotfix/*  ✅
#      demo-freeze-hotfix-validate    -> single signed commit, [demo-hotfix], issue ref, DCO  ✅
gh pr create --base main --head hotfix/<short-issue-slug> --fill

# 4. AUTO-MERGE rule: between T-7 (2026-06-09) and T+0, ONLY hotfix/* PRs merge.
```

## If the hotfix goes wrong — roll back the live Space

```bash
HF_TOKEN=<write-token> ops/demo-freeze/rollback.sh
# resets SZLHOLDINGS/a11oy to frozen baseline HF SHA a436bebd551d2221348b99e29d9ea6c1b0311402
```

## Hard rules (CI-enforced, not advisory)
- branch name **must** match `hotfix/*`
- PR **must** be a **single** commit (squash if needed)
- commit message **must** contain `[demo-hotfix]`
- commit message **must** reference an issue (`#123`, `fixes #123`, …)
- commit **must** be DCO-signed (`git commit -s`)

## Frozen baseline (tag `demo-freeze-baseline-2026-06-09`)
- HF Space  `SZLHOLDINGS/a11oy` @ `a436bebd551d2221348b99e29d9ea6c1b0311402`
- GitHub    `szl-holdings/a11oy` @ `c0c4ad164ccb258f34cea7b433fd4bf27cc6120d`
