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
Downstream engine copies must include their reviewed runtime dependency closure.
Historical shared payloads do not establish current source or deployed parity.

## Optional Cloudflare Access for the bounded model client

The services-layer `szl_model_access.py` helper supports a separately provisioned
model Access application using these server-side names:

| Setting | Kind | Contract |
| --- | --- | --- |
| `A11OY_MODEL_CF_ACCESS_ORIGIN` | Variable | One exact HTTPS origin on port 443; no user information, query, fragment or non-root path |
| `A11OY_MODEL_CF_ACCESS_CLIENT_ID` | Secret | Dedicated model service-token Client ID |
| `A11OY_MODEL_CF_ACCESS_CLIENT_SECRET` | Secret | Its paired Client Secret |

The client sends `CF-Access-Client-Id` and `CF-Access-Client-Secret` alongside the
existing `Authorization` bearer when `A11OY_MODEL_API_KEY` is configured. It never
uses meter credentials, a browser cookie, an inherited HF token, or the legacy
sovereign gateway keys for this protected code-endpoint contract. Both legacy
hexadecimal and newer `cfast_` Access secrets fit the accepted header alphabet;
local format validation does not establish that Cloudflare accepts a credential.

All three Access settings absent preserves the existing clients. Any one present
requires complete valid configuration and an exact destination-origin match.
An invalid or mismatched setting refuses dispatch before networking. This also
prevents stale Access configuration from falling back to the official HF origin.
With Access enabled, ordinary code-engine calls use the existing strict transport:
one selected model, one request, a 30-second bound, the requested output budget,
response identity validation, and no redirects. A caller must select a model or
configure a valid `A11OY_MODEL_ID`; the legacy retry roster is not used.

The registry observes one authenticated `/v1/models` GET for the explicitly
selected `A11OY_BRAIN_URL` or `A11OY_MODEL_BASE_URL`. It uses the same dedicated
model bearer, rejects redirects, and performs no generation or signing. Other
explicit registry targets are refused while this contract is enabled. Catalog
reachability does not establish inference, ownership, or production acceptance.
The registry's legacy generation method refuses this protected contract; the
older orchestration, streaming, and energy adapters remain separate and are not
qualified by enabling these settings. In particular, the VM Bonsai gateway has
no native embedding interface and does not accept streaming requests.

Deployment and configuration remain separate work. Before activation, the
configuration owner must verify the Access application's hostname/path and
Service Auth policy, the designated token's authority and validity, and secure
provisioning. Preserve the gateway's separate bearer authentication. The
qualification owner must retain an authorized bounded inference outcome and the
existing independently admitted execution evidence for the final source and boot.
This source change provisions no credentials and claims no live qualification.

Cloudflare's [service-token contract](https://developers.cloudflare.com/cloudflare-one/access-controls/service-credentials/service-tokens/)
documents the two headers and Service Auth policy. The two-header mode preserves
the model gateway's independent `Authorization` header.
