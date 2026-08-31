# Proposed HF org card (spaces/SZLHOLDINGS/README · README.md)

Status: **BLOCKED — not applied.** The 2026-08-31 audit token held
`read-repos` + `contribute-repos` OAuth scopes; both direct commit and
`--create-pr` against `hf://spaces/SZLHOLDINGS/README` were refused
(403 on preupload). Org-space writes need a token with explicit write
scope for the SZLHOLDINGS org. Apply by pasting the block below over the
current README.md, or re-run with a write-scoped token.

## What changes and why (measured 2026-08-31T21Z)

| Row | Card says | Measured | Method |
|---|---|---|---|
| Spaces | 47 · 47 public | **48 total · 34 public · 14 private** | authenticated enumerate (48) minus public API (34) |
| GitHub repos | 100 · 95 public · 5 private | **103 · 95 public · 8 private · 35 archived** | gh api org repo list, full |
| Models | 44 public | 44 public · all license-tagged | Hub API full=true — VERIFIED, no change |
| Datasets | 38 · 30 public · 8 private | 38 · 30 public · 8 private | Hub API — VERIFIED, no change |
| Audit line | "signed its own receipt" | receipt is **UNSIGNED**, verdict INCOMPLETE | auditor holds no org signing key — the claim must say so |

The "47 public" figure could not be reproduced by either enumeration path
and is replaced, not patched over. Runtime stage remains UNAVAILABLE via
read API and is not evidence of a deployed revision.
