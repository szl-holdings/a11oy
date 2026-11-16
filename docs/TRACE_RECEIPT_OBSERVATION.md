# Cortex receipt observations

Taxonomy: **services / observability**. Implementation: `vsp_otel/trace_ir.py`,
integrated by `a11oy_governed_cortex.py`.

## Runtime contract

A successful POST to the owned Khipu cortex's `/api/v2/governed-infer` appends
`trace_observation` after the existing inference and Nemo checks succeed.
The object links the current server trace/span to the host-computed receipt
digest, verified model digest and source revision. It accepts no free-text
attributes, prompt, output, evidence text, token, exception message or energy
object.

The sidecar is an **UNSIGNED_DERIVED_OBSERVATION**, with `authority: NONE`,
`delivery: RESPONSE_SIDECAR_ONLY`, `persistence: RESPONSE_ONLY`, and
`collector_delivery: UNVERIFIED`. It does not write a store or send a separate
export request. An existing OTLP exporter being configured does not establish
collector delivery of this object.

The original receipt payload and its serializer/digest are unchanged. Cortex
receipts remain `UNSIGNED_RUNTIME` and `EPHEMERAL_PROCESS_MEMORY_ONLY`.
No new receipt, signature or observation is minted by discovery/GET routes.
The contract GET declares the sidecar schema but is not an observation event.

## Structural consistency diagnostic

The required checks are fixed by the host:

| Check | Meaning |
| --- | --- |
| receipt_digest_match | Existing receipt digest equals recomputation using the existing receipt serializer |
| model_digest_match | Response and receipt model digests equal the cortex's pinned artifact digest |
| source_revision_match | Response and receipt source revisions equal the running source identity |
| nemo_pre_allow | Exactly one pre-generation witness declares ALLOW |
| nemo_text_allow | Exactly one text witness declares ALLOW |
| nemo_post_allow | Exactly one post-generation witness declares ALLOW |
| unsigned_receipt_declared | The existing receipt explicitly declares UNSIGNED_RUNTIME |
| proposal_only | Response and linked receipt retain proposal-only/no-execution authority fields |

`gated_minimum` is a bounded structural diagnostic. It requires explicit,
nonempty, unique required coverage; exact dictionary/string key types; and
numeric scores and threshold in [0, 1], excluding booleans and coercion.
Missing or unexpected checks, NaN, infinity, huge out-of-range integers and
malformed policy produce HOLD with fixed reason codes and strict JSON.
Invalid supplied names, values and exception text are never echoed.

For the cortex the threshold is 1 and each host-computed structural check is
0 or 1. PASS means these checks are consistent. It does not establish output
correctness, independent proof execution, a valid signature, replay resistance,
durable receipt storage, model quality or action authority. It does not replace
the canonical geometric-mean public admit contract or authorize release.

An absent/invalid server trace context or HOLD yields an UNAVAILABLE sidecar.
A diagnostic construction error is isolated after inference and returns a
fixed UNAVAILABLE reason. Existing inference/Nemo failures retain their
existing error response and do not create a success observation.

## Trace and hash profiles

The route reads the current `request.state.traceparent` from the existing
middleware. The current server span is the parsed `parent_id`; the sidecar
describes that same operation rather than inventing a child span. It does not
derive a trace identifier from the deterministic cortex request identifier.
Repeated requests therefore retain the middleware's per-request span behavior.

`observation_sha256` hashes all other sidecar fields using sorted-key, compact
UTF-8 Python JSON with `ensure_ascii=False` and `allow_nan=False`.
This is a deterministic representation checksum, not RFC 8785 canonicalization,
authentication, a signature or a proof. Receipt bytes use the unchanged receipt
profile. The sidecar deliberately omits additional prompt/output hashes.

Prior art and compatibility references:

- [W3C Trace Context](https://www.w3.org/TR/trace-context/) for propagation and
  trace/span identifiers.
- [OpenTelemetry OTLP exporter specification](https://opentelemetry.io/docs/specs/otel/protocol/exporter/)
  for distinguishing exporter configuration from successful delivery.

This change adds no claim of conformance to evolving GenAI semantic-convention
versions and changes no existing telemetry field meanings.

## Packaging and production surfaces

The canonical Dockerfile explicitly copies `vsp_otel/trace_ir.py` alongside
the existing package files. The deployment publisher derives its allowlist from
Dockerfile COPY sources; no second Space writer is added.
`tests/test_vsp_otel_packaging.py` imports the package from that copied closure
in an isolated Python process, with the source checkout absent from its path.

The owned Python cortex runs at
`https://szlholdings-a11oy.hf.space/api/v2/governed-infer`.
The product domain's `a-11-oy.com/api/v2/*` is separately implemented by
`cloudflare/a11oy-governed-inference-worker.mjs`, as configured in
`.github/workflows/deploy-cloudflare-governed-inference.yml`.
Deploying the cortex does not deploy this sidecar to that Worker.
`a11oy.net` is the documented static proof registry.

Verify the source revision at the origin's `/api/build-info`, its contract,
the exact successful POST result and the HF runtime commit before describing
the origin feature as deployed. Health alone does not validate an inference
response. Cross-origin rollout and collector delivery remain separate checks.

## Regression coverage

The owned-cortex workflow runs the existing pinned-Nemo suite together with:

- `tests/test_trace_ir.py`: malformed policy/coverage, numeric boundaries,
  strict JSON, key impersonation, context/hash validation and content exclusion.
- `tests/test_cortex_trace_observation.py`: actual ASGI middleware relationship,
  receipt byte preservation, metadata inconsistencies, telemetry failure
  isolation, unchanged denial behavior and read-only discovery behavior.
- `tests/test_vsp_otel_packaging.py`: imports from the deployed file closure.

No scheduler policy, model evaluation, model promotion, action admission,
signing, storage, DNS or Access configuration is changed by this module.
