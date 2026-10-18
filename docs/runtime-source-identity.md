# Authenticated runtime source identity

`szl_runtime_identity.py` belongs to the **provenance** layer. It binds the
canonical publisher's report to the files copied from source into `/app` and
the current process boot ID. Publication is **REPORTED** by the authenticated
publisher; local file hashes are **MEASURED** by this process. The scope is
`FINAL_APP_SOURCE_COPY_FILES`. This does not attest a complete container image,
installed dependencies, hardware, or the current provider host. It grants no
execution authority and creates no independent approval or witness.

## Publication and startup

The canonical `hf-sync.yml` opts into the pinned reusable publisher's
`runtime-identity` input. The publisher accepts only the canonical
`szl-holdings/a11oy` to `SZLHOLDINGS/a11oy` mapping and an exact default-branch
source SHA. It generates a unique run/attempt/nonce selector and a bounded
catalog of final source `COPY` destinations. The selector is copied to the
single fixed path `/tmp/.szl-runtime-marker.json`; it is outside the immutable
source catalog. The checked-in placeholder deliberately cannot verify.

After Hugging Face acknowledges the commit, the workflow attests
`hf-runtime-binding.json` using GitHub's OIDC provenance action and uploads
`hf-runtime-identity-<run_id>-<run_attempt>`. This occurs before the RUNNING and
smoke checks, so identity verification cannot deadlock startup. It reports
publication only; a later deployment or smoke failure remains a failure.

At process construction the verifier captures the selector bytes, source SHA,
boot ID, copied workflow pin, and actual source-file hashes. The application
lifespan starts one background verification window of five minutes. It reads
the exact run attempt, validates the artifact metadata and bounded ZIP, and
uses the installed GitHub CLI to verify the artifact attestation. Verification
requires the canonical reusable workflow, exact pinned publisher SHA, source
SHA, main ref, GitHub OIDC issuer, hosted runner, and certificate invocation
URI for the same run and attempt. Artifact metadata or a predicate alone is
insufficient.

Only one successful identity can be latched per process. Each execution
admission rechecks the selector and all cataloged source bytes without network
access. Observed local drift permanently refuses that boot, even if the bytes
are restored. Environment variables and provider current-head APIs cannot
replace its identity. The OS, Python process, verifier, GitHub trust roots, and
canonical publisher remain trusted components; this is not remote attestation
of those components.

## Operator prerequisites and release order

1. Merge the reusable publisher normally with its required checks. The new
   reusable revision has an explicit caller permission interface:
   `contents: read`, `id-token: write`, and `attestations: write`. Existing
   consumers remain on their old immutable pins until they adopt the change.
2. Pin A11oy's `hf-sync.yml` to that merged revision. Update the exact publisher
   revision and script SHA-256 in both `scripts/build_gdw_installed_source_manifest.py`
   and `gdw_durable_source.py`; their source identity checks remain mandatory.
   The exact selector build-input exception describes only the checked-in
   placeholder, never the generated selector bytes. It does not activate or
   extend retired storage admission.
3. Supply the runtime's dedicated `SZL_READINESS_GH_TOKEN` with `Actions: read`,
   `Attestations: read`, and `Contents: read` for the existing source probes.
   Credential provisioning must be verified separately. There is
   no fallback to a general `GH_TOKEN`. Existing independent approval, signer
   pins, lease, state-store, and effect authorization requirements still apply.
4. Publish through the sole canonical writer and verify its exact source/HF
   binding, CI, provider build, and runtime status separately. The Dockerfile
   installs `gh=2.102.0` from GitHub's authenticated apt repository and checks
   its version; an unavailable pin fails the build rather than downloading an
   unverified replacement executable.

`GET /api/a11oy/v1/series-a/status` exposes `runtime_source_identity` as a
read-only snapshot. It starts no verification, writes no receipt, and performs
no signing. Its local measurement describes the latch/admission check, not a
new measurement on every GET. An absent token, missing/expired artifact,
invalid signature, wrong run attempt, wrong target, unavailable verifier, or
changed local bytes leaves identity **BLOCKED**. Artifact retention is 90 days;
a later boot without that artifact requires a fresh canonical publication.

Offline tests use explicit synthetic attestations and cannot establish a live
deployment. Linux checks cover exact-run artifact selection, certificate
invocation replay, bounded filesystem/ZIP/JSON reads, source drift before and
after first verification, startup retries, and GET side-effect boundaries.

Prior art: [GitHub artifact attestation verification](https://cli.github.com/manual/gh_attestation_verify)
and [Sigstore certificate verification output](https://github.com/sigstore/sigstore-go/blob/main/docs/verification.md).
