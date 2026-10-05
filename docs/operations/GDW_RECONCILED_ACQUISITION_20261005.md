<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->
# One canonical acquisition after exact artifact reconciliation

This source proposal binds one signed direct successor of
`f1653a2908f944e37b7de87da36363cc9d661913` to its unique first canonical push run.
Publication requires protected source admission. Preparing or testing this source
does not perform recovery, install a database, or establish product readiness.

## Observed prerequisite

[Native read-only triage run 37357773764](https://github.com/szl-holdings/a11oy/actions/runs/37357773764),
attempt 1, completed successfully on that exact source. Contract job
`111924448606` and triage job `111924632435` both succeeded. The triage requalified
the fixed preservation capture into disposable runner storage and observed:

- Both database candidates: `LOGICAL_CONTINUITY_VERIFIED`; captured originals unchanged.
- Expected retained artifact objects: 224; present: 0; missing: 224.
- Classification: `NO_EXPECTED_OBJECTS_PRESENT_AT_READ_TIME`.
- Expected-set SHA-256: `7a28c53fa647e639375c6a90d3e34e89fe74bc2004f8161b5f38ac793301be42`.
- Empty observed-set SHA-256: `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`.
- Private dataset HEAD absent at revision `fd57865f92240626794729aecdc0827b90796aac`,
  stable throughout the observation.
- Provider writes, retry, restore and deployment admission: false.

Artifact `11365342348`, named `gdw-artifact-readonly-37357773764-1`, is exactly
1,092 ZIP bytes with SHA-256
`a6aa374c1878af66e142260a4f2ff9283c3566935dc88f958ce65bcc7265305b`.
Its sole member, `gdw-artifact-triage.json`, is 1,814 bytes with SHA-256
`9c8ffa25849305a95248d280989ac91e038e00cd04e3a5eb47d7e3b6949dbe37`.
The successor verifies both native producer metadata and these exact bytes.

This is an observation of the expected set only. It does not establish absence
of unrelated or orphan objects, attribute any historical writer, or prove that
no acknowledged writes were lost before capture. The earlier `62ca` acquisition
run `37263869028` retains `NOT_ESTABLISHED` historical provider effects. Preserve
the captured originals, all existing bucket objects and historical run artifacts.

## Finite source and run binding

The read-only `recovery-reconciliation` job executes after source admission. Its
helper requires the exact protected main, a valid GitHub-verified signature and
one parent equal to the observed source. It checks both the immutable attempt
and current run endpoints, the active executing job, and a complete source/run
census containing exactly this first push attempt. Dispatches, reruns, later
descendants, a moved main, changed artifact bytes or producer mismatch hold.

The prior producer verifier accepts only the successful two-job diagnostic
workflow above. It checks the contract, observation and artifact-upload steps,
archive provenance, sole member and closed report. The private dataset revision
and HEAD absence are reobserved twice before preflight emits `admitted=true`.

The existing credential-isolated subprocess, 115-second child budget,
120-second parent limit, bounded private output and canonical report validation
remain in force. The preflight performs reads only and cannot return an
acquisition locator.

## Ordered effects and unchanged gates

1. Source admission and exact reconciliation must succeed in the same native run.
2. The isolated 1.23.0 prerequisite environment preserves stopped originals into
   a new private capture prefix, requalifies the fixed capture and emits only the
   existing closed three-member prerequisite artifact. Original paths are never
   written. The source and expected dataset fence are checked before copies.
3. The 1.31.0 acquisition environment revalidates the native evidence, installed
   source manifest, Dockerfile-derived runtime base and legacy startup guard.
   It pauses the exact old Space and verifies its source, configuration and
   original object identities before acquisition.
4. Reproduced candidate identities must match the qualified pair. Before the
   first artifact add, the reconstructed plan must again contain exactly 224
   objects and the observed expected-set hash. Two exact-path metadata passes,
   bounded to 64 paths per call and bracketed by source checks, require every
   expected path still absent. A returned or unreadable object, changed candidate,
   or moved private fence holds before publication. No bucket enumeration or
   cleanup occurs. This pre-add check is not reapplied after this run's own adds.
5. Existing per-write current-source, paused-Space, unchanged-original and
   expected dataset-revision/HEAD checks remain mandatory. Objects and snapshots
   require exact readback; bootstrap is absent-only and conditional on the private
   dataset parent. An ambiguous submission is never blindly resubmitted.
6. Pair configuration runs only after successful acquisition in that first push,
   verifies the owned selector and installs the persistent old-source guard.
   Both acquisition and configuration records are retained for exact downstream
   locator validation.
7. The sole Dockerfile-derived publisher, actual-host source/storage checks,
   live proofs, readiness ingestion and final source reauthorization remain
   separate mandatory stages. Managed recovery does not use the ordinary
   predeployment resume job. The opt-in six-Space path stays unreachable through
   this push-only incident acquisition.

The non-cancelling canonical concurrency group is unchanged. No token, provider
target, writer, storage deletion or DNS change is added. Successful source tests
or an acknowledged bootstrap alone cannot establish deployment, runtime
durability or an independent witness. If the one admitted attempt holds,
preserve its evidence and inspect the resulting state before proposing a successor.
