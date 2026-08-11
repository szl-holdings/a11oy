# Public experience runtime contract

This directory defines how a11oy and the SZL public estate communicate state to investors, developers, and evaluators.

## State machine

Network-dependent UI may begin in `OBSERVING`, but it must terminate within eight seconds as one of:

```text
VERIFIED
REACHABLE
DEGRADED
STALE
FAILED
BLOCKED
UNAVAILABLE
```

`CHECKING`, `CONNECTING`, and `LOADING` are not terminal public states.

## Meaning

- `VERIFIED` — the stated verification procedure passed for the stated scope.
- `REACHABLE` — transport answered; readiness and authorization are not implied.
- `DEGRADED` — the interface works with a declared reduction in evidence or capability.
- `STALE` — the last known observation exceeded its freshness contract.
- `FAILED` — a completed procedure returned a negative result.
- `BLOCKED` — policy, approval, evidence, release, or source-binding gates prevent promotion.
- `UNAVAILABLE` — no fresh conclusion can be established.

## Source of truth

`scripts/build_public_source_of_truth.py` produces a digest-bound contract. External values are accepted only when the observation supplies a value, evidence label, timestamp, and source. Missing or malformed observations become:

```json
{"value": null, "label": "UNAVAILABLE", "observed_at": null}
```

The generator never carries a previous count forward.

## Public claim boundary

- Lambda uniqueness is `Conjecture 1`.
- Reachability is not readiness, safety, model quality, compliance, adoption, or authorization.
- A signature proves integrity and origin within its declared scope, not factual accuracy.
- Read-only observations do not mint receipts unless the read itself is the governed action.
