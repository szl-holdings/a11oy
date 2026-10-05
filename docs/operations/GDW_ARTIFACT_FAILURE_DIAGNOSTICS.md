<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->
# GDW artifact preparation: closed failure diagnostics

`gdw_durable_artifacts.py` belongs to the services layer. This change makes a
failure distinguishable; it neither repairs private data nor grants a retry.

## Observed incident

Canonical run `37263869028`, attempt 1, source
`62ca4d1506fe95f8bedf2143f5f8b60c786dcd74` verified two preserved private database
copies and qualified the candidate. Acquisition then returned HELD at
`ARTIFACT_PUBLICATION / BOUNDARY_ENTERED`. The 389-byte artifact `11325467455`
(SHA-256 `d290fa69bf530ec3cc27daccfd0daef13904064c2f3a75f73fe2bc71c2515afd`)
records `provider_effects=NOT_ESTABLISHED`, not zero writes. Configuration and
publication were skipped. Original and partial objects must remain preserved.

`ArtifactCache.prepare` previously replaced every inner failure with
`ARTIFACT_PERSISTENCE_UNAVAILABLE`; the worker decoder then generalized that
code again. Existing evidence cannot distinguish row validation, local
materialization, provider invocation, or provider readback. No underlying
provider fault is inferred from that receipt.

## Diagnostic contract

The source-owned closed set distinguishes database opening, schema validation,
row reading/validation, cache materialization, native binding, provider call,
and provider readback. Explicit source validation failures retain their fixed
codes. Arbitrary exceptions, including provider messages that resemble codes,
map only to the current source-authored boundary. No exception string, repr,
path, owner identifier, payload, URL, credential, or returned object is logged.

The acquisition worker accepts exactly those literals through its existing
nine-field HELD decoder. Stage/state remain descriptive; provider effects stay
NOT_ESTABLISHED and restore/deployment/secret-disclosure flags stay false.
Successful output shape, all-row validation before publication, per-write
fences, no-retry behavior, and the original database remain unchanged.

## Qualification and remaining boundary

Added tests exercise hostile exception redaction, fixed readback errors,
partial-publication failure without retry, unchanged databases, and the full
HELD serializer/decoder round trip. Existing tests still enforce successful
reconstruction and integrity rejection.

Windows cannot execute the native POSIX suite (`fcntl` is unavailable); do not
count collection errors as regression failures or native test passes. Portable
exact-source diagnostic-node checks are narrower evidence. The repository's
existing hosted Linux GDW job must execute the actual full tests before merge.

This source change does not activate a diagnostic provider run. Before any
future write-enabled recovery, perform a separately reviewed read-only
reconciliation of the current private metadata and retained artifact state.
Do not rerun the historical acquisition, resume the held Space, reset SQLite,
or delete partial objects to obtain a more specific message. Use the existing
canonical publisher after its source/evidence/restore gates are qualified.
