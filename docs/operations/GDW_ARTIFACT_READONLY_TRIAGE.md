<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->
# Read-only GDW artifact triage

Services-layer diagnostic; not a recovery attempt or additional publisher.
It follows #2570's closed diagnostics and the held acquisition at run
`37263869028`. Historical provider effects remain NOT_ESTABLISHED.

## Native execution

Use the manually dispatched `gdw-artifact-readonly-triage.yml` workflow on main,
with `source_sha` equal to the actual current protected main. Contract tests run
first without provider secrets. Triage requires the exact main/workflow/source,
valid GitHub signature, active native dispatch and first attempt. It performs
only fixed repository GETs, private dataset HEAD metadata reads, and the existing
read-only fixed-capture qualification into disposable runner storage. Source
movement or changed dataset metadata holds the result. No old run is replayed.

The production ArtifactCache validates every retained row and reconstructs the
exact local artifact plan from the captured candidate. The active v2 path then
uses a credential-isolated supervised child to read only those expected bucket
paths, validate present objects against their expected size and SHA-256, and
reobserve the entire expected set. Source, candidate, private HEAD and object
identity changes hold. The child must be killed/reaped before its closed report
is accepted; candidate and source are rechecked after cleanup. It has no provider
writer. The older sentinel callback remains an offline local diagnostic.

The output contains only source/run identity, fixed diagnostic codes, limited
private HEAD metadata, and false mutation/retry/restoration/deployment flags.
No private DB, row payload, owner identifier, path or arbitrary exception message
is uploaded. A single fixed JSON file is retained; temporary captures and
reconstructed artifacts are removed with the disposable working directory.
A four-minute native deadline and six-minute job cap bound execution.

## Reading the outcome

- `NO_EXPECTED_OBJECTS_PRESENT_AT_READ_TIME`: all expected exact paths were absent
  during both reads; unrelated or orphan object absence remains unknown.
- `PARTIAL_EXPECTED_OBJECT_SET_PRESENT_AT_READ_TIME`: some expected objects were
  validated; the missing count stays explicit.
- `ALL_EXPECTED_OBJECTS_PRESENT_AND_VALIDATED_AT_READ_TIME`: all expected bytes and
  current identities were validated; historical writer attribution remains
  `NOT_ESTABLISHED`.
- Top-level HELD: native authority, capture qualification or metadata stability
  could not be established; never infer a private-state resolution.

HEAD absence is not absence of orphan/partial bucket objects. This diagnostic
is not an exhaustive bucket audit and cannot establish no historical effects.
No pause/resume, bootstrap, database reset, snapshot publication, bucket copy,
upload, dataset commit, deletion, credential change or restored runtime is part
of its scope. A separately qualified recovery decision remains necessary.

The native observation uses the source-owned LOGICAL_ROOTS for both proof and
receipt binding, matching the corrected isolated worker admitted in #2571.
It never inherits caller overrides or moves/relabels captured logical paths.

Successful supervised v2 run `37357773764` on source
`f1653a2908f944e37b7de87da36363cc9d661913` observed 224 expected, 0 present, 224
missing; both captured stores qualified and private HEAD absent at a stable
revision. Exact archive/report identities and the separately guarded source
proposal are documented in
[GDW_RECONCILED_ACQUISITION_20261005.md](GDW_RECONCILED_ACQUISITION_20261005.md).
The diagnostic's false retry, restore and deployment flags remain unchanged.
