# Brain vertical slice plan

## Slice 1 — honest capabilities manifest

- Add `/api/a11oy/v1/brain/capabilities`.
- Add `execution/brain/CLAIM_EVIDENCE_LEDGER.csv`.
- Keep all model/training claims UNAVAILABLE until receipts exist.
- Frontend consumes statuses instead of hard-coded green labels.

## Slice 2 — durable event memory

- Ingest one real GitHub PR event.
- Store source URL, commit SHA, checks, author, review state, and outcome.
- Emit a replayable content digest.
- Keep signature state explicit: unsigned until approved signing is wired.

## Slice 3 — improvement proposal loop

- Retrieve related graph/memory nodes.
- Generate a bounded proposal with evidence and expected tests.
- Run sandbox checks.
- Open a human-governed PR; never bypass required review.

## Slice 4 — model admission

- Publish weight SHA, license, training/eval receipt, and smoke-test output.
- Admit model only after repeatable evals and license review.
- Promote from UNAVAILABLE/SIMULATED only when the evidence ledger supports it.
