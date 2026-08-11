# Acceptance manifest

This file is the canonical checklist for the local spin-up.

1. Claim lint pass
2. Receipt schema parse + field coverage
3. Offline signature verification
4. Counterfactual replay fixture exists and is tied to an auditable policy
5. Semantic run diff fixture exists (placeholder artifact + hash)
6. Decision transparency log fixture exists
7. Evidence economics placeholder exists
8. Frontier spin-up probe (`scripts/frontier_spin.py`) runs and writes both `frontier_snapshot_*.json` and `frontier_report_*.md` in `outputs/`.
9. Workflow guard: `.github/workflows/frontier-spin.yml` exists and references the same probe for ongoing operational evidence.

All steps must pass before release promotion.
