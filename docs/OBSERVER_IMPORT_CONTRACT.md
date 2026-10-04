<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Observer offline import and report contract

Status: local implementation, not an A11oy route or a production release.
Taxonomy: services/provenance. No listener, authentication store, network client,
provider action, signing, training, or persistence is created.

The shared kernel now has a bounded JSON adapter and a script-free HTML report.
It is independently implemented; no BOb code, branding, or assets are included.
Existing eight locked formulas are untouched. Median/MAD is descriptive ranking,
not a new locked formula, calibrated probability, or domain approval.

## Input

Send UTF-8 JSON bytes to `evaluate_import(raw)`, or to stdin of
`python -m scripts.review_observer_import` from the repository root. Add `--html`
to emit the read-only report instead of JSON. The CLI writes only stdout; it
does not open input paths or create output files. HTML is emitted as explicit
UTF-8 bytes even when Windows stdout defaults to another code page. Exit 0 means RANKED locally;
exit 2 means HOLD. Neither means operational qualification.

The envelope has exactly six keys:

```json
{
  "schema": "szl.observer-import/v1",
  "domain": "enterprise",
  "metric": "review-count",
  "unit": "count",
  "scope": "your-explicit-scope",
  "records": []
}
```

The empty example intentionally yields HOLD. Supply 6–256 records for a possible
rank, each with exactly `payload_base64`, `evidence_uri`, `evidence_digest`,
`retrieved_at`, and `kind`. `payload_base64` is canonical base64 of the exact
source bytes, never reserialized by this adapter. The URI is
`urn:sha256:<lowercase-hex>` and the digest is `sha256:<same-lowercase-hex>`.
Hash agreement binds bytes; it does not authenticate a producer.

Each decoded payload is a strict JSON object with exactly `record_id`, `domain`,
`metric`, `unit`, `scope`, `value`, `event_at`, and `kind`. The four scope fields
must match the envelope; units are not silently converted. `kind` is either
OBSERVATION or SIMULATION and is inside the hashed bytes, so simulation cannot
be promoted by changing its wrapper. All samples must have distinct IDs/times,
finite bounded values, and timezone-aware event/retrieval clocks.

The adapter fixes freshness at 900 seconds and obtains its own UTC clock. Old
sources are not refreshed by a recent retrieval timestamp. Caller `now`,
`generated_at`, `max_age_seconds`, URLs, commands, approvals, additional keys,
duplicate JSON keys, noncanonical base64, and malformed bindings are rejected.
The envelope is at most 2 MiB; each source payload is at most 4096 bytes.

## Output and trust

JSON uses `szl.observer-report/v1` and includes a typed result with immutable
byte references. It always keeps source authenticity NOT_VERIFIED, scientific
validation NOT_EVALUATED, external actions DISABLED, and probability null.
An observation import is SNAPSHOT, not live telemetry. Simulation is SAMPLE.
Constant baselines, stale data, contradictory kind/binding, numeric failure,
and invalid input return HOLD with no score.

The HTML view re-evaluates imported evidence rather than trusting an imported
result. It renders text with escaping and contains no script, form, iframe, or
connector. It references A11oy's local design-system stylesheet when hosted;
without it, layout-only rules and browser defaults apply. Responsive CSS and
skip/focus affordances are source-tested only; browser/mobile geometry and assistive technology are
NOT_VERIFIED. The seven domain cards are review contracts, not live products.

## Production integration is a separate admission

Do not import `serve.py` into this adapter. Current parallel lanes own the
assembler, Dockerfile, demo-route guard, readiness, and publication closure.
Reconstruct on then-current protected main only after refreshing overlap and
ownership. Source observed during this work advanced to
`059dc5bdd9358e8c51af442d7f052ea2d2d9b74b`; this prototype remains based on
`e6d1a43e3ef90d9267243b6b79076b2edc826ee7` and is not current-main-qualified.

Before registration: enforce handler-level authorization for sensitive reads
(global GET/HEAD exemptions are not confidentiality); authenticate before lookup;
never accept arbitrary file paths, URLs, or clocks; add the observer namespace
to the in-process-only proxy defense; mount exact supported methods before the
catch-all; deny unsupported methods; ship all imports through canonical COPY
closure; add hosted tests; independently validate browser/mobile behavior;
and use the existing signed source → HF publisher → runtime witness sequence.
No second HF writer or protection/settings change belongs to this prototype.

## Prepared regression workflow (2026-10-02)

`.github/workflows/observer-contract-tests.yml` is prepared locally for pull
requests and protected-main pushes. It installs the repository's hash-pinned
test lock, targets Python 3.12, and runs exactly the kernel and import/CLI/report
test files. The tests use pytest, PyYAML, and the standard library. Permissions
are `contents: read`; checkout persistence is disabled.
It has no provider credential, publication step, path filter, job condition,
dependency gate, or failure masking. A regression validates its parsed job
structure. This is implementation-test coverage, not a candidate's authority to
change protected release controls.

The final local source slice passes 109 focused tests on Python 3.11.9 with
pytest 9.0.3 and PyYAML 6.0.3. The six pytest packages were installed into a fresh
task-only directory using hashes from the existing CI lock; the existing local
PyYAML 6.0.3 package was used. No global Python environment was modified.
The bundled Python 3.12 environment is currently incomplete, so this new
109-test slice has not been rerun on Python 3.12 or in hosted CI.

The report now uses the canonical design token names without parallel literal
colors or font names. Without the optional design stylesheet, browser defaults
and the report's layout rules apply. This does not establish visual, mobile, or
accessibility acceptance.

The existing prototype base remains `e6d1a43e3ef90d9267243b6b79076b2edc826ee7`.
An explicit GitHub API quota 403 at 2026-10-02T22:04:17Z stopped publication
attempts before any commit, push, or PR. No alternate credential was used.
Refresh protected main and ownership, reconstruct the eight-file source-only
slice, and run scoped checks before publication when the API is available.
Do not represent the locally prepared workflow as a completed hosted run.

## Current-main source-only candidate (2026-10-02)

After the quota recovered, this eight-file slice was reconstructed in a separate
clean sparse worktree on verified protected main
`606e21927a6b043dc7ed2cd4d46d17ec1acb465c`. The original prototype and its dated
outputs are preserved unchanged. The initial signed reconstruction at
`a0001a403b12ab6989b882487b9726acc85b77e1` is also preserved locally, unpushed,
after main advanced. The earlier six-PR inventory found no path overlap; a new
exact-main tree read confirmed all eight paths were absent at this base.
No Dockerfile, canonical publisher, payload preparation, or existing CI control
is changed by this candidate.

This candidate adds only the offline kernel, adapter/CLI/report, two test files,
two documents, and their dedicated regression workflow. It does not register an
A11oy route or enter the HF payload. Its seven profiles remain NOT_CONNECTED;
no scientific or model qualification is claimed. Hosted checks and exact-head
review must be witnessed separately. Any later main merge can still trigger
the existing canonical publisher, so source-only does not mean provider-inert.
