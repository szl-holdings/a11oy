# A11oy release-manifest evidence syntax — fail-closed validation

**Source-only security correction, November 20, 2026.** No deployment, API, payment, signer, cloud or GPU provider configuration is changed by this PR.

## Verified defect

The existing `szl_release_manifest.py` release gate returned `PASS` for a forged matching source commit such as `abc`, equal but non-SHA artifact strings, a matching non-string model identity, and a manifest with an unsupported status that `load_manifest` converted into `GENERATED`. A credential-free local reproduction against source commit `6a6f9df5417f84b4512152cead63f2b46c2b482c` returned `PASS` for each malformed case. This is a deterministic source-gate defect; we have not established an unauthorized real deployment.

An independent, source-only review was completed by **Kimi K3.1 Pro** and **Mistral Large 4** via the existing Ollama API. They independently identified the same class of fail-open status coercion and invalid matching identities. Both models ran in their cloud configurations and were given only a sanitized public module description, with no keys, private runbooks or action tools.

## Corrected contract

- Loader only accepts `GENERATED` or `PLACEHOLDER_UNTIL_CI_GENERATED`. Unknown status stays `UNAVAILABLE`, never upgraded. Duplicate JSON keys are refused before parsing.
- Direct `promotion_gate` calls independently reject unsupported statuses.
- Both runtime and manifest source revisions must be true lower-case immutable 40-hex commit strings. Matching malformed text never passes.
- Frontend/API byte-digest declarations must be lower-case 64-hex SHA-256 strings (not all zero).
- Model/deployment identity must be bounded, plain string and source-pinned as `name@sha256:<64-lowerhex>` or `name@<40-lowerhex>`. Unpinned latest tags, dictionaries/lists, booleans, whitespace and mismatching IDs refuse.
- `runtime_evidence()` calls a field `MEASURED_ENV` only if its **syntax** meets the contract. `generate_manifest` adds invalid identities to `missing` so `--require-complete` can deny. Syntax is not proof that an image, frontend, model or deployment actually exists.
- The existing honest publication-lag error remains intact.

## Bounded verification

On BETTERWITHAGE, the staged canonical source plus its existing tests and new adversarial tests passed **23/23 stdlib unit tests**. Ruff E4,E7,E9,F lint passed; the new test file was formatted with Ruff. Existing normal signed-pinned release-manifest input remains able to produce `PASS` in the **source-level predicate**, which is not an authorization to release.

See `tests/test_release_manifest_adversarial.py` for malformed status, duplicate keys, bogus source/digest, non-string or mutable model/deployment identities, generator and environment labels, plus valid controls.

**Remaining release gates:** source-owner review, protected CI, runtime artifact byte verification, signature/provenance trust, independent execution identity, actual deployed source, Cloudflare public-proof access and consumer-grade smoke/stress tests. Do not merge or deploy by model consensus alone; never let the source-level `PASS` override runtime admission.
