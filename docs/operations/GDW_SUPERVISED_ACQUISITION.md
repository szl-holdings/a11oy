# Refresh the held canonical acquisition inspection

This source selects the existing bounded read-only inspection after current-main
admission. It cannot retry acquisition, preserve new copies, configure, restore
or deploy. Publication and the resulting native inspection require source review
and protected GitHub admission. No provider action was performed while preparing
this change; a new inspection result is not yet established.

## Current held checkpoint

The supervised source `de48eec9dfdff1e0f905f11fb92bfc8415338bac` is a verified
signed commit with tree `962daf4109b10bd1202f82e8a2c0060488669cfa` and sole parent
`0e63b001630b359f8efaa4cf2d744c08c32b70dc`. Canonical push run `37252210120`,
attempt `1`, completed with successful source-admission job `111581985385` and
failed read-only reconciliation job `111582017162`. All eleven other jobs were
skipped, including preservation, acquisition and every downstream provider writer.

Artifact `11321093816` contains a `401`-byte ZIP with SHA-256
`5ff6b6f467ab36549cedbeb83f45020d7a4de162c39a40e7bfe95a541df33192`.
Its sole `gdw-supervised-reconciliation.json` member is `297` bytes with SHA-256
`87e736d831fffca6f6658e63d05fed282ca1e21ef337263e72cf2e15503db9d6`.
The report records `SUPERVISED_RECONCILIATION / BOUNDARY_ENTERED / HELD`, diagnostic
`EXPECTED_ABSENCE_UNVERIFIED`, provider effects `NOT_ESTABLISHED`, and false
restore and deployment admission. It does not identify the current private
Dataset revision, establish whether a private read was reached, classify HEAD,
or explain the failed absence predicate. A Dataset move is not established.

## Inspection-only successor

The existing `--inspect-held-acquisition` worker is selected inside the same
canonical acquisition job identity, using only its fixed output path. The caller
supplies no source, artifact, publisher, retry or GitHub-output override. The
existing HF secret expression, read permissions, 1.31.0 metadata ABI, private
visibility and identity checks, current protected source checks, and deadlines
are unchanged. The earlier manual job retains its separate exact 1.23.0 ABI.

| Workflow boundary | Behavior in this source |
| --- | --- |
| Source admission | Existing successful current-main receipt with `publish == 'true'` is mandatory. |
| Reconciliation and manual preservation | Both retain their complete original predicates with an additional literal `&& false`; no capture copies or reconciliation attempt can run. |
| Canonical acquisition job | Only push attempt `1`, source success and ownership, and both disabled predecessors explicitly `skipped` allow the fixed read-only inspection. Its existing dependency list is unchanged. |
| Pair configuration | The existing command has an independent literal false condition. Inspection cannot supply an acquisition locator. |
| Downstream jobs | Existing dependencies and conditions are unchanged. The skipped manual job blocks every provider writer, even if inspection were hypothetically reported successful. Explicit first-attempt guards also block partial reruns that reuse successful dependencies. |

The inspector retains the original fixed `d61a838e…` acquisition binding. The
subsequent `0e63b001…` inspection and `de48eec9…` reconciliation were read-only;
neither replaces the failed acquisition as the historical subject. The fixed
`353c5253…` absence predicate and all source, native evidence, absence and retry
negative controls remain unchanged. This successor does not bypass that predicate
to acquire; it uses the already existing inspection mode to observe current
private Dataset revision and HEAD classification.

The worker returns exit code `2` for every inspection outcome, including valid
ABSENT, ACKNOWLEDGED, INVALID or UNAVAILABLE classifications. Its safe report
remains HELD with retry, restore and deployment admission false; provider objects
are not verified. The existing artifact allowlist remains exactly
`gdw-durable-acquisition.json` and `gdw-managed-configuration.json`; only the
inspection JSON is expected because configuration is disabled. No private store,
raw capture or SDK cache is retained in an Actions artifact. New evidence requires
another explicit review before any future source could enable provider effects.

## Historical observations

The failed acquisition on `d61a838e8763f560ddbd113bfa398f4bb64f2342`, run
`37244394814`, attempt `1`, job `111559424879`, emitted only the old generic HELD
report. Its stage and exception class were lost. The approximately 32.76-second
duration and a later PAUSED observation do not establish its cause or attribute
the pause to that job. Review of its absolute worker path, file-derived source
root and `git -C` calls did not reproduce a temporary-working-directory defect.
The closed stage/diagnostic decoder added subsequently remains in place.

The actual read-only successor is source
`0e63b001630b359f8efaa4cf2d744c08c32b70dc`, run `37247543538`, attempt `1`,
inspection job `111568333469`. Its source-admission job `111568304241` succeeded;
the inspection exited `2`; all ten other jobs were skipped, including manual
preservation and every provider writer. Artifact `11319502797` has exact ZIP
size `565` and SHA-256
`8a099f20d3d85927bda80e2c702a645b9f8ac01314fbceaf244f616933be0b9e`.
Its sole canonical JSON member is `640` bytes with SHA-256
`e093e8a7b02c170d076f49b3094721eb576e154b020716b73dfaec2b5d1336e5`.
That report says **ABSENT / HELD** at private dataset revision
`353c525331d7f9d83d6fd16fa1e1828a09bbe9ba`; provider-object verification, retry,
restore and deployment admission are all false.

ABSENT concerns the private dataset HEAD only. It does not establish that no
orphan objects were uploaded during the failed attempt. Existing captures,
original stores and any such objects are preserved; this source has no cleanup
or deletion path.

## Retained supervised contract from de48 (disabled in this successor)

The following describes the supervised source that held at reconciliation. Its
helper code and negative controls remain intact, but its preflight, copies and
acquisition command are not enabled by the inspection-only workflow above.

### Finite source and native run authority

The new read-only job `recovery-reconciliation` runs after source admission and
before `manual-prerequisites`. Its helper requires all of the following:

- The exact protected current main is a GitHub-verified, valid signed commit
  whose sole parent is the inspected source `0e63b001…`.
- The workflow source equals `GITHUB_SHA` and `GITHUB_WORKFLOW_SHA`; the event is
  `push`, attempt is integer `1`, repository and workflow are the fixed canonical
  values, and the exact executing job is active with no conclusion.
- Both the immutable attempt endpoint and the current unversioned run endpoint
  identify that same active first attempt. A complete bounded workflow push-run
  census for the source contains exactly the current run; every returned
  repository, source, workflow, branch and event identity is checked.
- The fixed prior run, all twelve prior jobs, failed inspection step, skipped
  pair configuration, successful artifact upload, native artifact metadata,
  archive bytes and sole report bytes match the identities above.
- Two private metadata observations find that same fixed dataset revision,
  private visibility and absent HEAD. Changed, present, invalid or unavailable
  state remains held. Reads are bounded and ownership/deadline checks bracket
  each callback and provider read.

The preflight uses a 115-second worker budget inside a 120-second parent limit,
descriptor-level private output suppression, a closed request and a canonical
4-KiB result allowlist. Only a validated exit-zero result bound to the current
source/run/attempt/job can write `admitted=true`. It cannot produce an acquisition
locator. Failure retains only the existing closed HELD stage/code report.

Manual dispatches, later source commits and reruns are rejected. Direct
first-attempt conditions also guard independently rerunnable effect jobs, so
GitHub's reuse of a previously successful prerequisite cannot reopen deployment,
configuration, ingestion or Finance publication in a later attempt. The existing
workflow-wide non-cancelling concurrency group is unchanged. This is a bounded
native-history admission, not a claim of an irreversible reservation against an
administrator deleting run history or rewriting protected main.

### Credential and effect ordering

The only new credential exposure is the explicitly reviewed read-only job. It
uses the exact same HF secret expression and `contents: read` / `actions: read`
permission set already used by `durable-acquisition`. There is no new token,
permission, provider target or publisher. It exposes only private dataset
metadata reads and bounded GitHub GETs; no bucket, pause, upload, commit or
configuration method is called by the preflight.

| Ordered owner | Allowed behavior and mandatory predecessor |
| --- | --- |
| `source-admission` | Existing GitHub-only current-main ownership receipt. |
| `recovery-reconciliation` | Fixed native inspection verification and private HEAD metadata reads only; every failure blocks all later effects. |
| `manual-prerequisites` | Runs only after the positive same-run preflight. The existing 1.23.0 environment remains exact. A fixed supervised flag requires canonical push/attempt 1 and rechecks protected current main plus fixed-revision HEAD absence immediately before each existing add-only capture/manifest batch. Original paths are never written. Existing candidate qualification and classifier remain fail closed. |
| `durable-acquisition` | Existing separate 1.31.0 environment. Revalidates the complete native prerequisite, same-run source/qualification artifacts, current source, installed-source manifest, isolated base and legacy guard. Rechecks HEAD absence before pause, then before every private object submission and absent-only bootstrap. Both exact candidates must be reproduced and verified. |
| Pair configuration | Only after the worker returns its acknowledged, exact-owned bootstrap locator; existing private admission validation and persistent old-source guard remain mandatory. A partial result holds. |
| Canonical deployment | Existing pinned Dockerfile-derived publisher only, after successful managed acquisition and the existing source/manual gates. Current push/attempt 1 is required directly on this job. |
| Runtime proofs and readiness | Existing actual-host source, SQLite, storage, restart, receipt and acknowledgment contracts remain mandatory. Configuration/proof and verdict-ingestion jobs require the first push attempt directly. |
| Relock and Finance | Existing exact live/source verification precedes the established Finance projection publisher, which also requires the first push attempt. The separately opt-in six-Space dispatch path is unreachable through this push-only incident gate. |

Once this run's own bootstrap has been acknowledged, its subsequent readback
uses the existing exact owned HEAD/admission contract. It does not incorrectly
require its own newly created HEAD to be absent. The storage backend's existing
bounded handling of definite conditional conflicts is unchanged; the incident
wrapper additionally refuses any changed private dataset revision. Ambiguous
write outcomes are never blindly resubmitted. A new attempt requires a new
inspection and explicit source review.

The preflight and its safe JSON are prerequisites only. Candidate continuity
does not prove the absence of pre-capture data loss, provider object completeness
or final runtime durability. Those claims remain governed by the existing
independent native readback and actual-host proof contracts.
