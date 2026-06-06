# UDS-Mesh Conformance Suite

`pytest mesh/conformance/ -v`

Validates, with zero required dependencies (PyYAML used if present):

| Group | Checks |
|---|---|
| Schema integrity | all 5 organ schemas exist, parse as YAML, declare a `version` and `schema_url` |
| Span-name coverage | each schema declares its 3 span names (`*.lambda`, `*.evaluate`, …) |
| Cross-organ envelope | every schema carries the identical `szl.mesh.*` governance envelope (`organ`, `receipt_hash`, `dsse_payload_type`, `lambda_value`, `governance_drift`) |
| SDK ↔ schema | `mesh/sdk/mesh.py` emits spans whose names + attributes are accepted by the matching schema; unknown organ/span names are rejected |
| BLS batch receipts | aggregate verification round-trips and detects tampering (lutar-lean #180 `aggregate_verify`) |
| W3C Trace Context | `traceparent` parse/format round-trips; all-zero ids rejected |

**33 tests, all passing** as of the make-real strike (2026-06-03).

The suite is the executable definition of "a span conforms to the mesh." CI runs
it on every push (see `.github/workflows/tests.yml`). It is the production-parity
gate referenced in the repo README: a schema change that breaks cross-organ
correlation fails here.
