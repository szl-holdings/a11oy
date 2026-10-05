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

The production ArtifactCache then validates retained rows and reconstructs
local artifact bytes from the captured candidate. Its callback always raises
an observation-only sentinel before any provider call. It never returns a fake
publication acknowledgement. Because the production routine validates all rows
before its first callback, reaching that callback establishes local validation,
not cloud publication. An empty set is named separately. Exact before/after
candidate digests must agree.

The output contains only source/run identity, fixed diagnostic codes, limited
private HEAD metadata, and false mutation/retry/restoration/deployment flags.
No private DB, row payload, owner identifier, path or arbitrary exception message
is uploaded. A single fixed JSON file is retained; temporary captures and
reconstructed artifacts are removed with the disposable working directory.
A four-minute native deadline and six-minute job cap bound execution.

## Reading the outcome

- `LOCAL_ROWS_VALIDATED_PUBLICATION_NOT_ATTEMPTED`: local row/file qualification
  completed; provider-specific publication remains untested.
- `NO_RETAINED_ARTIFACTS`: no callback was needed; this is not an upload receipt.
- An `ARTIFACT_*` code in the local observation: an actual validation/materialization
  failure was observed against the disposable candidate, without provider writes.
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
