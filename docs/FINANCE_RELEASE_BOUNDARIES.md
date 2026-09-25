# Finance release-boundary hardening

This follow-up belongs to the existing 16-adapter backend and canonical finance
Space projection. It adds no provider, trading action, deployment workflow,
model weight, or independent authority.

## Failure is not an identity exception

Every observation, including UNAVAILABLE, carries its runtime source revision.
The public projection validates schema, source identity, disabled execution and
exact canonical source revision for HTTP 503 STALE/UNAVAILABLE responses as well
as successful responses. Nested overview observations must bind to the same
revision. A stale observation from another revision is withheld, not repainted
as current data. Missing provider provenance remains null.

The projection rejects duplicate JSON keys, non-finite numbers, unexpected MIME
types, content encodings, excessive declared or actual bytes, and read-deadline
overruns. It sends only fixed public request headers; credentials and cookies are
not forwarded. Request errors return allowlisted codes only, never arbitrary
upstream bodies. Failed reads cannot introduce account or trading authority.

## Bounded provider contention

Provider lock acquisition waits at most 250ms. Busy sources do not retain worker
threads indefinitely. A still-valid cached result remains CACHED; an expired
cached result remains STALE with its original provenance and ok=false. Without a
cached observation the result is UNAVAILABLE/PROVIDER_BUSY. Locks release even
when an unexpected internal exception propagates. These are process-local
controls, not distributed quotas or a durable trading ledger.

## Qualification scope

`tests/test_finance_release_boundaries.py` runs the actual generated Space code,
not a copied approximation, and covers these failure paths with synthetic
fixtures. It is included in both Python versions of the existing finance CI.
Provider smoke observations, browser evidence, source admission and live HF
publication evidence remain separate obligations. Passing tests does not make
credentials configured, data entitled, a model calibrated, or real money usable.

## Legacy alias closure

The pre-existing `/v1/markets/macro` and `/api/a11oy/v1/markets/macro` routes
now delegate to the same canonical FRED reader and owner-access check. The
legacy summary cannot anonymously fetch FRED with a server-held key or report
aggregate success when a child is unavailable. Credentialed results use
private/no-store responses; token-bearing query strings do not grant access.
Legacy and canonical routers are registered idempotently ahead of SPA fallbacks
on both flat and grouped FastAPI releases. Existing company/debt compatibility
representations are unchanged; their legacy period/representation semantics
are not substituted for the stricter canonical finance observation contracts.

## Source-bound analytics v2

The canonical backend composes the exact math module from
`szl-holdings/vertical-services@f487dc0fdc71af52841e3634bf7b9c6bf9fb6448`,
`services/finance/engine.py`, with SHA-256
`78816c492102ffb8b0ab958a18a89adb1e57eb77a93d1c89a7b6a92a20b691b6`.
The component loader verifies its bytes before import. A11oy retains provider
access, request validation and response semantics; the existing Finance Space
is a thin projection. Both source revisions and the component hash travel in
each response and unsigned computation receipt.

Canonical routes under `/api/a11oy/v1/finance/analytics/v2` expose GET
`signals/{symbol}`, `quote/{symbol}`, `receipts`, and `receipts/verify`, plus
stateless POST `portfolio` and `receipts/verify`. The corresponding Space routes
use `/api/finance/v2`. POST performs bounded arithmetic or integrity checks;
there is no account, order, durable ledger, signing key or trading action.

Coinbase is the default input lane, with 260 completed daily intervals,
365-day annualization, exact timestamp pairing for beta and no interpolation.
One cooldown wait of at most 355 ms respects the canonical provider limiter;
longer backoff blocks computation. Explicit `origin=fixture` uses a deterministic
synthetic walk and 252-period annualization. Caller portfolios accept at most
16 assets with 3–300 finite positive prices, labeled UNVERIFIED. Their output
contains per-asset statistics and arithmetic means, not weighted portfolio risk.
All derived analytics are MODELED, advisory and paper-only. Receipt verification
checks content integrity and never establishes authenticity.

The existing manual flagship publisher now accepts `scope=finance`. It requires
current protected main and a bound canonical synthetic analytics preflight
before publishing exactly `SZLHOLDINGS/finance`. It preserves sibling Spaces.
The existing `hf-sync.yml` remains the automatic canonical backend writer.
Source CI, container/browser tests, canonical deployment, Finance publication,
live provider observations and domain readback remain separate proof layers.
