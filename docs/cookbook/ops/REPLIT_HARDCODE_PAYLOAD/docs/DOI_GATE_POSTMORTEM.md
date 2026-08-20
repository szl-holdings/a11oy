# DOI-Title Gate Postmortem

## Symptom

The `doi-title-gate` workflow on `ouroboros`, `ouroboros-thesis`, and `szl-trust` was failing on every PR that touched `CITATION.cff` or workflow files. CI output: `parse error: Invalid numeric literal at line 1, column 8`.

## Root cause

The gate ran:

```bash
curl -sS "https://zenodo.org/api/records/$DOI" | jq '.metadata.title'
```

For **concept DOIs** (the umbrella DOI that always points to the latest version), Zenodo responds with **HTTP 302** redirecting to the versioned record URL — and the body is **HTML** ("Found. Redirecting to /api/records/20195368"), not JSON. `curl -sS` does not follow redirects by default, so `jq` got HTML and failed.

Example:
- Concept DOI: `19944926`
- `GET /api/records/19944926` → 302 → `/api/records/20195368`
- Versioned record: `20195368` returns JSON with `metadata.title`

## Fix

Three changes in `.github/workflows/doi-title-gate.yml`:

1. **Follow redirects + force JSON:**
   ```bash
   curl -sSL -H "Accept: application/json" "https://zenodo.org/api/records/$DOI"
   ```

2. **SHA-pin `actions/checkout`** to v4.1.1 (`b4ffde65f46336ab88eb53be808477a3936bae11`) — required by Scorecard PinnedDependencies rule.

3. **SPDX header** at top: `# SPDX-License-Identifier: Apache-2.0`.

The fixed workflow is in `doi-title-gate.fixed.yml` (golden copy in this directory).

## Verification

```bash
./scripts/verify_doi_gate_fix.sh
```

This does three things:
1. Confirms each of the 3 PRs has the expected fix commit (`7d8f1f3`, `c32321f`, `e0e6893`).
2. Runs the same `curl -sSL -H "Accept: application/json"` against concept DOI `19944926` and confirms `.metadata.title` parses.
3. Reports current CI rollup on each PR.

## PR landing

| Repo | PR | Commit | CI |
|------|----|--------|----|
| ouroboros | #28 | `7d8f1f3` | ✅ passed |
| ouroboros-thesis | #38 | `c32321f` | ✅ passed |
| szl-trust | #11 | `e0e6893` | ❌ failing (different root cause) |

## szl-trust#11 follow-up

`szl-trust` references a **different** concept DOI (`19944926` → currently bound to `20195368`). The title returned from Zenodo no longer matches the title declared in `CITATION.cff` because the deposit metadata diverged. The gate is now working correctly — it's catching a real metadata drift.

**Operator action:** rebind the DOI or update `CITATION.cff` so they match.
