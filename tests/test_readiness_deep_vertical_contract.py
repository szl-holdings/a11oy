from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "tools" / "readiness-harness" / "gen_tabs_matrix.py"
PROBE = ROOT / "tools" / "readiness-harness" / "probe_runner.mjs"
TABS = ROOT / "tools" / "readiness-harness" / "tabs.json"

SPEC = importlib.util.spec_from_file_location("gen_tabs_matrix", GENERATOR)
assert SPEC and SPEC.loader
matrix_generator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(matrix_generator)


REAL_ESTATE_ROUTES = {
    "/api/a11oy/v1/deva/re/pulse",
    "/api/a11oy/v1/deva/re/distress?limit=1",
    "/api/a11oy/v1/deva/re/ownership",
    "/api/a11oy/v1/deva/re/deal?violations=0&class_c=0",
    "/api/a11oy/v1/deva/re/brokeredge",
}
LEGAL_ROUTES = {
    "/api/a11oy/v1/devb/legal/matter?limit=1",
    "/api/a11oy/v1/devb/legal/matter?term=defense&limit=1",
    "/api/a11oy/v1/devb/legal/matter?term=insurance&limit=1",
    "/api/a11oy/v1/devb/legal/regulatory?limit=1",
    "/api/a11oy/v1/devb/legal/exposure?limit=1",
}
VERTICAL_FEED_ROUTES = {
    "/api/a11oy/v1/vert/defense/feed",
    "/api/a11oy/v1/vert/finance/feed",
    "/api/a11oy/v1/vert/legal/feed",
    "/api/a11oy/v1/vert/cyber/feed",
    "/api/a11oy/v1/vert/realestate/feed",
}


def _node_binary() -> str:
    node = shutil.which("node")
    if node:
        return node
    runtime_nodes = (
        Path(sys.executable).resolve().parent.parent / "node" / "bin" / "node.exe",
        Path.home() / ".cache" / "codex-runtimes" / "codex-primary-runtime"
        / "dependencies" / "node" / "bin" / "node.exe",
    )
    for runtime_node in runtime_nodes:
        if runtime_node.is_file():
            return str(runtime_node)
    pytest.skip("Node.js is required for readiness-runner contract tests")


def _node_eval(source: str) -> subprocess.CompletedProcess[str]:
    node = _node_binary()
    module_url = PROBE.resolve().as_uri()
    program = (
        'import assert from "node:assert/strict";\n'
        f'import * as probe from {json.dumps(module_url)};\n'
        + source
    )
    return subprocess.run(
        [node, "--input-type=module", "--eval", program],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )


def test_real_estate_and_legal_tabs_use_deep_operational_routes() -> None:
    matrix = matrix_generator.build()
    tabs = {tab["key"]: tab for tab in matrix["tabs"]}

    expected = {
        "vrealestate": {
            "/api/a11oy/v1/vert/realestate/feed",
            "/api/a11oy/v1/deva/re/pulse",
            "/api/a11oy/v1/deva/re/distress?limit=1",
            "/api/a11oy/v1/deva/re/ownership",
        },
        "rem": {
            "/api/a11oy/v1/vert/realestate/feed",
            "/api/a11oy/v1/deva/re/pulse",
        },
        "red": {"/api/a11oy/v1/deva/re/distress?limit=1"},
        "reo": {"/api/a11oy/v1/deva/re/ownership"},
        "redeal": {
            "/api/a11oy/v1/vert/realestate/feed",
            "/api/a11oy/v1/deva/re/deal?violations=0&class_c=0",
        },
        "rebe": {
            "/api/a11oy/v1/vert/realestate/feed",
            "/api/a11oy/v1/deva/re/brokeredge",
        },
        "vlegal": {
            "/api/a11oy/v1/vert/legal/feed",
            "/api/a11oy/v1/devb/legal/matter?limit=1",
            "/api/a11oy/v1/devb/legal/regulatory?limit=1",
            "/api/a11oy/v1/devb/legal/exposure?limit=1",
        },
        "legMatter": {
            "/api/a11oy/v1/vert/legal/feed",
            "/api/a11oy/v1/devb/legal/matter?limit=1",
        },
        "legDefense": {
            "/api/a11oy/v1/vert/legal/feed",
            "/api/a11oy/v1/devb/legal/matter?term=defense&limit=1"
        },
        "legReg": {
            "/api/a11oy/v1/vert/legal/feed",
            "/api/a11oy/v1/devb/legal/regulatory?limit=1",
        },
        "legInsure": {
            "/api/a11oy/v1/vert/legal/feed",
            "/api/a11oy/v1/devb/legal/matter?term=insurance&limit=1"
        },
        "legExposure": {"/api/a11oy/v1/devb/legal/exposure?limit=1"},
        "vcyber": {
            "/api/a11oy/v1/vert/cyber/feed",
            "/api/a11oy/v1/sec/threats",
            "/api/a11oy/v1/sec/threatgraph",
        },
        "vdefense": {
            "/api/a11oy/v1/vert/defense/feed",
            "/api/a11oy/v1/mesh/state",
        },
        "vfinance": {
            "/api/a11oy/v1/vert/finance/feed",
        },
    }
    for key, routes in expected.items():
        assert set(tabs[key]["endpoints"]) == routes
        assert all(not route.endswith("/healthz") for route in routes)


def test_deep_routes_have_non_generic_schema_and_supported_citations() -> None:
    matrix = matrix_generator.build()
    endpoints = matrix["endpoints"]
    schemas = matrix["schemas"]

    operational_routes = REAL_ESTATE_ROUTES | LEGAL_ROUTES | VERTICAL_FEED_ROUTES
    assert operational_routes <= endpoints.keys()
    for route in operational_routes:
        schema_name = endpoints[route]["schema"]
        assert schema_name not in {None, "generic_obj", "generic_list"}
        schema = schemas[schema_name]
        assert schema["type"] == "object"
        assert schema.get("required")
        assert schema.get("requiredPathTypes")

    for route in LEGAL_ROUTES:
        assert endpoints[route]["citationsRequired"] is True
    for route in VERTICAL_FEED_ROUTES:
        assert endpoints[route]["citationsRequired"] is True
    for route in REAL_ESTATE_ROUTES:
        assert endpoints[route]["citationsRequired"] is False

    # Health responses are capability descriptors, not timestamped source data.
    assert endpoints["/api/a11oy/v1/deva/healthz"]["freshnessSLA"] is None
    assert endpoints["/api/a11oy/v1/devb/healthz"]["freshnessSLA"] is None


def test_generated_matrix_contains_the_curated_deep_contracts() -> None:
    generated = matrix_generator.build()
    checked_in = json.loads(TABS.read_text(encoding="utf-8"))

    assert checked_in["endpoints"] == generated["endpoints"]
    assert checked_in["schemas"] == generated["schemas"]
    generated_tabs = {tab["key"]: tab["endpoints"] for tab in generated["tabs"]}
    checked_in_tabs = {tab["key"]: tab["endpoints"] for tab in checked_in["tabs"]}
    assert checked_in_tabs == generated_tabs


def test_router_stats_gate_still_requires_live_or_cached_evidence() -> None:
    matrix = matrix_generator.build()
    contract = matrix["endpoints"]["/api/a11oy/v1/router/stats"]
    schema = matrix["schemas"]["router_stats"]

    # The implementation must supply real counters. MODELED is intentionally not
    # admitted here; adding it would hide a return to synthetic display traffic.
    assert contract["degradedRules"]["allowLabels"] == ["live", "cached"]
    assert "MODELED" not in contract["degradedRules"]["allowLabels"]
    assert contract["freshnessSLA"] is None
    assert "routing-decision counters" in contract["note"]
    assert "not QPS" in contract["note"]
    assert schema["properties"]["state"] == {"const": "LIVE"}
    assert schema["properties"]["throughput_state"] == {"const": "OBSERVED"}
    assert schema["properties"]["counter_scope"] == {"const": "process_lifetime"}
    assert schema["properties"]["source"] == {
        "const": "szl_llm_registry.router_stats_snapshot"
    }
    assert schema["requiredPathTypes"]["routes"] == "nonempty_array"
    assert schema["requiredPathTypes"]["servedThisWindow"] == "nonnegative_integer"


def test_freshness_sla_fails_closed_for_missing_stale_and_future_clocks() -> None:
    matrix = matrix_generator.build()
    sla_paths = [
        path
        for path, contract in matrix["endpoints"].items()
        if contract["freshnessSLA"] is not None
    ]
    result = _node_eval(
        f"""
const now = Date.parse("2026-08-11T12:00:00Z");
const spec = {{ freshnessSLA: 3600 }};
const fresh = probe.evaluateFreshness(
  "/ordinary", spec, {{ nested: {{ fetched_at: "2026-08-11T11:59:30Z" }} }}, now,
);
assert.equal(fresh.freshOk, true);

for (const path of {json.dumps(sla_paths)}) {{
  const missing = probe.evaluateFreshness(path, {{ freshnessSLA: 60 }}, {{}}, now);
  assert.equal(missing.checked, true, path);
  assert.equal(missing.freshOk, false, path);
  assert.equal(missing.freshnessMissing, true, path);
}}

const textBody = probe.evaluateFreshness("/ordinary", spec, "ok", now);
assert.equal(textBody.freshOk, false);
assert.equal(textBody.freshnessMissing, true);

const stale = probe.evaluateFreshness(
  "/ordinary", spec, {{ fetched_at: "2026-08-11T10:59:59Z" }}, now,
);
assert.equal(stale.freshOk, false);
assert.equal(stale.ageSec, 3601);

const future = probe.evaluateFreshness(
  "/ordinary", spec, {{ fetched_at: "2026-08-11T12:05:01Z" }}, now,
);
assert.equal(future.freshOk, false);
assert.match(future.freshnessReason, /future clock skew/);

const nestedFuture = probe.evaluateFreshness("/ordinary", spec, {{
  first: {{ freshness: {{ fetched_at: "2026-08-11T11:59:30Z" }} }},
  second: {{ freshness: {{ fetched_at: "2026-08-11T12:05:01Z" }} }},
}}, now);
assert.equal(nestedFuture.freshOk, false);
assert.match(nestedFuture.freshnessReason, /future clock skew/);

const nestedStale = probe.evaluateFreshness("/ordinary", spec, {{
  first: {{ freshness: {{ fetched_at: "2026-08-11T11:59:30Z" }} }},
  second: {{ freshness: {{ fetched_at: "2026-08-11T10:59:59Z" }} }},
}}, now);
assert.equal(nestedStale.freshOk, false);
assert.equal(nestedStale.ageSec, 3601);

const aggregateSpec = {{ schema: "deva_re_pulse", freshnessSLA: 3600 }};
const aggregate = {{
  hpd: {{ freshness: {{ fetched_at: "2026-08-11T11:59:30Z" }} }},
  dob: {{ freshness: {{ fetched_at: "2026-08-11T11:59:20Z" }} }},
  rates: {{ freshness: {{ fetched_at: "2026-08-11T11:59:10Z" }} }},
}};
const aggregateFresh = probe.evaluateFreshness("/aggregate", aggregateSpec, aggregate, now);
assert.equal(aggregateFresh.freshOk, true);
assert.equal(aggregateFresh.ageSec, 50);

aggregate.rates.freshness.fetched_at = "2026-08-11T10:59:59Z";
const aggregateStale = probe.evaluateFreshness("/aggregate", aggregateSpec, aggregate, now);
assert.equal(aggregateStale.freshOk, false);
assert.equal(aggregateStale.ageSec, 3601);

aggregate.rates.freshness.fetched_at = "2026-08-11T12:05:01Z";
const aggregateFuture = probe.evaluateFreshness("/aggregate", aggregateSpec, aggregate, now);
assert.equal(aggregateFuture.freshOk, false);
assert.match(aggregateFuture.freshnessReason, /future clock skew/);

delete aggregate.rates.freshness.fetched_at;
const aggregateMissing = probe.evaluateFreshness("/aggregate", aggregateSpec, aggregate, now);
assert.equal(aggregateMissing.freshOk, false);
assert.equal(aggregateMissing.freshnessMissing, true);
assert.match(aggregateMissing.freshnessReason, /rates\.freshness\.fetched_at/);

const allowedSkew = probe.evaluateFreshness(
  "/ordinary", spec, {{ fetched_at: "2026-08-11T12:05:00Z" }}, now,
);
assert.equal(allowedSkew.freshOk, true);

const evalNotLive = probe.evaluateFreshness(
  "/api/a11oy/v1/eval-arena/history", spec,
  {{ latest_run_at: "2026-08-11T11:59:30Z", freshness: {{ status: "cached" }} }}, now,
);
assert.equal(evalNotLive.freshOk, false);
assert.match(evalNotLive.freshnessReason, /declares freshness cached/);
"""
    )
    assert result.returncode == 0, result.stderr


def test_strict_deep_schema_rejects_missing_source_evidence() -> None:
    result = _node_eval(
        """
const pulse = {
  tab: "pulse",
  hpd: { value: { items: [] }, freshness: { status: "live", fetched_at: "2026-08-11T12:00:00Z" } },
  dob: { value: { items: [] }, freshness: { status: "live", fetched_at: "2026-08-11T12:00:00Z" } },
  rates: { value: { items: [] }, freshness: { status: "live", fetched_at: "2026-08-11T12:00:00Z" } },
  doctrine: {},
};
assert.equal(probe.validateSchema("deva_re_pulse", pulse).ok, true);
delete pulse.rates.freshness.fetched_at;
assert.equal(probe.validateSchema("deva_re_pulse", pulse).ok, false);

const matter = {
  surface: "matter",
  term: "insurance",
  opinions: {
    value: { items: [{ url: "https://www.courtlistener.com/opinion/1/" }] },
    freshness: { status: "live", fetched_at: "2026-08-11T12:00:00Z" },
  },
  doctrine: {},
};
assert.equal(probe.validateSchema("devb_legal_matter", matter).ok, true);
matter.surface = "health";
assert.equal(probe.validateSchema("devb_legal_matter", matter).ok, false);

const observed = {
  value: { items: [] }, freshness: { status: "live", fetched_at: 1786449600 },
};
const finance = {
  vertical: "finance",
  equities_official: { SPY: structuredClone(observed) },
  equities: { SPY: structuredClone(observed) },
  equities_note: "official plus fallback",
  crypto: { "BTC-USD": structuredClone(observed) },
  fx: structuredClone(observed),
  fintech_cve: structuredClone(observed),
  sources_cited: [{ url: "https://example.test/source" }],
  doctrine: {},
};
assert.equal(probe.validateSchema("vert_finance_feed", finance).ok, true);
delete finance.fx.freshness.fetched_at;
assert.equal(probe.validateSchema("vert_finance_feed", finance).ok, false);
"""
    )
    assert result.returncode == 0, result.stderr


def test_required_http_200_stale_unavailable_and_modeled_labels_fail() -> None:
    result = _node_eval(
        """
const spec = {
  required: true,
  degradedRules: {
    allowStatuses: [200],
    allowLabels: ["live", "cached"],
    liesIf: ["mock", "fabricated", "placeholder"],
  },
};
for (const status of ["STALE", "UNAVAILABLE", "MODELED"]) {
  const verdict = probe.evaluateEndpointLabels(
    200, spec, { freshness: { status, fetched_at: "2026-08-11T12:00:00Z" } },
  );
  assert.equal(verdict.checked, true, status);
  assert.equal(verdict.ok, false, status);
  assert.equal(verdict.disallowed.length, 1, status);
}

// A case/incident status is domain data, not endpoint freshness evidence.
const unrelated = probe.evaluateEndpointLabels(200, spec, {
  freshness: { status: "live", fetched_at: "2026-08-11T12:00:00Z" },
  items: [{ status: "UNAVAILABLE" }],
});
assert.equal(unrelated.ok, true);
assert.deepEqual(unrelated.labels.map((entry) => entry.path), ["freshness.status"]);

const modeledAllowed = probe.evaluateEndpointLabels(200, {
  required: true,
  degradedRules: {
    allowStatuses: [200], allowLabels: ["MODELED"], liesIf: [],
  },
}, { freshness: { status: "MODELED" } });
assert.equal(modeledAllowed.ok, true);
"""
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("value", ["0", "NaN", "-1", "1.5"])
def test_probe_cli_rejects_invalid_concurrency_before_network(value: str) -> None:
    node = _node_binary()
    result = subprocess.run(
        [node, str(PROBE), "--concurrency", value],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode != 0
    assert "--concurrency" in (result.stdout + result.stderr)
    assert "[probe] base=" not in result.stderr


def test_all_unreachable_required_endpoints_block_release_runner() -> None:
    result = _node_eval(
        """
const results = Array.from({ length: 5 }, () => ({
  required: true, unreachable: true, lie: false, skipped: false,
}));
const gate = probe.summarizeReleaseGate(results, 5);
assert.equal(gate.complete, true);
assert.equal(gate.requiredUnreachable, 5);
assert.equal(gate.blocked, true);
assert.equal(probe.releaseExitCode(gate, false), 1);
assert.equal(probe.releaseExitCode(gate, true), 0);

const incomplete = probe.summarizeReleaseGate([], 5);
assert.equal(incomplete.complete, false);
assert.equal(incomplete.blocked, true);
"""
    )
    assert result.returncode == 0, result.stderr


def test_all_throttled_required_endpoints_block_release_runner() -> None:
    result = _node_eval(
        """
const results = Array.from({ length: 5 }, () => ({
  required: true, throttled: true, unreachable: false, lie: false, skipped: false,
}));
const gate = probe.summarizeReleaseGate(results, 5);
assert.equal(gate.complete, true);
assert.equal(gate.requiredThrottled, 5);
assert.equal(gate.blocked, true);
assert.equal(probe.releaseExitCode(gate, false), 1);
assert.equal(probe.releaseExitCode(gate, true), 0);
"""
    )
    assert result.returncode == 0, result.stderr
