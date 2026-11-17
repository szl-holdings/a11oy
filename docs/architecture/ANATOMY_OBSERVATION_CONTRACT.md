<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Anatomy observation contract

Contract: `szl.anatomy.observation/v1`.
Implementation: [szl_anatomy_3d.py](../../szl_anatomy_3d.py).
Scope: the seven legacy Anatomy 3D pages and their v4 endpoints. This is a read model, not an execution-admission or production-readiness API.

## Routes and effects

All API paths below start with `/api/{ns}/v4`. A namespace must match `[A-Za-z0-9][A-Za-z0-9_-]{0,63}`.

| Method | Suffix | Meaning |
| --- | --- | --- |
| GET, HEAD | `/yuyay-13/vote` | Read the last admitted sample-vote summary in this process and namespace |
| GET, HEAD | `/orchestrate/routing` | Read the last admitted sample-routing summary |
| GET, HEAD | `/lambda/convergence` | Derive the displayed sample convergence from that same retained vote |
| GET, HEAD | `/khipu/chain` | Inspect one existing namespace/organ chain; never allocate or seed a chain |
| GET, HEAD | `/spans/recent` | Read a minimized, bounded process-wide trace projection |
| GET, HEAD | `/immune/observation` | Return modeled gate geometry; no evaluator or cross-organ request |
| GET, HEAD | `/body/composed` | Compose partial observations and explicit per-anatomy states |
| POST | `/yuyay-13/vote` | Operator-gated sample evaluation and existing receipt path |
| POST | `/orchestrate/routing` | Operator-gated advisory route selection and existing receipt path |

The public pages are `/yuyay-13`, `/khipu-chain-3d`, `/immune-3d`, `/lambda-spine-3d`, `/nervous-3d`, `/wires-3d`, and `/body-3d`. The existing `/body-3d-v6` redirect to `/holographic#brainreranker` remains separate.

The blood endpoint's `organ` query permits `yuyay`, `kallpa`, and historical `anatomy`; the default is `yuyay`. The page lets the reader inspect the two retained action chains. Returned records identify their actual organ. No response merges independent heads into a synthetic chain. The `since` filter is a finite nonnegative timestamp.

## Observation envelope

These fields have distinct meanings and are validated together by the shared page code.

| Field | Meaning |
| --- | --- |
| `schema`, `ns`, `kind` | Exact version, namespace, and expected page subject |
| `mode` | Always `READ_ONLY` |
| `state` | `OBSERVED`, `STALE`, `UNAVAILABLE`, or `MODELED` |
| `reason` | Bounded machine-readable explanation |
| `evidence_class` | `SAMPLE`, `MODELED`, or `UNAVAILABLE`; not a measured-energy label |
| `observed_at`, `age_seconds` | Actual retained observation time and age, or null; a read does not renew the time |
| `max_age_seconds` | 60 |
| `storage_writes`, `receipt_minted_on_get` | Zero and false; GET has no application write path |
| `model_invoked`, `execution_performed`, `execution_authorized` | False; an observation never supplies authority |
| `source_revision`, `runtime_boot_id` | Null in v1 because this adapter has no independently established binding |
| `identity_binding` | `NOT_ESTABLISHED` |
| `signature_verified`, `signature_verification` | False and `NOT_PERFORMED`; no signer/key resolver is consulted by reads |
| `receipt_signature_status` | `NOT_ESTABLISHED`, `UNVERIFIED`, or `UNSIGNED`; retained signature-shaped metadata is not verification |
| `signature_count`, `receipt_sha256` | Bounded retained receipt metadata, or zero/null; never synthesized on GET |
| `chain_integrity` | Explicit verification state, checked-record count, suffix scope, and prefix coverage |
| `chain_verified` | Can establish only internally consistent complete retained hash linkage; it is never DSSE verification |
| `joules_measured`, `energy_label` | Null and `UNAVAILABLE` |
| `data_scope`, `bounded` | The projection's actual process/namespace scope and its enforced bounds |
| `data` | Per-kind projection, or null; unavailable values must not be represented as favorable defaults |

An `OBSERVED` state means a recent sample or metadata record was observed. It does not mean an approved workload ran, a model is ready, a signature verified, or a theorem was proved. A composed body can be `OBSERVED` with only partial observations; its data explicitly reports `operational_readiness: NOT_ESTABLISHED`.

An empty source is `UNAVAILABLE`, not a successfully verified empty chain. `EMPTY` is not a valid v1 state. Modeled immune geometry is the only standalone `MODELED` observation; other static shapes remain visibly modeled even when no API observation is available.

## Write admission and failure behavior

Both POSTs are covered by the shared operator middleware and a standalone handler guard. Refusal occurs before reading the request body. There is no browser-generated POST or public convenience path around this gate.

Authorized bodies are bounded to 16 KiB and decoded as JSON objects with duplicate-field and nonfinite-number rejection. Vote scores must be finite values in [0,1] for declared axes. Routing permits at most 16 uniquely named routes with finite, bounded advisory costs. Unknown fields are rejected.

An unauthorized request receives the operator refusal. Invalid admitted input receives HTTP 400. An action failure returns HTTP 503 with `retry_authorized: false`; a caller must not infer absence of effects from an error. If the display cache fails after the action was attempted, the response reports that cache failure without converting it into an automatic retry instruction.

The vote and routing math retain their existing sample/advisory role. A successful sample response does not grant infrastructure execution. Caller-supplied route admissibility is labeled as a sample filter. Numeric route energy inputs are not meter-derived joules.

## Bounded state and privacy

The cache retains only heart and wires summaries: at most eight namespaces, two operation slots per namespace, and 16 KiB per observation. Writes deep-copy the admitted summary; reads deep-copy it without moving eviction order, refreshing age, signing, or persisting. Its monotonic age expires after 60 seconds. A restart can remove it. It is not a durable audit log.

Chain inspection reads at most 60 existing records under the existing registry and DAG locks. It checks canonical hash inputs and adjacent links. A retained suffix cannot establish an unobserved prefix. It exports no receipt payload or signature body and does not call a lazy DAG constructor.

Trace inspection uses at most 20 already-collected summaries. It does not start a collector or import a provider. Process-wide scope is explicit. Raw trace names, inbound IDs, attributes, prompts, and tool arguments are excluded from the public view; the minimized projection uses fixed labels and an opaque correlation reference. Correlation does not establish a completed or authorized action.

The composed body does not create a receipt. It keeps modeled brain/immune geometry, missing data, sample evidence, chain scope, and trace scope distinct.

## Browser behavior

All seven pages use the existing local Three.js r128 asset and shared Kanchay stylesheet. No runtime CDN or remote evaluator is introduced. The immune silhouette uses supported geometry.

Polls use GET with no credentials, redirects, or response caching. They are bounded by a five-second deadline and 64 KiB response limit, with a 15-second interval while visible. The page validates schema, namespace, kind, field shapes, and freshness before rendering observations. Errors clear dynamic geometry, pickable references, and open evidence cards. Old observations cannot remain favorable after a failed read.

Dynamic geometry and materials are disposed between observations. Reduced-motion preference is respected. Page lifecycle cleanup cancels outstanding requests and timers; persisted-page restoration resumes one polling loop.

Evidence cards use text nodes and fixed DOI destinations. Returned metadata is not inserted as active HTML. Static formula cards are labeled historical/modeled. The module's declared historical 749/14/163 snapshot is associated with Lean commit `1dca00032dfc9aa8559cc6c2e4b63192fcf52371`. This repair does not revalidate that historical count or present it as a current proof inventory.

## Verification and compatibility

The registered-route suite traps evaluator, signer, key-resolution, append, and lazy-store paths on reads. It also exercises handler and middleware refusal before body parsing, namespaces, cache bounds/expiry, malformed numbers, partial failures, and authorized write-to-read projection.

The offline browser suite loads actual page builders, vendored Three.js, and local CSS. It captures all requested methods, blocks unrecognized network access, exercises failure transitions and bounded scene resources, and consumes current backend-generated default envelopes. It does not import a production signer or use a real browser profile.

The v4 GET payloads now use the versioned envelope rather than the former loose fields. Tracked consumer searches found no callers of these v4 paths outside this module and the deliberately updated legacy span test. External consumers must use the envelope and explicit organ scope. The scoped CI workflow is [anatomy-observation-contract.yml](../../.github/workflows/anatomy-observation-contract.yml).

These tests establish the bounded source contract. Deployment and operational readiness still require the repository's existing human review, governed publication, runtime identity readback, and workload-specific evidence.
