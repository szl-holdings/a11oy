# Fixed 62ca metadata inspection checkpoint

This source checkpoint permits one kind of operation: bounded metadata inspection
of the canonical acquisition attempt at source
`62ca4d1506fe95f8bedf2143f5f8b60c786dcd74`, run `37263869028`, attempt `1`.
It grants no acquisition retry, preservation copy, restore, runtime configuration,
resume, deployment, or publication authority. Every inspection result remains
`HELD` and the canonical helper exits `2`.

The checkpoint is based on admitted main
`0b5a117f6ecbf6722c84dfefb72b932677dd7c99`, tree
`9ebbe0be63bd7148f95922e56cadf64e9d420190`. It retains the artifact diagnostics
and trusted logical-directory correction from PRs 2570 and 2571. Those changes
do not establish the cause or provider effects of the earlier attempt.

## Exact incident and qualification binding

The new `scripts/inspect_gdw_62ca_acquisition.py` is a separate, source-fixed
reader. It has no incident, artifact, path, or profile selector in the CLI or
environment. The existing empty-request `--inspect-held-acquisition` mode routes
both the worker and its parent report validator to this reader.

| Binding | Fixed value |
|---|---|
| Prior source | `62ca4d1506fe95f8bedf2143f5f8b60c786dcd74` |
| Run / attempt | `37263869028` / `1` |
| Acquisition job | `111616768413` |
| Qualification job | `111616609573` |
| Raw source-admission JSON SHA256 | `596d2dd741cec3684fbf2f87040be96823757caaa0331bd7bc6c4267b58ae96e` |
| Raw qualification JSON SHA256 | `37bdf39c89fc6aee7aa50de0da96465c3941fb4632fd75012c6e03afd767b973` |
| Qualification artifact | `11324504756` |
| Qualification ZIP SHA256 | `127c4412063effef9c554a6cf6f6a084e17d69a7b4a3675521e03aee33d2af0d` |
| Safe failed-acquisition artifact | `11325467455` |
| Safe failed-acquisition ZIP | `389` bytes; SHA256 `d290fa69bf530ec3cc27daccfd0daef13904064c2f3a75f73fe2bc71c2515afd` |
| Sole safe member | `gdw-durable-acquisition.json`; `298` bytes; SHA256 `f4e638d0b73f865add47e16c7de5bdfff9f9ce8b6b505ee4e6debf1098db35a2` |

The raw source and qualification digests bind the admission's native contexts;
the qualification artifact is distinct from the safe acquisition failure
artifact. The latter contains only this closed report:

```json
{"deployment_admitted":false,"diagnostic_code":"CANONICAL_ACQUISITION_UNAVAILABLE","provider_effects":"NOT_ESTABLISHED","restore_admitted":false,"schema":"szl.gdw-durable-acquisition/v1","secret_values_recorded":false,"stage":"ARTIFACT_PUBLICATION","stage_state":"BOUNDARY_ENTERED","state":"HELD"}
```

Before any private dataset metadata read, the reader verifies the native failed
attempt, its complete 13-job census, the exact source/reconciliation/qualification
successes, acquisition failure, and nine downstream skips. It checks the named
failed acquisition step, skipped pair configuration, and successful safe report
upload. The artifact's identity, repository, source, run, producer time window,
size, archive hash, single regular JSON member, member size/hash, canonical
encoding, and complete report value must all match. Expiry, transport errors,
unexpected redirects, incomplete metadata, and substitutions fail closed.

## What metadata can establish

The provider adapter exposes only `dataset_info`, `get_paths_info`, and
`hf_hub_download` for the existing private dataset `SZLHOLDINGS/szl-evidence`.
It initially permits only `a11oy/durable-store/v1/head.json`. A strictly parsed
BOOTSTRAP for the fixed prior source may unlock only its exact history JSON and
admission JSON. Reads remain bound to immutable dataset revisions, private
resource identity, bounded regular files, and their Git blob hashes. Bucket
listing, artifact objects, SQLite bytes, original stores, configuration, pause,
upload, and commit methods are unavailable to this adapter.

- `ABSENT` means that HEAD is absent in the same private dataset revision observed
  twice. It cannot establish that earlier bucket/Xet writes never occurred, that
  no partial or orphan artifact objects exist, or that retry is safe.
- `ACKNOWLEDGED` means the fixed BOOTSTRAP HEAD, history, admission, qualification,
  native execution context, and provider resource-group binding agree. Object
  existence, content, completeness, restoration, and a running service remain
  unverified.
- `INVALID` or `UNAVAILABLE` grants no absence inference. Uncertain transport or
  source ownership cannot be converted into `ABSENT`.

The earlier `ARTIFACT_PUBLICATION` phase wraps local artifact validation followed
by serial private publication callbacks. `BOUNDARY_ENTERED` does not distinguish
validation failure before callbacks from a partial publication. HEAD bootstrap
occurs later, so absent HEAD can coexist with previously written private objects.
All reports retain `prior_provider_effects: NOT_ESTABLISHED`, false provider-object
verification and false retry/restore/deployment flags. `provider_writes_performed`
describes this read-only inspection, not the prior attempt.

## Exact retained-artifact reconciliation

The separate manual `gdw-artifact-readonly-triage.yml` contract can narrow the
remaining artifact-object ambiguity without changing the fixed inspector above.
It accepts only the exact current protected-main SHA on attempt 1, verifies its
signed commit and active native run, and re-verifies the fixed 62ca run, complete
job census, failed acquisition step, and safe failed-acquisition artifact
identity before any private provider read.

The runner reconstructs the current qualified GDW candidate in disposable
private storage. It validates every retained exported row before the first
artifact-object request, derives the canonical writer's deterministic object
paths, and admits only that finite exact set to a read-only adapter. Present
objects are downloaded only into runner-private temporary storage and checked
against their expected size and SHA256, followed by a second exact identity
observation. Both expected databases must report logical continuity, unchanged
captured originals, and unchanged declared stored values during the capture
qualification interval. The protected source, dataset revision and HEAD
presence, artifact-object identities, and candidate digest must remain unchanged
across the later artifact-object observation. The diagnostic does not claim
that the preserved capture objects were re-observed after that interval.

The uploaded v2 report contains only counts, a closed current-state
classification, and aggregate identity hashes. It contains no object path,
owner ID, payload, captured database, secret, or provider error text. The
classifications are limited to `ALL_EXPECTED_OBJECTS_PRESENT_AND_VALIDATED_AT_READ_TIME`,
`PARTIAL_EXPECTED_OBJECT_SET_PRESENT_AT_READ_TIME`, and
`NO_EXPECTED_OBJECTS_PRESENT_AT_READ_TIME`. They concern only the exact retained
set justified by the current candidate. Bucket history and historical writer
identity are not available through this API, so every result retains
`historical_writer_attribution: NOT_ESTABLISHED` and
`prior_provider_effects: NOT_ESTABLISHED`. None is retry, restore, publication,
or deployment authority.

The preservation report last explicitly observed `RUNTIME_ERROR` at
`2026-10-05T04:32:14.881806+00:00`. The acquisition source requires a PAUSED
readback before entering artifact publication; that is sequencing evidence.
Neither fact establishes the runtime's current state. The inspector performs no
runtime probe and reports `runtime_state_verified: false`.

## Native containment and legacy separation

Only an owned first `push` attempt on current protected main can reach the native
inspection job. Source admission must succeed, and reconciliation and manual
preservation must both be skipped under their literal false gates. The native
job retains its fixed identity, existing isolated worker, 120-second deadline,
private output suppression, strict parent validation, and nonzero outcome.
Pair configuration has an independent literal false gate. Downstream jobs still
require successful manual prerequisites, so even a synthetic successful
inspection cannot make a provider writer or publisher eligible. Only the safe
inspection JSON is uploaded from the job.

The original `scripts/inspect_gdw_held_acquisition.py` remains byte-for-byte fixed
to d61, and `scripts/reconcile_gdw_supervised_acquisition.py` retains its a601
inspection, parent, run, job, artifact, report, and absent-revision pins. The new
report schema is distinct; neither validator accepts the other incident's
report. No old ABSENT result becomes new retry authority.

The COPY lockstep guard still checks exact controller, Dockerfile source
coverage, workflow graph, and helper bytes. Its inspection-checkpoint result
describes a publication hold and makes no claim of live Hugging Face parity.
Targeted synthetic tests exercise cross-incident rejection, native artifact
binding, closed reports, no object methods, no writes, and the complete held
workflow graph. They cannot establish live provider state.

Native source: [62ca canonical run](https://github.com/szl-holdings/a11oy/actions/runs/37263869028),
[failed acquisition job](https://github.com/szl-holdings/a11oy/actions/runs/37263869028/job/111616768413),
[admitted correction](https://github.com/szl-holdings/a11oy/commit/0b5a117f6ecbf6722c84dfefb72b932677dd7c99).
