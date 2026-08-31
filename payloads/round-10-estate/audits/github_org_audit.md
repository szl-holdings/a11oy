# GitHub Org Audit — szl-holdings

Collected: 2026-08-30 23:55 UTC · READ_ONLY · via `gh` CLI (authenticated as stephenlutar2-hash)
Org: **szl-holdings** (hyphen, NOT szlholdings) · member-confirmed

## Scale
- **100 repos** in org (95 public / 5 private per org card cross-check)
- **12 open PRs**
- **1,576 PRs merged in the last 45 days** (~35/day)
- **86 repos have CI runs**; **16 repos currently have failing recent runs**

## Casing gotcha
`szlholdings` (no hyphen) does not resolve on GitHub. The org is `szl-holdings`. Same class of bug as the HF casing gotcha — standardize both handles in every doc, link, and script.

## Open PR classification (12)

| PR | Title | CI | Approved | Risky path | Mergeable | Recommendation |
|---|---|---|---|---|---|---|
| a11oy#1540 | docs(ops): laptop-only local model wiring runbook | success | no | no | MERGEABLE | HUMAN_REQUIRED_NO_APPROVAL |
| a11oy#1537 | fix(runtime): recover tested console surfaces | success | no | no | CONFLICTING | BLOCKED_CONFLICT |
| a11oy#1535 | feat(frontier): brainanswer governed synthesis | failure | no | no | CONFLICTING | BLOCKED_CONFLICT |
| a11oy#1534 | feat(governance): round-10 truth gates + governed slice | failure | no | **YES (governance)** | MERGEABLE | HUMAN_REQUIRED |
| a11oy#1532 | chore(security): audit dependency closure | failure | no | no | MERGEABLE | BLOCKED_CI |
| a11oy#1530 | feat(frontier): brainlocal liveness surface | failure | no | no | CONFLICTING | BLOCKED_CONFLICT |
| a11oy#1529 | lexicon: 'Governed Inference' → governed agent change mgmt | failure | no | no | MERGEABLE | BLOCKED_CI |
| a11oy#1528 | fix(security): retire non-resolving szlholdings.ai | pending | no | **YES (security)** | MERGEABLE | HUMAN_REQUIRED |
| a11oy#1521 | feat(frontier): brainretro calibration surface | failure | no | no | MERGEABLE | BLOCKED_CI |
| killinchu#348 | fix(security): retire szlholdings.ai, drop phantom refs | failure | no | **YES (security)** | MERGEABLE | HUMAN_REQUIRED |
| governance-as-code#1 | chore(legal): add Apache-2.0 LICENSE + NOTICE | failure | no | no | MERGEABLE | BLOCKED_CI |
| szl-gov#1 | chore(legal): add Apache-2.0 LICENSE + NOTICE | failure | no | no | CONFLICTING | BLOCKED_CONFLICT |

## Zero AUTO_ELIGIBLE
No PR is auto-eligible. None are approved (solo founder — expected). Three touch governed/security paths and are HUMAN_REQUIRED regardless of CI. Four are blocked purely by failing CI. Three have merge conflicts.

## Repos with failing recent CI (16)
khipu-pages (3/3) · szl-organ-integrity (3/3) · governance-as-code (2/3) · szl-frontier (2/3) · szl-kernels-live (2/3) · szl-provctl-live (2/3) · lambda-gate-holo (2/3) · and 9 more at 1/3.

## Notable
`a11oy#1534` is Codex actively building this thread's round-10 truth gates. This payload is designed to land alongside it — do not merge #1534 automatically (governance path = HUMAN_REQUIRED by law).
