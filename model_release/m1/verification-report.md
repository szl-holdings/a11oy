# M1 gate verification report

Local reconciliation verification for branch `codex/operational-union-wave23`.

## Passing checks

- Python compile: `szl_m1_model_gate.py` and
  `szl_m1_corpus_manifest.py` pass `py_compile`.
- Focused corpus-gate verification parses every committed ledger row, verifies
  the exact evidence hashes, and returns `PASS` for the M1 corpus receipt chain.
- Formula-admission reconciliation: all 7 dependency-light focused tests pass,
  including byte-for-byte artifact rebuild and zero raw-node training rows.
- Brain graph self-test: 9,464 nodes, 4,229 distinct artifacts, 5,235 person
  metadata nodes, 14,234 links, and eight locked formulas pass all invariants.
- Raw-graph admission is fail-closed: 9,464 of 9,464 Brain rows are
  quarantined, and zero raw graph rows are training-eligible. Canonical
  evidence admission remains a separate, receipted process.
- Deterministic rebuild: the corpus manifest and both ledgers reproduce the
  same SHA-256 values:

  - corpus manifest: `6f5e0d9ecb60d8aa52fc229a42ad37d62fc7fa7406993a0b8352b2b574fb40a4`
  - Brain ledger: `c9c96e62f047de72c8cfd7daa560bd2bb69e86fd84fbd1635c3cd812b9c5946d`
  - formula ledger: `028ff018a9574af2356b23ac581c1eb4087c170e689ca221fdb59ace4cae63a8`

## Known test-host limitation

The permitted bundled Python runtime on this Windows worktree does not include
`pytest`, FastAPI, or Starlette. The full HTTP/route suite was therefore not
re-run in this reconciliation. Dependency-light generator, hash-chain,
per-row quarantine, deterministic-rebuild, and formula-admission checks were
run directly; route behavior is not newly claimed by this report.

## Non-claims

No model was trained, promoted, uploaded, deployed, or published. The live
operator still needs the exact local artifacts, runtime packages, provider
identity, and a GPU that passes admission. Missing or saturated resources remain
structured `BLOCKED` / `UNAVAILABLE`, never a green production label.

This reconciliation did not load the adapter or attempt inference. Runtime
admission remains independently gated on the exact local artifacts, PEFT
runtime, provider identity, and a fresh GPU measurement. No prior runtime
receipt is upgraded by the corpus alignment.
