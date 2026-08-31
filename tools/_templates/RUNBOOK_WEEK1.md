# Week 1 runbook: from bootstrap to gates green

Truth state of this document: VERIFIED as a procedure as of 2026-08-30; the
outcomes it describes become VERIFIED only when the gates report them.

## Day 1 — bootstrap

1. `python3 tools/szl_master_bootstrap.py --run` (idempotent; safe to re-run).
2. `python3 tools/lexicon_gate.py` — expected exit 1. The single finding is
   the seeded footnote in `docs/positioning/AUTO_REVIEW_DELTA.md` that quotes
   the banned compliance phrase to prove the gate has teeth.
3. `python3 tools/release_gate.py` — expected exit 1. All 24
   COMMERCIAL_LEDGER rows are UNKNOWN with `blocks_raise: true`. This is the
   honest Week 1 state, not a bug.
4. `python3 tools/demo_harness.py` — expected exit 0, 12/12 PASS.

## Day 2 — lexicon gate green

1. Delete the "Seeded gate test" footnote from
   `docs/positioning/AUTO_REVIEW_DELTA.md`. The banned-phrase canon lives only
   in `tools/lexicon_gate.py`; docs reference it by pointer.
2. Re-run `python3 tools/lexicon_gate.py` — expected exit 0.
3. Wire both gates into CI so every pull request runs them.

Notes on mechanics: bootstrap treats README.md, docs/RUNBOOK_WEEK1.md, and
docs/positioning/AUTO_REVIEW_DELTA.md as seed documents — it creates them
once and never overwrites your edits on re-runs. The copies under
`tools/_templates/` are bootstrap sources: they retain the seeded footnote
(so every fresh scaffold reproduces the Week 1 red state) and are excluded
from the gate's own scan because each template is scanned where it lands.

## Ongoing — release gate (reviewed weekly, red by design until earned)

A COMMERCIAL_LEDGER row stops blocking a raise only when it is VERIFIED:

1. Attach a real evidence entry to the row:
   `evidence:` gains a list item with `kind`, `ref`, `note`, and
   `status: supports`. Evidence must be a durable artifact (billing export,
   signed contract, counsel letter, audit output) — never a prose claim.
2. Set `state: VERIFIED` and record the value that the evidence proves.
3. `python3 tools/release_gate.py --apply` demotes any VERIFIED claim in
   claims-ledger.yaml that lost its evidence (Zero-Bandaid auto-demotion).
4. Exit 0 requires every `blocks_raise: true` row VERIFIED with supporting
   evidence. Until then the company cannot honestly raise. That is the point.

## After gates green — customer slice only

Week 1 ends the bootstrap. From then on, only the locked wedge ships:
governed agent change management, end to end, for real customers. Everything
on the v1 exclusions list (CANON section 11) stays unbuilt.
