# Canonical readiness artifact reader

`szl_readiness_artifact.py` belongs to services/provenance. It reads the existing
`hf-sync.yml` readiness artifact into process memory during the application
lifecycle. GitHub retains the artifact; this implementation adds no durable local
store, provider write, signing key, Space variable update, or automatic publisher.
Public readiness GETs only inspect a memory snapshot.

## Prerequisites and trust boundary

The reader runs only with `SPACE_ID=SZLHOLDINGS/a11oy`, the exact deployed
`SZL_GIT_SHA`, and the canonical `https://szlholdings-a11oy.hf.space` origin.
It uses an already provisioned Actions-read credential from
`SZL_READINESS_GH_TOKEN`, `GITHUB_TOKEN`, or `GH_TOKEN`, in that order. Absence or
denied access is **UNAVAILABLE**. This change does not provision a credential or
change its privileges. Credential values and signed download URLs never appear
in readiness output. Artifact-object requests do not carry the GitHub token.

Admission requires protected current main to equal the deployed source before
and after acquisition, the newest exact-source canonical workflow run and
attempt to succeed, both named probe and relock jobs to succeed, and a complete
artifact census. The archive must match its Actions SHA-256 and size, contain
only the expected JSON member, and bind the same repository, source, run and
attempt. The complete shipped endpoint matrix must have acceptable observations;
missing `requiredNotProbed`, skipped required effects, malformed counts, stale
data, unavailable required sources and incomplete runs fail closed. No older
successful run is substituted for a newer failure.

This is authenticated GitHub Actions metadata plus byte-digest verification.
It is **not an independent signature or independent runtime witness**:
`signatures_verified` remains false. A retained artifact does not grant effect
authority, certify AGI, establish model quality, or establish storage durability.

## Timing and operational limits

One worker starts during application startup and stops during shutdown. It
polls every 240 seconds. A fetch has a 30-second budget checked between bounded
stream chunks and a maximum five-second network read timeout; shutdown joins
for at most six seconds and never replaces a still-stopping worker.

Every acquisition and canonical hosted GET applies the existing publisher's
one-hour admission limit to the original `checkedAt`. Repeated retrieval never
renews that timestamp. An unchanged artifact becomes **UNAVAILABLE** on GET once
that hour expires, even if the background worker stalls or no refresh occurs.
The reader snapshot and final hosted route validation both enforce this limit
without provider access. Restart clears memory and requires a new admission.
Any new failed acquisition clears previously accepted evidence. The legacy
noncanonical local path retains its separate 24-hour limit.

The five required effect contracts (`policy/decide`, `operator/ask`, `eval/run`,
`agentloop/run`, `policy/compliance`) remain **BLOCKED** when unprobed. This reader
does not execute them or weaken their acceptance requirements. A new qualifying
artifact requires separately authorized effect acceptance through the canonical
workflow. This change adds no schedule, dispatch, or restart to produce evidence.
The read-only runner records skipped required contracts as `requiredNotProbed`;
the publisher rejects a positive count, and this reader independently refuses
that artifact. An ordinary GET-only run therefore cannot clear this gate.

The canonical hosted route ignores the legacy Space-variable verdict. Local
noncanonical operation retains its existing behavior. If the optional readiness
module cannot import, no reader is started and readiness remains unavailable.

## Offline verification

Run `python -B -m pytest -q tests/test_readiness_artifact.py
tests/test_publish_readiness_verdict.py`.
The new tests also run in the existing `python-estate-rag` CI job with its pinned
dependencies. They cover exact-source ownership, failed and incomplete runs,
artifact byte bounds and digests, malformed archives, clock expiry, credentials,
redirects, deadlines, lifecycle restart and side-effect-free GETs. Offline tests
are **MEASURED** test results; provider publication and runtime qualification
require separate evidence.
