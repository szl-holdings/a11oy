<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Fixed-plan execution observer

This source implementation is **not evidence of a live qualified deployment**. Its tests make no live model requests. The new modules belong to the provenance/services layers. The existing Series-A service, signing key, registered SQLite store, fenced StateStore and native routes keep ownership of their respective work.

`observer_runtime.py` admits an independently signed five-case plan, reserves all five attempts in the existing Series-A SQLite database, persists the exact approved plan, and obtains acknowledgment of those exact rows in immutable storage before dispatching the first case. Each case calls the actual first-match ASGI route through its middleware. Complete observations and their exact native receipts are acknowledged before the next case; the whole signed bundle is persisted and acknowledged before export. There is no generic target URL, proxy, caller-selected signer, automatic approval, retry or plan resumption.

`observer_adapters.py` validates the complete fixed scope before reservation, then checks native policy audit readback, the selected compliance source record, the declared locked-formula table and citation, actual bounded eval evidence, and engine/self-eval/composite evidence. Formula/table observations do not establish Lean verification. Model execution does not qualify a model or verify its provider internals.

`native_readbacks.py` receives full receipts from the actual native producers after signing, within a trusted observer dispatch context. It stores and links the original bytes in the registered Series-A database. Digest-only reads return already stored bytes. Completed model observations must match both their captured readback and the owning receipt/link rows in the immutable acknowledged snapshot. The observer does not manufacture a second native receipt from a returned response.

## Interfaces and lifecycle

The Series-A `register` integration reuses `app.state.szl_series_a_service` and installs `app.state.szl_execution_observer`. It also installs the real `app.state.execution_native_readbacks` owner when independent public pins are configured. The eval and agent-loop handlers consume that owner through their existing route closures, including nested self-eval. Their callbacks are inert outside an observer-owned reservation.

All four observer HTTP routes require the existing operator credential and configured tenant:

- `POST /api/a11oy/v1/series-a/execution-observations/challenge`: empty body; emits a signed, bounded-lifetime runtime challenge. This is not an approval or execution authorization.
- `POST /api/a11oy/v1/series-a/execution-observations/run`: exact JSON object `{ "plan": <independent approval DSSE>, "run_nonce": <issued nonce> }`.
- `POST /api/a11oy/v1/series-a/execution-observations/cancel/{nonce}`: empty body; burns the nonce, invalidates current exports and cancels the active internal ASGI await. Already dispatched provider work cannot be recalled or assumed cancelled.
- `GET /api/a11oy/v1/series-a/execution-observations/exports/{nonce}`: reads frozen bytes after authorization and fresh fenced-state checks. It does not sign, modify SQLite, snapshot or execute a case.

A cancellation, exception, ambiguous dispatch or incomplete acknowledgment consumes the plan. Signed-plan expiry cancels the internal native await, and strict native handlers close their shared model budget. A storage worker retains its own inflight fence until an already-started operation actually finishes; cancelling its awaiting task does not falsely report that the worker drained.

The export wrapper is `szl.execution-observation-export/v1`, with `bundle`, `storage_acknowledgment`, `archive_only`, `publication_eligible: false`, `execution_authorized: false`, and `passive_probe_modified: false`. Its bundle remains the existing `szl.execution-acceptance-bundle/v1` contract. The five passive `NOT_PROBED` results remain unchanged; separately verified execution coverage belongs to the companion consumer changes.

The internal synchronous method `Observer.context_for_bundle_digest(sha256(canonical(bundle)))` resolves only a retained, completed, current-boot export. It rechecks independent pins, current process source/HF/boot identity, fenced storage, cancellation and expiry. A submitted artifact cannot supply the context. The companion readiness reader binds this method before its worker starts and rechecks it on each served snapshot.

At startup, `restore_completed_archives()` reads already acknowledged immutable SQLite bytes and verifies the full approved plan, signed observations, exact completion metadata and owning native receipt/link records. It may restore at most eight historical exports. These are labeled `archive_only: true`, preserve the original bundle, never enter the current-boot admission cache, and cannot be replayed or used for current readiness. Restore performs no new signing, provider dispatch or snapshot publication. Missing native readback rows or unacknowledged complete bundles fail closed. Historical signatures are checked at their original validity interval; that is not a freshness assertion.

## External admission that remains required

The implementation deliberately stays disabled or refuses a run until these independent prerequisites exist:

- Exactly one deployment-selected public-pin source: `A11OY_EXECUTION_AUTHORITY_FILE` names a local public-only JSON file, or `A11OY_EXECUTION_AUTHORITY_PINS_JSON` contains the same JSON directly in runtime configuration. The schema is `szl.execution-authority-pins/v1`, with exactly `approval_public_pem`, `approval_key_id`, `runtime_public_pem`, and `runtime_key_id` in addition to `schema`. Both sources use the same 16-KiB byte limit, strict JSON parser and ECDSA P-256 public-key validation. IDs are SHA-256 values of normalized SubjectPublicKeyInfo PEM with surrounding whitespace stripped. Approval and runtime keys must be distinct. Both settings present is ambiguous and disables execution even when either value is empty; an empty or invalid sole setting also fails closed. The actual independent approval custodian and provisioning policy are not present in the available environment. No production key was generated.
- Existing operator and tenant credential bindings. These are neither recovered from artifacts nor replaced with new secret values.
- A real persistent runtime signer matching the admitted runtime public pin. The native eval signer and host engine/composite signer must also match that pin and their actual receipt contracts.
- Exact protected source identity plus an independently established immutable in-process Hugging Face revision. The implementation currently requires `SPACE_REPOSITORY_COMMIT`, but official Hugging Face documentation does not establish that the host injects this field and the available live deployment did not expose it. This remains an implementation/hosting identity gap. Setting a manually guessed variable, reading the current provider API, or copying a revision from an approved plan cannot repair that trust boundary.
- Independent source-to-Hugging-Face byte/publication binding and a current fenced, acknowledged StateStore writer. GitHub and Hugging Face commit IDs are separate identities; equal strings are not assumed.
- The companion verified-execution consumer changes and explicit trusted CI admission distribution. A signed challenge or export cannot supply its own approval pins or current context.

`register_from_service` reads the two deployment settings once when the existing service is registered. It passes explicit values to the observer constructor, which does not read those settings itself. The parsed immutable pins remain fixed for that observer's lifetime; later environment or file changes cannot replace them. No request header, query, body, plan or exported artifact installs authority. Reconfiguration requires a new observer startup and fresh admission for the resulting boot. Inline JSON removes the need to deliver a local pin file; it does not establish an independent custodian, approve execution, satisfy the immutable HF identity requirement, or configure the runtime signer.

The request limits bound client dispatch reservations, requested/reported output tokens, and cooperative elapsed time. They are not aggregate billing limits, remote cancellation, immutable weight identity, license qualification, or proof of provider-internal retries. Each model-bearing case carries its own exact approved limits; the five-case HTTP plan is not a five-provider-call claim.

## Packaging and validation

The Dockerfile copies the producer modules, `szl_execution_readiness.py`, and the acceptance parser with an explicit `tools` package marker. It combines two adjacent existing COPY instructions to retain the existing layer ceiling. Packaging checks preserve historical count/digest assertions and declare only the added source files.

Run the isolated fixture integration from the repository root:

```bash
python -m pytest -q tests/test_observer_runtime.py tests/test_native_readbacks.py tests/test_observer_adapters.py tests/test_real_execution_routes.py tests/test_combined_consumers.py
```

Tests use temporary keys and local transport fixtures. The composed five-case test executes the exact policy/compliance/formula handlers, helper functions and tables extracted from this checkout’s `serve.py`, the actual strict eval/agent ASGI handlers, code engine and host signing function. It uses real Series-A SQLite, native receipt ownership, StateStore snapshot/CAS acknowledgment, complete bundle validation, actual observer export through the collector parser, and successor-boot historical-only recovery. A separate observer/storage unit suite deliberately uses synthetic endpoint boundaries; its pass count alone does not prove native route compatibility. These controlled ASGI tests do not boot the whole production application, contact live model providers, or establish deployment admission.

The independent CI and served-consumer handoff is documented in [execution-readiness.md](execution-readiness.md).
