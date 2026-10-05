<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SZL Holdings | Stephen P. Lutar | ORCID 0009-0001-0110-4173 -->
# Second-brain completion boundary

Evidence class: DECLARED source contract. Local hermetic tests establish only
the exercised software boundaries, not deployed health, model qualification,
scientific correctness, clinical validation, or external authorization.

## Source and wire binding

`serve.py` binds the admitted sibling `a11oy_code.py` explicitly. The flagship
`a11oy_code/` package remains unchanged; it must not shadow the deterministic
router in a full source checkout. Docker already includes the flat router and
`packages/inference/`; this change adds no payload writer or provider dependency.

The bridge follows the reviewed public producer at
[`szl-second-brain@9954209d`](https://github.com/szl-holdings/szl-second-brain/blob/9954209d99c20a960188c4938daefb6dcd87bd80/app.py),
with the response contract in
[`second_brain/retrieve.py`](https://github.com/szl-holdings/szl-second-brain/blob/9954209d99c20a960188c4938daefb6dcd87bd80/second_brain/retrieve.py).
POST requests use `query` and **`k`**, not `top_k`. The producer's returned `k`
is the hit count, not a request echo. BM25-like scores can exceed one; they are
neither probabilities nor correctness or trust scores. Optional `sourceId` and
`generation_sha256` remain upstream declarations, not independently attested
source identities or verified content bytes.

The bridge rejects wrong schemas/query bindings, non-ready/non-software data,
non-handles-only or gradient claims, invalid/duplicate handles, raw-text fields,
inconsistent counts, misaligned/nonfinite/negative scores, and invalid SHA256
pointers. Accepted values are retained without editing. No documents are hydrated.

Limits: 2,000 query characters and 8,192 UTF-8 bytes, 1–12 requested handles,
128 KiB response bytes, 64 KiB rendered context, and explicit field limits.
The timeout is a bounded **socket inactivity timeout**, not an end-to-end wall
deadline. Redirects are refused so operator queries cannot follow a new host.
Duplicate JSON object keys and malformed encodings fail closed. Failure returns
empty handles and `UNAVAILABLE`; it never fabricates retrieval.

## Policy, data and effects

All three POST completion aliases (`route`, `auto`, `complete`) call the existing
shared operator principal before body parsing, routing, retrieval, inference, or
receipt emission. Missing/wrong credentials and principal resolution failures
are refused. An unavailable auth helper is `BLOCKED`. No body field grants
authority; the byte-pinned shared auth module remains unchanged.

Anonymous callers and existing Amaru/Sentra proxies without an independently
authenticated forwarding contract are now BLOCKED at this boundary. Never fix
that by attaching a server operator credential to anonymous requests. A caller
integration must establish its own authorized principal separately.

`SZL_SECOND_BRAIN_RAG` remains OFF by default. Enabling it discloses the operator's
query to the named public Space; do not enable it for private or clinical inputs
without the appropriate separate data/authorization review. This change does not
enable it, send patient data, activate devices, train a model, or publish weights.

When enabled, validated handles are serialized as **untrusted user/data context**
after the trusted system policy and before the user's query. Upstream notes are
never system instructions. JSON escaping and role separation are defense in
depth, not a prompt-injection-resistance benchmark. The model still proposes;
it gains no kernel, tool, training, promotion or receipt-signing authority.
Formatter failures leave original messages unchanged with `used=false`.
`content_hash_verification` stays `UNKNOWN`: checking hash syntax is not checking
the referenced bytes. Legacy `LIVE` means a successful validated transport call,
not deployed/runtime or scientific qualification.

Public GET health/tiers remain read-only. Health exposes configured mode as
DECLARED, with runtime and signature verification UNKNOWN; credential presence
does not establish either. GET never probes a model or invokes the signer.

## Verification and release boundary

The existing required estate-RAG job includes `test_second_brain_bridge.py` and
`test_code_completion_boundaries.py`. The suites use synthetic wire fixtures,
registered application routes, and explicitly SIMULATED completion/emitter
doubles. Actual deterministic-router checks are separate from those doubles.
These tests do not qualify a hosted provider or model.

Protected merge, canonical HF workflow publication, byte readback, runtime probes
and independent witness remain separate gates. Existing recovery holds are
untouched. Clinical gateway status remains NOT_SITE_VALIDATED; Killinchu effectors
remain SIMULATED. No numerical model-release denominator or doctrine claim changes.
