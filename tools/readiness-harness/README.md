# a11oy readiness harness

An automated harness that proves **every tab in the a11oy (and killinchu) console
is real** — backed by a live endpoint, returning the contracted schema, fresh
within its SLA, and citing its sources. Doctrine v11: *no mock theater*. A tab
that is stale, mocked, or uncited is a **lie** and fails the build.

## Pieces

| File | What it does |
|------|--------------|
| `gen_tabs_matrix.py` | Reads the console source and generates `tabs.json` — the contract matrix (tab → route → endpoints → schema → freshnessSLA → citationsRequired → degradedRules). Single source of truth. `--check` mode fails on drift. Also emits `stress/stress-targets.json`. |
| `tabs.json` | The generated contract matrix (committed; regenerate, don't hand-edit). |
| `probe_runner.mjs` | Throttled API probe. For every endpoint: status, p50/p95 latency, schema validity, citations, freshness → a per-endpoint **"Lies?"** verdict in `readiness-verdict.json`. Exit ≠ 0 on any lie (unless `--soft`). |
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
node probe_runner.mjs --base https://a11oy.net
node probe_runner.mjs --base https://a11oy.net --soft   # report, never fail

# 4. live tab sweep (needs a running console)
A11OY_BASE=https://a11oy.net npx playwright test tab_sweeper.spec.ts

# 5. stress (manual; needs k6 installed)
k6 run -e A11OY_BASE=https://a11oy.net stress/warhacker.js
k6 run -e A11OY_BASE=https://a11oy.net -e PROFILE=soak stress/warhacker.js
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

## Live serving

The matrix is also served by the running console at:

```
GET /api/a11oy/v1/readiness/tab-matrix
```

(see `szl_readiness.py::register`). It returns `tabs.json` plus the latest probe
verdict when `readiness-verdict.json` is present on disk, and says so honestly
when it is not (`available: false`) rather than faking a pass.

> **Note:** serving the matrix live requires a rebuild/redeploy of the Space
> image. The harness files and the GitHub workflow ship independently of that.
