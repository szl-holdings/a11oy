<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Finance read-API contract

The public Finance Space (`SZLHOLDINGS/finance`) is a read-only projection of
the canonical finance API served by A11oy (`/api/a11oy/v1/finance/*`). The two
Spaces deploy independently. They are coupled by a versioned contract, not by
git revision.

## What A11oy serves

- `runtime/contract.py` declares the contract name `szl.finance.read-api`, the
  served versions (currently `1`) and the top-level response schemas each
  version covers.
- Every finance response, failures included, carries
  `X-SZL-Finance-Contract: szl.finance.read-api/1` (`routes.reply`).
- `GET /api/a11oy/v1/finance/contract` returns the same declaration plus the
  runtime's reported `source_revision`, labelled
  `EVIDENCE_NOT_COMPATIBILITY_KEY`.

Bump the version, and keep serving the old one while consumers move, when a
listed response schema or the meaning of an existing field changes
incompatibly. Additive fields keep the version.
`tests/test_finance_source_contracts.py` checks that each listed schema is one
the runtime actually emits.

## What the Finance projection accepts

`scripts/hf_finance_read_proxy.py` declares `CONTRACT.supported_versions`
(currently `(1,)`). For every upstream response it:

| Upstream condition | Projection result |
| --- | --- |
| Header names a supported version, body valid | Forwarded unchanged. The A11oy `source_revision` in the body is kept as evidence, whatever it is |
| Header absent | 503 `CANONICAL_CONTRACT_UNDECLARED` |
| Header malformed | 503 `CANONICAL_CONTRACT_INVALID` |
| Header names only unsupported versions | 503 `CANONICAL_CONTRACT_INCOMPATIBLE`, with `contract.served_versions` |
| Body reports no valid revision | 503 `CANONICAL_REVISION_UNREPORTED` |
| Nested overview revisions disagree | 503 `CANONICAL_REVISION_INCONSISTENT` |
| Unreachable, HTML, timeout | 503 `CANONICAL_SOURCE_*` |

Every existing schema, provenance-digest, receipt and component check still
applies. Only the equality between A11oy's revision and the revision Finance
was published from has been removed.

`/readyz` on Finance is ready only when its own landing and panels files
verify and the A11oy contract endpoint answers with a supported version. Any
other outcome returns 503 with `state` `INVALID`, `INCOMPATIBLE` or
`UNAVAILABLE` and the reason in `canonical_upstream`. Results are cached for 10
seconds so that readiness probes do not multiply upstream reads. `/healthz`
stays process liveness only.

The finance publish preflight (`finance_preflight` in
`scripts/hf_publish_vertical_flagships_v4.py`) applies the same rule. It
records the observed A11oy revision and contract and does not require A11oy to
run the publishing commit. `tests/test_finance_release_boundaries.py` checks that
the projection supports a version this repository serves, so a same-commit pair
is always compatible.

## Limits

- The contract version is declared by code and review. It is not a signature
  and does not prove the schemas are semantically identical across revisions.
- The analytics engine identity (`components/*/source.json`) is still pinned
  exactly. If A11oy changes that component, Finance analytics routes return
  `CANONICAL_COMPONENT_MISMATCH` until Finance is republished.
