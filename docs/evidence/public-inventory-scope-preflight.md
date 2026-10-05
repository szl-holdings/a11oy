# Public inventory preflight: one explicit predicate

The estate-release-train count comparison previously inherited whatever Hugging
Face credentials were in its environment and accepted a non-list HTTP 200 body
as an empty inventory. It compared totals only. A same-count substitution or a
partial page could therefore be mistaken for complete membership.

The native release train now additionally runs `scripts/hf_public_inventory.py`.
It makes anonymous, bounded, same-endpoint public GETs; checks explicit public
visibility, organization ownership, page completion and unique repository IDs;
and compares actual membership with the existing public card-audit manifest.
Unavailable, private, truncated or malformed evidence has null counts and null
membership; only an observed empty namespace has zero and an empty list. Both
receipt gates must pass before the existing incident can close or the non-PR
workflow succeeds. PR runs test the collector but preserve real estate drift as
an observation, not a software regression that prevents repairing the collector.

The `hf-public-author-membership/v2` predicate is recorded in config, observations
and issue diagnostics. Native kernels occupy a separate repository namespace;
identity is `(kind, id)`, so cross-namespace totals are not unique-project or
trained-model totals. Gated/disabled public metadata and a public reserved README
are included. Collections and buckets are different asset kinds and stay outside
these four repository totals. Official authenticated
inventory v2 stays separate and unchanged. No asset is deleted, hidden, renamed,
paused, re-licensed, promoted or reclassified as a fleet member by this preflight.

A full card audit is NOT silently refreshed: its observedAt, card semantic hashes,
rights claims and membership remain the source-controlled snapshot. Real current
additions/removals and public/profile/count drift remain blockers until that
snapshot and its generated projections are reviewed together. This implements
szl-holdings/.github#728's precise scoped-delta acceptance path; it does not assert
those old card snapshots are now current or that the entire estate is operational.

The original estate receipt remains byte-preserved. A separate immutable output
binds that input digest, collector/config/manifest bytes, profile/source revisions
and public page evidence. The comparator requires an explicitly empty error map
and verifies the membership digest against sorted IDs in each namespace before
reporting alignment. The checkout identity is not a runtime attestation.
Both membership collectors retain null evidence on failures. Existing canonical
writers, schedules, permissions and runtime/quality/fallback gates are unchanged.
This is read-only membership validation,
not model inference or production authorization.

Tests: `python tests/test_hf_public_inventory.py` (offline fixtures). The native
release workflow also runs the existing release-vector controller tests and
uploads both complete or failed evidence records under the original run/attempt.
