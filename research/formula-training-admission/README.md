# Formula training-data admission tranche

This directory is a deterministic, local-only admission result. It follows the
A11oy evidence path:

`DORMANT_RAW -> NORMALIZED_ARTIFACT -> FORMULA_LINK -> ADMISSION_DECISION -> QUERY_READY_CONTEXT`

The result is deliberately holdout-only. The current Brain has 9,464 raw nodes,
while the historical M1 ledger has 9,462 rows. All 9,464 raw nodes remain
quarantined and zero raw-node text rows are emitted.

The critical crosswalk finding is that `F1` through `F23` are reused by two
different namespaces:

- `puriq-runtime-registry` contains executable numerical/runtime claims.
- `puriq-lean-proof-pack` contains operational Lean/thesis claims.

Matching IDs do not mean matching statements. Proof credit never crosses that
boundary without an explicit semantic binding. The status vocabulary is
`KERNEL_ACCEPTED`, `CONDITIONAL`, `OPEN`, and `REFUTED`; executable is a separate
axis and never implies proof.

The two SZL-Lake examples remain evaluation-only with proof status
`NOT_EVALUATED`. The five-document canonical Brain index remains query-ready for
the committed retrieval pilot but is not training-eligible. No latency was
recorded by that pilot, so latency is `NOT_EVALUATED`; no two-second or other
response-time claim is made.

Rebuild and verify:

```powershell
python .\szl_formula_training_admission.py --write
python .\szl_formula_training_admission.py --verify
python -m pytest -q tests\test_formula_training_admission.py
```

No network call, model training, promotion, signing, or external mutation is
performed.
