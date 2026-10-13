<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Finance read-API contract

The public Finance Space (`SZLHOLDINGS/finance`) is a read-only projection of
the canonical finance API served by A11oy (`/api/a11oy/v1/finance/*`). The two
Spaces deploy independently. They are coupled by a versioned contract and by
the exact analytics and signed-price component pins, not by git revision.

## What A11oy serves

- `runtime/contract.py` declares the contract name `szl.finance.read-api`, the
  served versions (currently `1`), and for each version its finance routes
  (`ROUTES`) and top-level response schemas (`RESPONSE_SCHEMAS`).
- Every response the finance route handlers produce (`routes.reply`), failures
  included, carries `X-SZL-Finance-Contract: szl.finance.read-api/1`.
  Framework-generated 404/405 replies for undeclared paths or methods carry no
  header; the projection reports those as `CANONICAL_CONTRACT_UNDECLARED`.
- `GET /api/a11oy/v1/finance/contract` returns the same declaration, the exact
  component bindings (`components.analytics` from
  `components/finance_v2/source.json`, `components.signed_price` from
  `components/puriq_verity/source.json`) and the runtime's reported
  `source_revision`, labelled `EVIDENCE_NOT_COMPATIBILITY_KEY`.

`tests/test_finance_source_contracts.py` checks that the router serves exactly
the declared routes and freezes version 1's routes and schemas.
`tests/test_finance_functional_gate.py::test_canonical_sweep_accepts_a_compatible_runtime_on_every_contract_route`
drives the real router through every declared route and checks that every
declared schema comes back and passes the projection's emitted validators.

## Changing the contract

A released version never changes. Adding a route or response schema, or
changing an existing one incompatibly, defines a new version. Additive fields
in an existing body keep the version.

A response declares every version whose rules it satisfies; there is no
per-request version selection. So:

- A purely additive version 2 (version 1's routes and bodies unchanged) is
  declared beside version 1 (`szl.finance.read-api/1,szl.finance.read-api/2`).
  A Finance build that supports only 1 keeps working. A Finance build that needs
  version 2's routes declares `supported_versions = (2,)`, and its publish
  preflight refuses to write until the running A11oy declares 2.
- An incompatible change drops version 1 from what A11oy declares. Finance
  answers `CANONICAL_CONTRACT_INCOMPATIBLE` until it is republished for the new
  version. This needs a coordinated rollout: deploy A11oy, then republish
  Finance.

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
| Nested overview or analytics (Coinbase input) revisions disagree with the envelope | 503 `CANONICAL_REVISION_INCONSISTENT` |
| Analytics body carries another `finance_v2` component | 503 `CANONICAL_COMPONENT_MISMATCH` |
| Signed-price body carries another `puriq_verity` component, or fails any signed-price check | 503 `CANONICAL_SIGNED_PRICE_INVALID` |
| Unreachable, HTML, timeout | 503 `CANONICAL_SOURCE_*` |

The schema, provenance-digest, receipt and component checks are the ones the
projection applied before. The equality between A11oy's revision and the
revision Finance was published from is gone. It is replaced by the contract
check, and by the requirement that every nested observation in one overview
or analytics answer carries that answer's revision.

## Readiness

`/readyz` on Finance uses the same fields as the other vertical shells:
`checks.upstream` and an `upstream` object. It is ready only when the landing
and panels files verify, the A11oy contract endpoint declares a supported
version with a valid descriptor, and the declared component bindings equal the
ones this build pins. Otherwise it returns 503 with one of these `state` values:

| `state` | Meaning |
| --- | --- |
| `INVALID` | A local landing or panels digest does not verify |
| `UPSTREAM_UNAVAILABLE` | A11oy unreachable, timed out, non-JSON or non-200 |
| `CONTRACT_UNDECLARED` | A11oy answered without a contract header |
| `CONTRACT_INVALID` | Malformed header, or a contract descriptor that is invalid or disagrees with its header |
| `INCOMPATIBLE` | A well-formed declaration with no supported version |
| `COMPONENT_MISMATCH` | Compatible contract, but A11oy serves other analytics or signed-price components |

The reason code is in `upstream.reason`. Readiness reads the contract endpoint
only. It does not call each data route; a provider outage behind a data route
is reported by that route, not by `/readyz`.

Concurrent readiness requests share one upstream read: a lock admits one read
at a time, and callers that arrive during it get its result. The result is
cached for 10 seconds from when that read completes, so a probe stored later
was also started later. `/healthz` stays process liveness only.

## Publishing Finance

`finance_preflight` in `scripts/hf_publish_vertical_flagships_v4.py` runs
before any write and does not require A11oy to run the publishing commit. It:

1. requires the publishing commit to be current `main`;
2. checks one synthetic analytics answer and its receipt directly;
3. runs `observe_canonical` from `scripts/hf_finance_functional_gate.py`
   against `https://szlholdings-a11oy.hf.space`. That sends every data request
   the post-write functional gate sends (all but its Finance-only build-info,
   version and private-source checks), plus the contract, overview, a public
   observation, both receipt capability reads and a synthetic research audit,
   so every declared route is covered. Each answer must declare a supported
   contract and pass this build's emitted validators, and the contract must
   declare this build's component pins.

If any step fails, nothing is written and the run fails, naming each failed
route and reason. On success the witness, including the A11oy revisions that
answered, is recorded in the publication receipt
(`canonical_preflight.canonical_compatibility`). Live-provider routes (Coinbase signals,
signed BTC) are part of the sweep, so a provider outage also stops a publish:
the post-write gate requires them as well.

## Limits

- The contract version is declared by code and review. It is not a signature
  and does not prove the schemas are semantically identical across revisions.
- The component pins are exact. If A11oy changes either component, Finance
  readiness reports `COMPONENT_MISMATCH` and the affected routes fail closed
  until Finance is republished from a commit with the same pins.
- The preflight observes A11oy at one moment. A deploy of A11oy between the
  preflight and the write is not prevented; the post-write functional gate and
  `/readyz` report it.
