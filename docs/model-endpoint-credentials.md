<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Model endpoint credentials

The code engine selects one configured OpenAI-compatible endpoint from
`A11OY_BRAIN_URL`, `A11OY_MODEL_BASE_URL`, or `HF_ROUTER_BASE`, in that order.
Its default is `https://router.huggingface.co/v1`.

| Destination | Authorization |
| --- | --- |
| Exact `https://router.huggingface.co` origin, absent port or port 443 | Existing detected Hugging Face token |
| A custom HTTPS endpoint | Only `A11OY_MODEL_API_KEY`, when explicitly configured |
| A custom endpoint with `A11OY_MODEL_API_KEY` absent | No Authorization header |

Custom endpoints never receive an inherited Hugging Face token. A lookalike
hostname is a custom endpoint. Blank or malformed configured credentials refuse
dispatch instead of silently becoming anonymous. Credentials must be at most
4096 ASCII bearer-token characters: letters, digits, `-`, `.`, `_`, `~`, `+`,
`/`, with optional trailing `=` padding. Do not put credentials in endpoint URLs.

Both HTTP clients reject redirects, including same-origin redirects. Resolve a
provider's final endpoint explicitly. A rejected credential or redirect is a
terminal result in the legacy client; it is not retried against the roster.
Error results do not include transport exception text or credential values.

The strict bounded transport retains its HTTPS port 443, fixed model, usage
accounting, resource budget, and no-retry requirements. Legacy anonymous HTTP
services remain supported. Sending a bearer credential over HTTP is refused.
This document does not authorize a network request or configure a provider.

For a custom authenticated provider, set its final HTTPS base URL and a separate
`A11OY_MODEL_API_KEY` through the runtime's secret manager. An existing custom
endpoint that previously relied on the inherited HF token must receive its own
dedicated credential before activation. Do not commit secret values or include
them in receipts. No runtime secrets are changed by this source patch.

Endpoint configuration and a declared GPU label do not establish runtime
availability, local execution, hardware identity, or model qualification.
The paired A11oy and Killinchu engine files use the existing shared payload
manifest for byte parity. Source parity is separate from deployed parity.
