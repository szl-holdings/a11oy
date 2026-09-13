<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Opt-in governed SZL Router integration

The existing `POST /api/a11oy/v1/govern/infer` consumer accepts
`{"prompt":"Explain this public example","effort":"szl-router"}`. The existing
`a11oy_vertical_feeds.governed_turn` executes first. Denial and human review make
no gateway call. This integration does not change default inference selection.

Configure all four variables in A11oy to admit the explicit request:

| Variable | Contract |
|---|---|
| `SZL_ROUTER_BASE_URL` | HTTPS gateway origin, optionally ending in `/v1` |
| `SZL_ROUTER_TOKEN` | Bearer credential shared with the gateway |
| `SZL_ROUTER_SOURCE_REVISION` | Exact 40-character GitHub source SHA expected from `/api/source` |
| `SZL_ROUTER_MODEL` | Public model alias admitted by the gateway provider registry |

Use a separate gateway origin; do not point these variables at A11oy or reuse
`A11OY_MODEL_BASE_URL`, `A11OY_BRAIN_URL`, `SZL_LOCAL_LLM_URL`, or
`SZL_SOVEREIGN_GATEWAY`. The adapter rejects equal origins to prevent direct
recursion. Operators must also keep the gateway's own provider registry free of
routes back to A11oy or the gateway. Redirects and ambient HTTP proxy settings are
disabled. No automatic enablement or provider secret copying occurs.

This adapter uses **`router_control.app`**, source schema `szl.router-source/v1`
and completion schema `szl.router-receipt/v1`. The older `szl_router.app` DSSE
header contract is incompatible and fails admission. Gateway source is checked
before and after the completion. `/readyz/inference` admits configuration only;
it is never treated as a successful inference. The request ID is forwarded in
`X-Request-ID` and the normalized `user` field so the receipt digest binds it.
The client requires all four controlled-file digests and the source contract's
disabled-by-default egress and secret-output guarantees. These digest claims are
not independently compared with Git file contents at request time. Synchronous
gateway transport runs in the serving thread pool so it does not block the
application event loop.

Only PUBLIC and INTERNAL data admitted by A11oy's existing sensitivity classifier
may traverse this remote gateway. Restricted/secret or unknown classifications
fail closed. Cost tier is capped at zero in this first adapter. Streaming, tool
input, and multimodal input are unavailable. The adapter preserves returned
refusals and tool-call completion fields, and never performs a fallback after
any refusal, failed request, bad receipt, or source mismatch.

Successful evidence appears under `generation`: original completion and refusal,
receipt, source revision, and request ID. The client verifies the gateway receipt
digest and header, normalized request digest, original response digest, model and
classification provenance, and the successful provider attempt. **Receipt
integrity is UNSIGNED**. It does not prove model weights, persistent execution
history, independent witnessing, or measured energy. The original A11oy governance
receipt and its actual signature state remain separate. A source GET is only a
source claim checked against an operator pin, not a provider deployment attestation.

Rollback: remove the four gateway variables and omit `effort: szl-router`.
No existing serving URL changes are required. Enabling production requires a
protected source merge, canonical HF publication, exact source/provider readback,
and a permitted live end-to-end inference witness. Local isolated tests do not
establish those proof layers.

Implementation scope: services-layer `szl_router_client.py`, its Dockerfile copy,
and the existing governed-inference consumer hook. No additional API endpoint or
Space publisher is introduced.

Validation: `.github/workflows/szl-router-consumer-contract.yml` runs the isolated
consumer contract and the same cases through router source
`091346fd29b8fec4e0f1ce056a97b66933a6a8f2`. The provider HTTP boundary supplies
synthetic completions; the actual A11oy gates and actual pinned router request,
classification, authentication, routing, and receipt code execute. Local command:
`python -m pytest -q tests/test_szl_router_client.py`. To also run the pinned peer
locally, set `SZL_ROUTER_CONTRACT_CHECKOUT` to that exact source checkout first.
