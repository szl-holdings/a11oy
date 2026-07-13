# M1 gate verification report

Local verification for branch `codex/m1-operational-gate-wave22`.

## Passing checks

- Python compile: `szl_m1_model_gate.py` and
  `szl_m1_corpus_manifest.py` pass `py_compile`.
- Focused gate suite: 10 tests cover exact artifact/evidence admission,
  provider and GPU refusal, production-tier refusal, bounded inference,
  tampered adapter refusal, tampered corpus refusal, route order, Docker
  packaging, page/API security headers, and the committed full-corpus counts.
- Adjacent suite: 68 tests pass across M1, Brain corpus, numerics adapter and
  routes, formal conjecture lab, route parity, and runtime-gap contracts.
- Brain graph self-test: 9,462 nodes, 4,227 distinct artifacts, 5,235 person
  metadata nodes, 14,229 links, and eight locked formulas pass all invariants.
- Deterministic rebuild: the corpus manifest and both ledgers reproduce the
  same SHA-256 values:

  - corpus manifest: `1349828f5b9af5949e4d31d582abffe0b75e37c1708bb1b2127021c8055d5f6d`
  - Brain ledger: `8a0c82f8745c8b80ccb161e19ba625d3433219eacba4126fc3262a60758e74e5`
  - formula ledger: `028ff018a9574af2356b23ac581c1eb4087c170e689ca221fdb59ace4cae63a8`

## Known test-host limitation

`tests/test_security_headers.py` reports 8 failures and 3 passes on this
Windows worktree. All eight failures occur before header assertions because
the legacy `/console`, `/determinacy`, and `/signature-is-not-proof` handlers
look for the Docker-only absolute file `\\app\\static\\index.html` and return
500 when it is absent. `serve.py` defines that path at module lines 81-83; this
behavior predates and is independent of M1.

The new `/models/m1` and `/api/a11oy/v1/models/m1` surfaces are tested directly
and return 200 with `nosniff`, strict-origin referrer policy, HSTS, and the
enforced `frame-ancestors` policy. No legacy static-path behavior was changed in
this isolated wave.

## Non-claims

No model was trained, promoted, uploaded, deployed, or published. The live
operator still needs the exact local artifacts, runtime packages, provider
identity, and a GPU that passes admission. Missing or saturated resources remain
structured `BLOCKED` / `UNAVAILABLE`, never a green production label.

The final local probe against the exact cached base and adapter verified all
9/9 base files, 6/6 adapter files, 6/6 tokenizer files, training lineage,
offline reload, metadata, and both corpus ledgers. Runtime admission remained
`BLOCKED`: the bounded verification interpreter did not expose the local
`torch` / `transformers` / `peft` stack, and GPU 0 measured 6,473 MiB free, 5%
utilization, but 82 C against the fixed 75 C ceiling. No inference was attempted.
