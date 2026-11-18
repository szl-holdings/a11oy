<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Configured model catalog: observation and recovery

Date: 2026-11-17. Scope: the existing local-provider observation path in
`a11oy_code_orchestrator.py` and its Second Brain projection in
`ayllu/model_binding.py`.

## What changed

The liveness and model-catalog probes now use the same existing local inference
header helper as completions. Authorization is supplied only after the requested
base exactly matches the operator-configured local base. The HF Router remains
excluded from this local credential path, including equivalent hostname casing,
IDNA normalization, and a trailing DNS dot.

A failed catalog request no longer becomes an observed empty catalog. The shared
observer supplies the liveness decision, profile inventory, and turn-level model
attestation with an explicit result:

| Observation | State | Model count |
|---|---|---|
| Valid catalog | `MODEL_CATALOG_OBSERVED` | Observed integer, including zero |
| Access denied by HTTP 401 or 403 | `MODEL_CATALOG_UNAUTHORIZED` | Unknown (`null`) |
| Invalid JSON, catalog shape, or identity row | `MODEL_CATALOG_MALFORMED` | Unknown (`null`) |
| Transport, redirect, or other retrieval failure | `MODEL_CATALOG_UNAVAILABLE` | Unknown (`null`) |
| No eligible configured local provider | `LOCAL_ENDPOINT_UNAVAILABLE` | Unknown (`null`) |

`MODEL_TAG_MISSING` is derived only after a valid catalog was observed and the
exact requested tag was absent. Case and whitespace remain identity bytes;
provider output is not repaired into a matching tag. Failed observations have
no catalog digest that could be mistaken for an observed empty inventory.

`catalog_scope: CONFIGURED_LOCAL_PROVIDER` identifies what the new diagnostics
observe. The existing `base_url` field retains the serving resolver's fallback
semantics and can identify the HF fallback when the configured local catalog is
unavailable. A status read does not invoke or attest a completion on either path.

Second Brain preserves the allowlisted reason in its profile availability state.
Its model-availability input must be literal `True`. An unbuilt index remains a
separate blocker; when model and index are both unavailable, the aggregate state
reports both and the profile retains the model-specific explanation.

## Credential and transport boundaries

Metadata reads retain the existing bounded, DNS-pinned provider transport and
resolve authorized headers for each observation. A failed authorization is not
cached across credential rotation. New failure diagnostics expose fixed states,
not provider response bodies, headers, exception messages, or additional URLs.

Authenticated metadata refuses redirects. Optional native Ollama `/api/show`
and `/api/tags` probes are permitted only for configured root or `/v1` bases
without query or fragment scope. A gateway prefix or query cannot be discarded
while forwarding its bearer to an origin-root endpoint. Catalog and completion
requests keep their configured-base behavior. The generic document helper keeps
its existing unauthenticated default and redirect policy.

## Operational interpretation

For an access-denied result, check the existing configured provider and its
credential/permission contract through the normal deployment configuration.
For malformed or unavailable results, check catalog compatibility and transport.
Only a valid catalog supports a conclusion that the exact model tag is absent.
A missing tag calls for verifying the actual loaded model and its intended
profile, without renaming an unrelated model to satisfy the comparison.

An observed tag remains `ARTIFACT_UNBOUND`. Artifact identity, evaluation,
promotion, and per-turn identity checks remain separate requirements. This
repair does not establish that catalog authorization caused the current Khipu
absence: a valid generic-model catalog was observed during the investigation.

The canonical owned GGUF loader is also not a configuration-only substitute for
the BrainNavigator provider. Ayllu uses an OpenAI-compatible catalog/completion
contract; the owned cortex exposes a different governed prompt contract. The
release records still require artifact/profile reconciliation. Relevant sources:

- [Profile observation and completion](../../a11oy_code_orchestrator.py)
- [Second Brain composition](../../ayllu/model_binding.py)
- [Ayllu completion and handle checks](../../ayllu/backend.py)
- [Owned GGUF loader](../../a11oy_governed_cortex.py)
- [Second Brain release record](../../model_release/szl-khipu-second-brain.json)
- [Forge family release record](../../model_release/szl-forge-family.json)

## Verification

The focused source run passed 81 cases: 54 catalog cases, 17 existing Forge
runtime cases, and 10 existing Second Brain contract/route/signer cases. Tests
used synthetic credentials and providers. The redirect regression exercises the
real shared transport with synthetic connections and no sockets. No live
inference, service startup, or model download was performed.

The existing `python-estate-rag` CI job now includes the Forge runtime and catalog
suites beside the Ayllu tests. The workflow already covers all PRs to `main` and
pushes to `main`. Local source checks and independent review are candidate
validation; live deployment and grounded-turn qualification require their own
source-bound observations.
