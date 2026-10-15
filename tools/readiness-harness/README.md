# a11oy readiness harness

A read-only observer for the a11oy and killinchu console contracts. It checks
GET/HEAD responses, schemas, source clocks and citations. Required execution
contracts remain in the denominator as `NOT_PROBED`; passive observation cannot
establish an execution outcome. Stale, unsupported or uncited evidence fails its
existing doctrine checks.

## Pieces

| File | What it does |
|------|--------------|
| `gen_tabs_matrix.py` | Reads the console source and generates `tabs.json` — the contract matrix (tab → route → endpoints → schema → freshnessSLA → citationsRequired → degradedRules). Single source of truth. `--check` mode fails on drift. Also emits `stress/stress-targets.json`. |
| `tabs.json` | The generated contract matrix (committed; regenerate, don't hand-edit). |
| `probe_runner.mjs` | Throttled GET/HEAD probe: status, p50/p95 latency, schemas, citations and freshness. Other methods are recorded without requests. Required unprobed, unreachable, throttled or degraded contracts and doctrine failures block release; `--report-only` retains diagnostic evidence. |
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
node probe_runner.mjs --base https://a-11-oy.com --report-only   # diagnostic artifact; cannot admit readiness

# 4. live tab sweep (needs a running console)
A11OY_BASE=https://a-11-oy.com npx playwright test tab_sweeper.spec.ts

# 5. stress (manual; needs k6 installed)
k6 run -e A11OY_BASE=https://a-11-oy.com stress/warhacker.js
k6 run -e A11OY_BASE=https://a-11-oy.com -e PROFILE=soak stress/warhacker.js
```

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

## Required execution coverage

The observer never issues a state-changing request, including when legacy
`--allow-state-changing` or `A11OY_READINESS_MUTATION_AUTHORIZED` settings are
present. Those settings grant no authority. Each such contract retains its
required/optional classification and contributes to `skippedStateChanging`;
required ones also contribute to `requiredNotProbed` and block the release gate.

The compact publisher, canonical relock verifier and served tab-matrix reject
nonzero, malformed or unclassified required coverage gaps. Historical summaries
without `requiredNotProbed` conservatively treat all skipped contracts as
required. Explicit optional skips remain visible without counting as successful
probes. No endpoint requirement or status allowlist is removed.

The existing required execution contracts need a separately governed producer
and source-bound acceptance evidence. This repair does not supply that producer
or qualify a release. Explicit operator execution clients remain separate.

### Isolated POST acceptance rehearsal

`effect_acceptance.py` is a separate, one-shot **SIMULATED** rehearsal for the
five required POST paths. It never calls the public origin or changes the
read-only readiness validator. Supply an **already local** immutable A11oy
image ID whose `org.opencontainers.image.revision` label matches the clean Git
HEAD; the driver does not pull or build images:

```powershell
python tools/readiness-harness/effect_acceptance.py --image sha256:<local-image-id> --out C:\path\outside\repo\effect-acceptance.json
```

Use a fresh output filename for every run; existing reports are never replaced.
The container runs with `--network none`, read-only root, a disposable `/app/data`
tmpfs, no inherited host credentials, and a generated local operator key. Its
NVD CVSS warmer is disabled before importing `serve.py`; other import-time
cache probes may still run inside that disposable, networkless container. The
TestClient does not follow redirects, so a 3xx response cannot cause a second
POST. The driver checks response semantics and before/after in-process decision-feed and
forum counts. It can observe policy decision, cited formula answer,
compliance lookup, and a **MODELED** eval with zero evaluated model responses.
The public forum exposes only a count and a limited event projection: the
increment is local correlation, not an independently verified eval receipt.
The agent-loop route is sent one anonymous request to observe its 401 refusal;
its execution effect remains **UNAVAILABLE**. Missing/mismatched images,
unavailable routes, or ambiguous state readback produce `UNAVAILABLE` rows and
exit code 2. A failed readback before a POST records zero attempts. A failed
readback or response after a POST records an **UNKNOWN** effect and stops later
POSTs. If the Docker invocation has begun but its child report cannot be
validated, occurrence and attempt counts remain **UNKNOWN**. Every invocation
uses a unique name, nonce label, and temporary CID file; the host checks for
that exact container and verifies it is absent after a bounded stop/remove
sequence before accepting the child report. Failed cleanup remains explicit in
the host receipt. The report hashes
requests/responses; it never records the local operator key.

An image revision label is a declared source binding, not independent image
provenance. The report is local simulated evidence only; it is neither live
same-origin effect coverage nor a release/admission verdict. A governed live
producer still needs an approved disposable tenant, effect-specific readback,
exact deployed image proof, and independent review before the required POST
coverage can close.

`tools/verify_board.py` likewise reads only, records execution endpoints and
HTTP 405 as `NOT_PROBED`, and never retries with POST. HTTP 503 is an unavailable
observation and cannot establish a live image.

## Live serving

The matrix is also served by the running console at:

```
GET /api/a11oy/v1/readiness/tab-matrix
```

(see `serve.py`). It returns the matrix and, when independently supplied,
a compact verdict bound to the exact source revision, canonical origin, complete
required coverage and a non-future observation no older than 24 hours. Missing
or rejected verdicts remain `available: false`; matrix availability is separate.
The current canonical workflow validates its run-local verdict and hands that
evidence to relock without writing a Space variable or restarting the runtime.
The full probe stays an immutable GitHub Actions artifact.
