# Post-merge #1986 review repair workcell

- `workcell_id`: `A11OY-1986-POSTMERGE-REVIEW-REPAIR-20260905`
- `source_base`: `94e129d016a7e82e0b22f11c00ea877b5cc430f5`
- `state`: `IMPLEMENTED_PENDING_EXACT_HEAD_CI`
- `objective`: close four substantive Codex findings that remained after PR #1986 merged.

## Required repairs

1. Bind nested `agent.nexus` request/program metadata to the current request and reject conflicting duplicate bindings before any `SEALED` verdict.
2. Serialize every `_do_run` mutation of the shared `_RUN_CHAIN`, including `/agent/run` and governed-cycle callers, so the lineage cannot fork under concurrency.
3. Preserve the protected Ouroboros endpoint while making the registered UI able to send operator bearer authority without persisting or exposing credentials.
4. Report the actual successful `verified_by_keyid` across receipt-key rotation instead of attributing verification to the current active key.

## Acceptance

- Add focused adversarial regressions for all four defects.
- Existing authentication, source-binding, receipt-verification, and no-external-effector boundaries remain fail closed.
- Exact-head hosted tests, security checks, and independent Codex review must be green before merge.
- No provider mutation, secret-value readback, protection weakening, force push, or direct-main write is authorized.

This file is the append-only workcell/proof anchor. Implementation evidence is completed in the protected successor PR.

## Forward implementation

The current-main successor now carries the four forward fixes:

- nested `agent.nexus` binding is authoritative and conflicting duplicates fail closed;
- every shared run-ledger append is serialized through one lock-protected primitive;
- the registered Ouroboros UI sends a session-only bearer credential and clears it after the request;
- rotated-key verification records the successful `verified_by_keyid`.

Focused adversarial regressions are in
`tests/test_post_merge_1986_review_repairs.py`. This state is not a merge or
deployment claim; exact-head CI and independent review remain required.
