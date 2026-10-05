# One supervised canonical acquisition after the refreshed held inspection

This source proposal permits one narrowly bound canonical recovery run. It does
not turn the prior inspection into retry, restore or deployment authority.
Publication and the resulting native run require source review and protected
GitHub admission. No provider action was performed while preparing this change.


> Refreshed evidence: canonical push run `37262929675`, attempt `1`, on signed
> protected source `a60125af336ea97ac29678a79110c30ec0122e99` performed a
> metadata-only inspection. It classified the private durable HEAD as **ABSENT**
> at dataset revision `dd34d6b0b20d918cc862888030569d03d99a9b37`; provider writes,
> retry, restore and deployment admission remained false. The 13-job run had only
> source admission succeed and the inspection job fail-closed as designed; all
> eleven provider/downstream jobs were skipped.

## Observed prerequisite and remaining uncertainty

The failed acquisition on `d61a838e8763f560ddbd113bfa398f4bb64f2342`, run
`37244394814`, attempt `1`, job `111559424879`, emitted only the old generic HELD
report. Its stage and exception class were lost. The approximately 32.76-second
duration and a later PAUSED observation do not establish its cause or attribute
the pause to that job. Review of its absolute worker path, file-derived source
root and `git -C` calls did not reproduce a temporary-working-directory defect.
The closed stage/diagnostic decoder added subsequently remains in place.

The actual read-only successor is source
`a60125af336ea97ac29678a79110c30ec0122e99`, run `37262929675`, attempt `1`,
inspection job `111613776558`. Its source-admission job `111613728997` succeeded;
the inspection exited `2`; all eleven other jobs were skipped, including manual
preservation and every provider writer. Artifact `11324359120` has exact ZIP
size `564` and SHA-256
`863191708947e38f6d3338e0f99cefff25f19fde55919132dd991e099d7c4513`.
Its sole canonical JSON member is `640` bytes with SHA-256
`d5f84ce152b3c46d5295792d1db44b0031568079719aa375a04be9750e38dee8`.
That report says **ABSENT / HELD** at private dataset revision
`dd34d6b0b20d918cc862888030569d03d99a9b37`; provider-object verification, retry,
restore and deployment admission are all false.

ABSENT concerns the private dataset HEAD only. It does not establish that no
orphan objects were uploaded during the failed attempt. Existing captures,
original stores and any such objects are preserved; this proposal has no cleanup
or deletion path.

## Finite source and native run authority

The new read-only job `recovery-reconciliation` runs after source admission and
before `manual-prerequisites`. Its helper requires all of the following:

- The exact protected current main is a GitHub-verified, valid signed commit
  whose sole parent is the inspected source `bedc2f55…`.
- The workflow source equals `GITHUB_SHA` and `GITHUB_WORKFLOW_SHA`; the event is
  `push`, attempt is integer `1`, repository and workflow are the fixed canonical
  values, and the exact executing job is active with no conclusion.
- Both the immutable attempt endpoint and the current unversioned run endpoint
  identify that same active first attempt. A complete bounded workflow push-run
  census for the source contains exactly the current run; every returned
  repository, source, workflow, branch and event identity is checked.
- The fixed prior run, all thirteen prior jobs, failed inspection step, skipped
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

## Credential and effect ordering

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
