# a11oy readiness harness

An automated harness that checks the a11oy (and killinchu) console contracts:
read-only endpoints, contracted schemas, freshness within the declared SLA, and
citations. Required contracts without probe evidence block readiness. Doctrine
v11: a response that is stale, mocked, or uncited is a **lie** and fails the build.

## Pieces

| File | What it does |
|------|--------------|
| `gen_tabs_matrix.py` | Reads the console source and generates `tabs.json` — the contract matrix (tab → route → endpoints → schema → freshnessSLA → citationsRequired → degradedRules). Single source of truth. `--check` mode fails on drift. Also emits `stress/stress-targets.json`. |
| `tabs.json` | The generated contract matrix (committed; regenerate, don't hand-edit). |
| `probe_runner.mjs` | Throttled GET/HEAD probe: status, p50/p95 latency, schema validity, citations, freshness → a per-endpoint verdict in `readiness-verdict.json`. Required unprobed contracts, lies, outages, throttling, or blocking degradation fail release mode. `--report-only` (legacy `--soft`) retains evidence without making it publishable. |
| `link_check.mjs` | Typo gate (catches a dropped trailing **s** on the GitHub/HF org names, a truncated `.net` on the domain, and a missing **b** in `github`) plus optional external link reachability (`--reach`). |
| `tab_sweeper.spec.ts` + `playwright.config.ts` | Playwright sweep that opens every tab in the live console and asserts it renders honestly (no unlabelled placeholder, citations present when required). |
| `stress/warhacker.js` | k6 stress/soak suite over the GET contract endpoints with a `lies` counter threshold of zero. |

## Run it

```bash
# 1. (re)generate the contract matrix from the console, or check for drift
python3 gen_tabs_matrix.py            # write tabs.json + stress targets
python3 gen_tabs_matrix.py --check    # CI drift gate (exit 1 if stale)

# 2. typo / link gate
node link_check.mjs                    # typo gate (fast, offline)
node link_check.mjs --reach            # + external link reachability

# 3. throttled API probe -> readiness-verdict.json + "Lies?" verdict
node probe_runner.mjs --base https://a-11-oy.com
node probe_runner.mjs --base https://a-11-oy.com --soft   # report, never fail

# 4. live tab sweep (needs a running console)
A11OY_BASE=https://a-11-oy.com npx playwright test tab_sweeper.spec.ts

# 5. stress (manual; needs k6 installed)
k6 run -e A11OY_BASE=https://a-11-oy.com stress/warhacker.js
k6 run -e A11OY_BASE=https://a-11-oy.com -e PROFILE=soak stress/warhacker.js
```

## Read-only boundary and coverage

The observer sends only GET and HEAD. The legacy `--allow-state-changing` flag
and `A11OY_READINESS_MUTATION_AUTHORIZED=1` never enable POST or any other method.
Retries and timing samples apply only to read requests. State-changing contracts
remain in the endpoint denominator as `skipped: true`, `runtimeState: NOT_PROBED`,
with no HTTP status, validation result, or latency. Skipping is neither a lie nor
an outage, and it is never counted as a successful probe.

`summary.requiredNotProbed` counts skipped required contracts separately from
`summary.skippedStateChanging`, which includes optional skips. Required skips
block strict execution, compact publication, runtime verdict ingestion, and
canonical relock. An older verdict without the new count treats every skip as
required; explicit optional skips remain visible without blocking required
coverage. Endpoint requirements and the matrix are unchanged.

The current matrix includes five required POST contracts: `policy/decide`,
`operator/ask`, `eval/run`, `agentloop/run`, and `policy/compliance`. Their effect
acceptance is **BLOCKED** in this observer. A separate governed acceptance path
and source-bound evidence integration are needed before full readiness can
qualify; this change does not create that authorization or evidence.

## "Lies?" verdict rules (probe)

An endpoint is flagged a **lie** when, against its `tabs.json` contract:

- the HTTP status is not in `degradedRules.allowStatuses`, **or**
- the body fails its declared schema, **or**
- `citationsRequired` is true but no citation/source/dataset-version field is present, **or**
- a timestamp in the body is older than `freshnessSLA`, **or**
- an explicit label field (`data_kind`, `status`, `mode`, …) admits a value in `degradedRules.liesIf` (e.g. `mock`, `fabricated`, `placeholder`).

What is **not** a lie (to keep the gate honest):

- a persistent `429` — that is our own rate-limiting; it is marked `throttled` and treated as inconclusive,
- honesty prose anywhere in the body (e.g. "never fabricated") — only explicit **label fields** are inspected, never raw substrings,
- an honest `SAMPLE` / `CACHED` / `DEGRADED` chip — those are truthful labels.

A canonical `UNAVAILABLE` envelope is truthful negative evidence, not a doctrine
lie. When a schema-required source exposes that envelope, the probe records
`runtimeState: DEGRADED` and its `unavailableSources` instead of counting the
endpoint as clean. A required degraded endpoint blocks release and the compact
verdict publisher; the server and canonical verifier also reject a degraded
summary. Recovery requires an observed source response, not a disabled probe.

An explicitly admitted `DEGRADED` or `UNAVAILABLE` scalar label at the response
root also records endpoint-level negative evidence as `unavailableSources: ["$"]`.
This includes root availability keys (`status`, `state`, `label`, `mode`, scalar
`freshness`) and explicit evidence-kind keys. A fresh, cited HTTP 200 from an
unbuilt RAG index therefore stays `DEGRADED` and blocks a required release probe.
This does not expand any allowed labels: unknown or non-admitted negative labels
still fail, and schema, citation, HTTP-status, and freshness checks remain
independent. Nested optional-source and domain labels do not declare root
availability; the existing schema-required unavailable-source map is unchanged.

## Live serving

The matrix is also served by the running console at:

```
GET /api/a11oy/v1/readiness/tab-matrix
```

(see `serve.py`). It returns `tabs.json` plus an accepted compact verdict when
one is available through its configured evidence sources. The server independently
requires the exact source revision, canonical origin, complete outcomes, and a non-future
observation no older than 24 hours. Missing or rejected evidence remains
`available: false`; the full probe stays an immutable GitHub Actions artifact.

`hf-sync.yml` currently validates the post-deploy verdict and hands it to relock
without writing a Space variable. Persistent runtime ingestion remains a
separate gap: a Space variable update restarts the canonical runtime and is not
part of the read-only observer.
