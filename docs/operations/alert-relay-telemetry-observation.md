<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Alert relay telemetry observation

## Purpose and evidence boundary

The diagnostic reads a bounded set of provider timing aggregates for the fixed
Cloudflare Worker service `szl-alert-relay`. It produces unsigned operational
observations. An `OBSERVED` result means that the expected numerical response
was received; delivery always remains `UNVERIFIED`.

The initial window is 2026-11-16 22:52:20–22:54:20 UTC, surrounding the timed-out
post-deployment canary in
[relay workflow run 43973289681](https://github.com/szl-holdings/a11oy/actions/runs/43973289681).
This diagnostic does not repeat that publication. Its time window may include
other requests to the same service, so the observations cannot identify a single
canary or establish a specific Worker version.

The implementation belongs to the supply-chain operational evidence layer. It
adds no application route, signer, durable store, deployment writer, or formula.
Provider telemetry is distinct from independently verified execution, a signed
receipt, or measured energy.

## Authorized execution

The workflow is `.github/workflows/audit-alert-relay-telemetry.yml`.
Pull requests and pushes run the offline contract suite. A provider observation
runs only after manual dispatch on protected `main`, through the existing
`production` environment, after that suite passes.

The provider job checks out the event SHA, requires a clean checkout and
protected-main ancestry, and compares its workflow, script, tests, and operating
notes with current main before using credentials. It runs Python in isolated
mode with bytecode writing disabled.

There are exactly two dispatch inputs: aware ISO start and end timestamps.
The interval must be positive and at most 15 minutes. Values enter shell
commands through environment variables and quoted arguments. Invalid timestamps,
unordered windows, or an oversized window fail before HTTP.

After the reviewed implementation is on main, the historical observation can
be requested with:

```bash
gh workflow run audit-alert-relay-telemetry.yml --ref main \
  --field from_utc=2026-11-16T22:52:20Z \
  --field to_utc=2026-11-16T22:54:20Z
```

Use the workflow result and its `alert-relay-telemetry-observation.json`
artifact. Exit code 0 records that numerical evidence was obtained. Exit code 2
records unavailable evidence or a permission block. Neither exit code asserts
message delivery.

## Credential and HTTP scope

The script uses only the existing environment names
`CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID`. Credentials are supplied
to the single provider step in place. They are not command-line arguments,
workflow outputs, report fields, or new stored secrets.

A nonempty token must be 16–512 printable ASCII characters without whitespace.
A configured account identifier must be exactly 32 hexadecimal characters.
When the identifier is absent, one bounded `GET /accounts` is permitted.
Discovery requires one result and pagination metadata proving page 1, count 1,
and total count 1; ambiguous, incomplete, or paginated discovery is unavailable.
The account listing is never written to disk. Cloudflare documents that
pagination metadata in its
[List Accounts API](https://developers.cloudflare.com/api/resources/accounts/methods/list/).

The only target host is `api.cloudflare.com`. Environment proxies and redirects
are disabled. The script permits only these fixed paths:

| Method | Path | Purpose |
|---|---|---|
| GET | `/client/v4/accounts` | Optional account discovery |
| POST | `/client/v4/accounts/{account}/workers/observability/telemetry/keys` | Verify the three fixed field names and types |
| POST | `/client/v4/accounts/{account}/workers/observability/telemetry/query` | Read one temporary aggregate query |

Cloudflare defines these telemetry POST operations as key discovery and query
execution. The query sets `dry: true`, so query results are not persisted.
Both telemetry endpoints currently require `Workers Observability Write`
according to the official
[keys](https://developers.cloudflare.com/api/resources/workers/subresources/observability/subresources/telemetry/methods/keys/)
and
[query](https://developers.cloudflare.com/api/resources/workers/subresources/observability/subresources/telemetry/methods/query/)
API references. A token that can deploy a Worker has not thereby demonstrated
access to those operations.

An HTTP 401 or 403 becomes `PERMISSION_BLOCKED` with the numeric HTTP status
and a fixed stage identifying the refused operation. Account discovery, key
discovery, and aggregate-query refusals remain distinct. The status does not
identify a particular missing permission or prove that a token is valid.
The diagnostic does not add scopes, mint credentials, change settings, deploy,
create saved queries, start tails, read raw trace views, or send a relay message.

Each observation permits at most three HTTP requests, with no automatic retry.
Each response is limited to 256 KiB and each socket operation has a maximum
12-second timeout. A separate 45-second process deadline also bounds a
trickling response. After that deadline, the client stops starting requests,
ignores a late in-memory result, and exits with unavailable evidence. The
deadline does not establish cancellation of a query already received by the
provider.

## Fixed query contract

Key discovery uses the requested interval, the fixed
`$metadata.service == szl-alert-relay` filter, and an anchored key-name filter.
It requires precisely these supported types:

| Field | Type |
|---|---|
| `$metadata.service` | string |
| `$workers.cpuTimeMs` | number |
| `$workers.wallTimeMs` | number |

Missing, additional, duplicate, or mistyped fields stop the diagnostic before
the aggregate request. There is no alternate-field or broader-dataset search.

The aggregate request uses `view: calculations`, `chartType: aggregate`,
`ignoreSeries: true`, and a row limit of 1. Its filters require the fixed
service and the existence of both timing fields. It has no grouping, full-text
search, trace view, invocation view, or user-defined query expression.

| Fixed output alias | Calculation |
|---|---|
| `matching_timing_events` | count of matching timing rows |
| `cpu_avg_ms` | average CPU milliseconds |
| `cpu_max_ms` | maximum CPU milliseconds |
| `wall_avg_ms` | average wall milliseconds |
| `wall_max_ms` | maximum wall milliseconds |
| `wall_p95_ms` | 95th percentile wall milliseconds |

The response must identify a completed query, echo the exact time interval, and
confirm `dry: true`. Every requested alias must appear exactly once with one
ungrouped aggregate. An incomplete run, missing alias, unexpected grouping,
nonfinite number, boolean in a number field, or inconsistent count is unavailable.

For each alias, only `value`, `count`, and `sampleInterval` are retained.
The
[query response schema](https://developers.cloudflare.com/api/resources/workers/subresources/observability/subresources/telemetry/methods/query/)
defines weighted calculations and sample intervals. Its database sampling is a
separate mechanism. The report therefore labels counts
`ESTIMATED_MATCHING_TIMING_EVENTS` even when the reported sample interval is 1.
These counts are not exact invocation counts or delivery counts.

## Report interpretation

| State | Meaning |
|---|---|
| `OBSERVED` | The fixed numerical aggregate contract was satisfied |
| `PERMISSION_BLOCKED` | An actual API request returned HTTP 401 or 403 |
| `UNAVAILABLE` | The diagnostic could not establish the expected observations |

An empty result is `UNAVAILABLE / NO_MATCHING_TIMING_EVENTS`. It may reflect
missing retained events, unavailable fields, an inappropriate interval, or
other evidence limits. It does not prove that a request never ran.

The report stage is one of `INPUT`, `ACCOUNT_DISCOVERY`, `KEY_DISCOVERY`,
`AGGREGATE_QUERY`, or `RESPONSE_ADMISSION`. A process deadline or an unexpected
worker failure may leave the stage `UNKNOWN`. Stage values are fixed constants;
provider and caller text cannot populate them.

The JSON includes fixed schema and service identifiers, these honest states,
validated observation and window timestamps, the last observed numeric HTTP
status, request count when known, and the filtered aggregates. The request count
is unknown when the process deadline wins a race with the worker thread.

Provider error messages, returned URLs, topics, headers, raw events, account
identifiers, and trace payloads are never copied into logs or the artifact.
Malformed input and transport exceptions produce fixed reason codes. The
artifact upload is restricted to the one sanitized report and retained for
seven days.

Wall time that substantially exceeds CPU time can support investigation of
waiting within a Worker request. This correlation alone does not identify a
network fault, origin restriction, firewall decision, or successful downstream
delivery. Those conclusions require separate evidence with an appropriate
authorization and privacy boundary.

## Offline verification

Run the same source boundary tests as CI:

```bash
python -I -B tests/test_cloudflare_alert_relay_telemetry.py -v
```

The suite uses the actual request builder and response parser with local
fixtures. It includes urllib's real redirect handler, a blocked transport
deadline, scope and input limits, permission refusals, malformed and oversized
responses, exact key and alias admission, empty evidence, sample preservation,
and output canaries. Workflow tests protect the manual-main condition, isolated
Python invocation, fixed artifact, and environment-mediated inputs. These tests
do not call Cloudflare or establish that the existing token has telemetry access.
