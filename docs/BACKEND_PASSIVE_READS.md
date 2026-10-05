# Passive backend reads

The backend registers GET and explicit HEAD for
`/api/a11oy/v1/assurance/attest`, its `/status` subpath, and
`/api/a11oy/v1/energy/cheapest-watt`. These responses observe existing state.
They return `dsse: null`, `signed: false`, `receipt_minted: false`, and
`export_read_only: true`, with `Cache-Control: no-store`.
The export also carries `retained_signature_verified: false` and
`retained_attestation_state: UNKNOWN`. These describe this read's evidence;
historical decision payloads are preserved without changing their fields.

The attestation routes expose an unsigned current receipt-chain observation.
They do not mint a new signature or retrieve a previously signed attestation.
Signing capability remains `UNKNOWN` (`signing_available: null`), because
inspecting the shared signing-key loader can provision a fallback identity.
SQLite reads use a read-only connection. Missing or malformed receipt storage
returns HTTP 503 without creating a replacement; an existing broken chain stays
visible with `chain_ok: false`. This observation grants no authorization.
The retained runtime axis is true only when this backend chain diagnostic
verifies successfully. It is not an independent runtime, source, or signature
proof, and a broken chain keeps that axis false.

WAL-mode receipt storage returns an unsigned HTTP 503 before SQLite is opened.
This scoped observer cannot guarantee that a WAL read leaves its sidecars
unchanged, and it does not use an immutable connection that disables locking and
change detection on a mutable store. Tests include an uncheckpointed receipt in
actual WAL mode with existing sidecars and
with sidecars absent, comparing all directory entries and their bytes after
each read. Existing writers keep their journal-mode behavior. See SQLite's
[WAL read-only rules](https://sqlite.org/wal.html#read_only_databases) and
[database header format](https://sqlite.org/fileformat.html#file_format_version_numbers),
and [immutable URI semantics](https://sqlite.org/uri.html#uriimmutable).
The header check and read run under the store's process-local lock. Concurrent
journal-mode changes by another process remain `UNKNOWN`; these local tests do
not establish an absolute guarantee against an external writer.

The placement route reads an already loaded module and an already existing
placement ledger. It does not import or activate the optional energy module,
construct a ledger, inspect or start an operator, append a decision, or sign.
`latest_decision` contains an existing raw decision payload or null. It does
not claim a retained DSSE envelope. An absent ledger is `UNAVAILABLE`, an empty
existing ledger is `EMPTY`, and malformed existing state returns an unsigned
HTTP 503. Existing sample or measurement labels are retained; no new physical
measurement is made by these reads.

Existing explicit receipt writers and direct signing APIs retain their behavior.
Clients that previously relied on GET minting must use an existing authorized
writer and its actual export contract. The artifact endpoint remains build and
image metadata with external verification pointers.

Run the served-route, SQLite, writer, security, and limiter regressions:

```bash
python -m pytest -q tests/test_be_hardening.py tests/test_dsse_real_signing.py -k "not real_org_key"
```

The tests use an actual hardened FastAPI app, a real test-owned SQLite store,
offline placement fixtures, and explicit traps for signing, key loading,
activation, receipt writing, and network calls. They check first route matching,
repeated GET/HEAD requests, file and memory stability, absent and malformed
state, and a positive explicit receipt write. This establishes source behavior
under that harness. Protected merge, Hub publication, deployed runtime parity,
and independent witness remain separate evidence states.
