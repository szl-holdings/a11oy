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
