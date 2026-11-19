<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Command Centre cache-policy observation

This is a read-only supply-chain diagnostic, not a cache repair or deployment
approval. It observes the existing a-11-oy.com Cloudflare owner for four mutable
assets whose Python registrar supplies Cache-Control: no-store:

- /command-centre/app.js
- /command-centre/style.css
- /command-centre/szl/szl-design-system.css
- /command-centre/szl/szl-console.css

The incident motivating this observer was a product-domain asset that disagreed
with its current same-origin source manifest. A fresh query key returned current
bytes, while the original key retained an older body. That observation identifies
a delivery problem; it does not by itself identify a particular live rule.

## Invocation and authority

After this workflow is reviewed and present on protected main, the existing
production owner can invoke:

~~~sh
gh workflow run audit-command-centre-cache-policy.yml \
  --repo szl-holdings/a11oy --ref main
~~~

The workflow is manual-only, has contents:read GitHub permissions, uses the
existing production environment and CLOUDFLARE_API_TOKEN, and shares the existing
edge controller's concurrency group. Its contract job runs without the provider
credential. Both workflow and helper refuse a GitHub Actions invocation outside
the canonical repository's main/manual-dispatch context. Production environment
approval and branch policies remain applicable.

A new workflow must exist on the default branch before GitHub can dispatch it.
This change does not provide a branch-execution bypass. Local review is offline:

~~~sh
python -B -m unittest tests.test_cloudflare_command_centre_cache_audit -v
~~~

An operator who already has the existing credential in their environment may
run the same GET-only helper directly, choosing a new report filename:

~~~sh
python -B scripts/audit_cloudflare_command_centre_cache.py \
  --report /tmp/command-centre-cache-observation.json
~~~

There is no token argument, arbitrary URL/zone/Worker argument, apply option,
credential installation, rule update, cache purge, Worker upload or DNS change.
The report is created exclusively; an existing file is not overwritten.

The existing production edge controller and its immutable-Worker/route
transition guards are unchanged. Its previous dry-run observes routes and DNS,
not these cache-policy surfaces.

## What is read

The helper resolves exactly one active a-11-oy.com zone, validates its opaque
zone/account identifiers, and inspects the apex Worker route. A content-addressed
Worker must match the checked-out canonical Worker source's name, or be the
existing named v3 owner. A unique exact apex binding permits that known Worker's
settings GET. The separate worker_route observation remains UNAVAILABLE when
any route pattern is unrecognized, including a potentially unrelated route.
Safe counts and refusal reasons distinguish missing/ambiguous apex bindings,
unrecognized Workers, malformed route metadata and uncertain coverage without
retaining arbitrary route patterns or script names. Reading the known Worker's
metadata does not certify which Worker handles the four asset URLs.
Source bytes on Cloudflare are not fetched or attested.

Only fixed GET endpoints under https://api.cloudflare.com/client/v4 are used:

| Surface | Observation |
| --- | --- |
| Zone and Worker routes | Fixed zone identity, owned apex route, end-of-run ownership recheck |
| Zone ruleset index | Entry-point presence information for the three inspected phases |
| http_request_cache_settings | Cache eligibility, bounded TTL settings, custom-key presence, rule identifiers |
| http_response_cache_settings | Corresponding bounded cache-response policy projection |
| http_response_headers_transform | Only changes to known cache-related response headers |
| Active Page Rules | Cache-related actions; target expressions remain redacted |
| browser_cache_ttl / cache_level | Typed zone settings |
| Owned Worker settings | Declared compatibility date/flags, cache_options booleans, counts of explicit entrypoint cache overrides |

The source uses the existing szl_provider_http transport with exact HTTP 200
success, TLS verification, private-address refusal, redirects disabled, an
eight-second request deadline and a 512 KiB response cap. The audit allows
sixteen logical GET calls and a ninety-second overall network budget. The normal
complete read uses eleven calls. Transport address fallback stays within each
call's deadline. Zone discovery requests one page of at most 50 rows and requires
page-completion metadata. The ruleset index requests per_page=50 and requires
explicit cursor-completion metadata. A continuation cursor, absent completion
metadata, oversized response or exhausted budget produces an incomplete
observation; no cursor or pagination link is followed or retained. Workers Routes
and Page Rules are unpaginated API collections. Every collection has a local
200-row processing cap; rule projections and nested arrays have further bounds.

## Privacy and evidence limits

Raw provider responses are never artifacts or log output. The projection omits
bindings, cookie/header names and values from custom cache keys, unknown response
header names/values, rule descriptions, and raw rule/target expressions.
Expressions retain only a checksum, fixed public literals, and recognized field
names. Seeing one of those literals does not establish that a rule matches.
Known Cache-Control directives and numeric TTLs may be retained; arbitrary
directive arguments are omitted. Cache Response Rules retain only fixed directive
names, set/remove operations, bounded numeric durations and cloudflare_only
booleans. Qualifiers and cache tags remain redacted. Malformed nested fields make
the affected observation incomplete while other safe observations survive.
The CLI refuses a report containing the bearer.

A successful collection is OBSERVED, not LIVE, repaired, attested, or ready.
Effective policy is NOT_EVALUATED: this GET-only observer does not invoke
Cloudflare Trace, evaluate arbitrary expressions, fetch browser cookies, or prove
which cache layer supplied an asset. Provider reads are not an atomic snapshot.
Collection time does not establish continuing freshness.

FORBIDDEN and UNAUTHENTICATED are distinct from missing configuration. A 404
alone is NOT_FOUND_UNCONFIRMED. A phase is ABSENT only when a successfully read
complete zone ruleset index lacks that zone entry point and the phase GET also
returns 404. The Worker script-and-version settings API supplies
cache_options.enabled and cache_options.cross_version_cache. Worker entries in
the exports map may supply a cache.enabled override; only counts of enabled,
disabled and unreported overrides are retained, never export names or bindings.
Missing cache metadata is NOT_REPORTED, never presumed disabled. Explicit false
is retained as false. Malformed or oversized metadata makes the observation
partial. These settings do not establish an asset's effective cache policy.

PARTIAL or UNAVAILABLE returns exit code 2, while retaining a safe report where
possible. The workflow uploads that report even when the observation step fails.
No raw provider exception is included in a report or log.

The existing credential's actual permissions are not inferred from its name.
Denied cache/ruleset or Worker reads remain explicit. This helper does not
request additional permissions or create credentials.

A later repair requires separately reviewed exact policy changes and cache-key
ownership. A fetch-cache key can be the HF subrequest URL rather than the product
URL. Worker-response caching is a different layer. Neither an acknowledged
purge nor a successful query-string request proves the original URL is repaired.

## Primary references

- [Ruleset list and cursor pagination](https://developers.cloudflare.com/api/resources/rulesets/methods/list/)
- [Cache Rules API and phase](https://developers.cloudflare.com/cache/how-to/cache-rules/create-api/)
- [Cache Response Rules API and phase](https://developers.cloudflare.com/cache/how-to/cache-response-rules/create-api/)
- [Workers and Cache Rules](https://developers.cloudflare.com/cache/interaction-cloudflare-products/workers-cache-rules/)
- [Worker settings API](https://developers.cloudflare.com/api/resources/workers/subresources/scripts/subresources/script_and_version_settings/methods/get/)
- [Workers cache configuration](https://developers.cloudflare.com/workers/cache/configuration/)
- [Worker fetch-cache ownership and purge keys](https://developers.cloudflare.com/workers/reference/how-the-cache-works/)
