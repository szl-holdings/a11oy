"""Regression coverage for the audited Hugging Face Spaces inventory.

These tests are deliberately offline: runtime health remains the responsibility of the
honest probe endpoint, while this suite locks identity, SDK host selection, and the
canonical-origin isolation boundary.
"""

from pathlib import Path

import szl_spaces_proxy as proxy
import szl_spaces_surface as surface


EXPECTED = [
    ("a11oy", "a11oy", "a11oy — Command Center", "docker"),
    ("anatomy", "anatomy", "SZL Living Anatomy", "docker"),
    ("cosmos", "cosmos", "SZL Cosmos", "docker"),
    ("david-leads", "david-leads", "David Leads — Sovereign Insurance Intelligence", "docker"),
    ("energy-attest-holo", "energy-attest-holo", "Energy Attestation Holo", "static"),
    ("energy-attested-runs", "energy-attested-runs", "Energy-Attested Inference Runs", "static"),
    ("governed-norm-holo", "governed-norm-holo", "Governed Norms — WILLAY classifiers", "static"),
    ("governed-agent-bench", "governed-agent-bench", "Governed Agent Benchmark", "gradio"),
    ("governed-receipt-verifier", "governed-receipt-verifier", "Governed Receipt Verifier", "static"),
    ("guardrail-receipt", "guardrail-receipt", "Guardrail Decision-Receipt", "static"),
    ("hatun-mcp", "hatun-mcp", "hatun — MCP Server", "docker"),
    ("holographic", "holographic", "Holographic Estate", "docker"),
    ("immune", "immune", "IMMUNE — Verifiable AI Defense Matrix", "docker"),
    ("killinchu", "killinchu", "killinchu — Andean Drone Intelligence", "docker"),
    ("lambda-gate-holo", "lambda-gate-holo", "Λ Gate — Conjecture 1, never green", "static"),
    ("llm-router-live", "llm-router-live", "SZL LLM Router", "docker"),
    ("receipt-chain-live", "receipt-chain-live", "Receipt Chain Live", "static"),
    ("sda", "sda", "SZL SDA", "docker"),
    ("szl-blocked-live", "szl-blocked-live", "szl-blocked-live", "static"),
    ("szl-estate-live", "szl-estate-live", "Khipu Loom — Governed AI Estate", "static"),
    ("szl-forge-lab", "szl-forge-lab", "SZL Forge Lab", "static"),
    ("szl-govsign-live", "szl-govsign-live", "szl-govsign-live", "static"),
    ("szl-kernels-live", "szl-kernels-live", "SZL Kernel Operations Hub", "static"),
    ("szl-model-inference-lab", "szl-model-inference-lab", "SZL Model Inference Lab", "docker"),
    ("szl-provctl-live", "szl-provctl-live", "szl-provctl-live", "static"),
    ("yarqa", "yarqa", "yarqa — Plug-Flow Compartments (live or sample, always honest)", "docker"),
]


def _rows(records):
    return [(sp["name"], sp["slug"], sp["title"], sp["sdk"]) for sp in records]


def test_audited_inventory_is_exact_and_in_lockstep():
    assert len(EXPECTED) == 26
    assert _rows(surface.SPACES) == EXPECTED
    assert _rows(proxy.SPACE_INVENTORY) == EXPECTED
    assert proxy.SPACE_INVENTORY is not surface.SPACES
    assert len({row[0] for row in EXPECTED}) == 26
    assert len({row[1] for row in EXPECTED}) == 26
    assert not {"cathedral", "energy", "khipu-constellation"} & set(proxy.ALL_SPACES)


def test_sdk_selects_the_canonical_hugging_face_host():
    for name, slug, _title, sdk in EXPECTED:
        suffix = ".static.hf.space" if sdk == "static" else ".hf.space"
        expected_url = f"https://szlholdings-{slug}{suffix}"
        assert surface.hf_url(name) == expected_url
        assert surface.hf_url(slug) == expected_url
        assert proxy.hf_url(name) == expected_url
        assert proxy.hf_url(slug) == expected_url

    assert surface.hf_api_url("governed-agent-bench") == (
        "https://huggingface.co/api/spaces/SZLHOLDINGS/governed-agent-bench"
    )


def test_every_audited_shortcut_hands_off_to_an_isolated_origin():
    expected_slugs = {row[1] for row in EXPECTED}
    assert set(proxy.ALL_SPACES) == expected_slugs
    assert set(proxy.HANDOFF_SPACES) == expected_slugs
    assert len(proxy.HANDOFF_SPACES) == 26
    for name, _slug, _title, _sdk in EXPECTED:
        assert surface.canonical_url(name) == surface.hf_url(name)
        assert surface.proxy_url(name) == surface.hf_url(name)  # compatibility alias
    assert proxy._canonical_target("governed-agent-bench") == (
        "https://szlholdings-governed-agent-bench.hf.space"
    )
    assert proxy._canonical_target("immune", "assets/app.js", "v=1&mode=full") == (
        "https://szlholdings-immune.hf.space/assets/app.js?v=1&mode=full"
    )


def test_unknown_identifiers_fail_closed():
    for resolver in (
        surface.hf_url,
        surface.hf_api_url,
        surface.hf_repo_url,
        surface.canonical_url,
        surface.proxy_url,
        proxy.hf_url,
        proxy.hf_repo_url,
    ):
        try:
            resolver("notreal")
        except ValueError as exc:
            assert "unknown Space identifier" in str(exc)
        else:
            raise AssertionError("unknown Space identifier must fail closed")


def test_tiles_and_fallback_render_every_audited_title_without_runtime_claims():
    tiles = surface._tiles_page("a11oy").decode("utf-8")
    fallback = proxy._fallback_index().decode("utf-8")
    for name, slug, title, sdk in EXPECTED:
        assert f'data-space="{slug}"' in tiles
        assert title in tiles
        assert f"{name} &middot; {sdk}" in tiles
        assert title in fallback
        assert name in fallback
    assert "All 26 audited Spaces" in tiles
    assert "All 26 audited Spaces" in fallback
    assert "all RUNNING" not in fallback
    assert "Open canonical app" in fallback
    assert "View repository" in fallback
    assert "reverse proxy" not in fallback.lower()


def test_registered_shortcuts_redirect_without_proxying_content():
    from starlette.applications import Starlette
    from starlette.responses import PlainTextResponse
    from starlette.routing import Route
    from starlette.testclient import TestClient

    app = Starlette(routes=[Route("/{full_path:path}", lambda _: PlainTextResponse("SPA"))])
    proxy.register(app)
    client = TestClient(app, follow_redirects=False)

    root = client.get("/spaces/immune")
    assert root.status_code == 307
    assert root.headers["location"] == "https://szlholdings-immune.hf.space"
    assert root.headers["x-szl-space-handoff"] == "canonical-origin"
    assert root.headers["cache-control"] == "no-store"
    assert root.headers["referrer-policy"] == "no-referrer"

    nested = client.get("/spaces/governed-agent-bench/assets/app.js?v=1&mode=full")
    assert nested.status_code == 307
    assert nested.headers["location"] == (
        "https://szlholdings-governed-agent-bench.hf.space/assets/app.js?v=1&mode=full"
    )
    assert client.get("/spaces/a11oy").status_code == 307
    assert client.get("/spaces/killinchu").status_code == 307
    assert client.get("/spaces/notreal").status_code == 404


def test_health_aggregate_and_cache_states_are_explicit():
    import asyncio
    import time

    running = {"app_reachable": True, "stage": "RUNNING"}
    unknown = {"app_reachable": False, "stage": "unknown"}
    assert surface._aggregate_health_state([running, dict(running)]) == "LIVE"
    assert surface._aggregate_health_state([unknown, dict(unknown)]) == "UNAVAILABLE"
    assert surface._aggregate_health_state([running, unknown]) == "DEGRADED"

    source = {"state": "LIVE", "count": 1, "spaces": [running], "fetchedAt": "test"}
    previous = dict(surface._HEALTH_CACHE)
    surface._HEALTH_CACHE["payload"] = source
    surface._HEALTH_CACHE["ts"] = time.monotonic()
    try:
        cached = asyncio.run(surface.spaces_health())
    finally:
        surface._HEALTH_CACHE.clear()
        surface._HEALTH_CACHE.update(previous)

    assert cached is not source
    assert cached["state"] == "CACHED"
    assert cached["cached_state"] == "LIVE"
    assert source["state"] == "LIVE", "cache labeling must not mutate the stored payload"


def test_anatomy_and_sda_health_use_exact_api_contract_routes():
    anatomy = surface.SPACE_API_CONTRACTS["anatomy"]
    sda = surface.SPACE_API_CONTRACTS["sda"]

    assert [item["url"].rsplit("/", 1)[-1] for item in anatomy] == [
        "manifest", "capabilities", "evidence", "receipt"
    ]
    assert [item["url"] for item in sda] == [
        "https://a-11-oy.com/api/a11oy/v1/compute-pool",
        "https://a-11-oy.com/api/a11oy/v1/verify/receipt",
        "https://szlholdings-killinchu.hf.space/api/killinchu/v1/mosaic/cop",
    ]
    assert all(item["url"] != "https://a-11-oy.com/api/a11oy/v1/verify" for item in sda)

    root_green = {"app_reachable": True, "stage": "RUNNING", "contract_state": "UNAVAILABLE"}
    assert surface._space_health_state(root_green) == "DEGRADED"


def test_sda_vendored_widget_is_locked_to_the_canonical_verifier_contract():
    widget = (Path(__file__).parents[1] / "spaces" / "sda" / "assets" /
              "szl_verify_widget.js").read_text(encoding="utf-8")
    assert widget.startswith(
        "// VENDORED FROM szl-holdings/platform@9798feff9af3d6b0d8737abd70f71a1db1755a65"
    )
    assert "VERIFY_PATH  = '/api/a11oy/v1/verify/receipt'" in widget
    assert "/api/a11oy/v1/verify?url=" not in widget
    assert "p = pull(u, {method:'GET'})" in widget


def test_exact_contract_probe_requires_expected_json_marker():
    import asyncio

    class Response:
        status_code = 200

        def __init__(self, data):
            self._data = data

        def json(self):
            return self._data

    class Client:
        def __init__(self, data):
            self.data = data

        async def get(self, *_args, **_kwargs):
            return Response(self.data)

    contract = surface.SPACE_API_CONTRACTS["sda"][1]
    live = asyncio.run(surface._probe_contract(
        Client({"schema": "szl.public-receipt-verifier/manifest/v1"}), contract
    ))
    stale = asyncio.run(surface._probe_contract(Client({"error": "not found"}), contract))
    assert live["state"] == "LIVE"
    assert stale["state"] == "UNAVAILABLE"


def test_inventory_set_equality_detects_missing_and_unexpected_spaces():
    import asyncio

    class Response:
        status_code = 200

        def __init__(self, names):
            self._names = names

        def json(self):
            return [{"id": "SZLHOLDINGS/" + name} for name in self._names]

    class Client:
        def __init__(self, names):
            self._names = names

        async def get(self, *_args, **_kwargs):
            return Response(self._names)

    canonical = [row[0] for row in EXPECTED]
    exact = asyncio.run(surface._probe_inventory(Client(canonical)))
    exact_with_profile = asyncio.run(
        surface._probe_inventory(Client(canonical + ["README"]))
    )
    drift = asyncio.run(
        surface._probe_inventory(Client(canonical[1:] + ["README", "rogue-space"]))
    )
    assert exact["state"] == "LIVE"
    assert exact["missing"] == exact["unexpected"] == []
    assert exact_with_profile["state"] == "LIVE"
    assert exact_with_profile["observed_count"] == len(canonical)
    assert exact_with_profile["missing"] == exact_with_profile["unexpected"] == []
    assert drift["state"] == "DEGRADED"
    assert drift["missing"] == [canonical[0]]
    assert drift["unexpected"] == ["rogue-space"]


def test_inventory_http_and_schema_failures_are_unavailable():
    import asyncio

    class Response:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload

        def json(self):
            return self._payload

    class Client:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self.payload = payload

        async def get(self, *_args, **_kwargs):
            return Response(self.status_code, self.payload)

    non_200 = asyncio.run(surface._probe_inventory(Client(503, {"error": "busy"})))
    malformed = asyncio.run(surface._probe_inventory(Client(200, {"spaces": []})))
    canonical = [{"id": "SZLHOLDINGS/" + row[0]} for row in EXPECTED]
    malformed_entries = [
        canonical + [None],
        canonical + [{}],
        canonical + [{"id": 7}],
        canonical + [{"id": "OTHER/rogue-space"}],
        canonical + [{"id": "SZLHOLDINGS/"}],
        canonical + [{"id": "SZLHOLDINGS/foo/bar"}],
    ]
    malformed_results = [
        asyncio.run(surface._probe_inventory(Client(200, payload)))
        for payload in malformed_entries
    ]

    assert non_200["state"] == "UNAVAILABLE"
    assert non_200["http_status"] == 503
    assert non_200["error"] == "hub_api_http_status"
    assert malformed["state"] == "UNAVAILABLE"
    assert malformed["http_status"] == 200
    assert malformed["error"] == "hub_api_schema"
    assert "missing" not in non_200 and "missing" not in malformed
    for result in malformed_results:
        assert result["state"] == "UNAVAILABLE"
        assert result["http_status"] == 200
        assert result["error"] == "hub_api_schema"
        assert result["malformed_index"] == len(canonical)
        assert "missing" not in result and "unexpected" not in result


def test_contract_retry_and_circuit_are_bounded_and_fail_closed():
    import asyncio

    contract = {"id": "unit-circuit", "url": "https://invalid.test/health",
                "expected": {"ok": True}}
    original_probe = surface._urllib_probe
    previous = surface._CONTRACT_CIRCUITS.pop(contract["id"], None)

    def timeout(*_args, **_kwargs):
        raise TimeoutError("simulated")

    surface._urllib_probe = timeout
    try:
        first = asyncio.run(surface._probe_contract(None, contract))
        second = asyncio.run(surface._probe_contract(None, contract))
        open_result = asyncio.run(surface._probe_contract(None, contract))
    finally:
        surface._urllib_probe = original_probe
        surface._CONTRACT_CIRCUITS.pop(contract["id"], None)
        if previous is not None:
            surface._CONTRACT_CIRCUITS[contract["id"]] = previous

    assert first["state"] == "UNAVAILABLE" and first["attempts"] == 2
    assert first["circuit_state"] == "CLOSED"
    assert second["state"] == "UNAVAILABLE" and second["circuit_state"] == "OPEN"
    assert open_result["probe_state"] == "CIRCUIT_OPEN"
    assert open_result["attempts"] == 0 and open_result["retry_after_s"] > 0


def test_hf_pending_custom_domain_stays_degraded():
    result = {"slug": "a11oy", "stage": "unknown"}
    surface._apply_hf_runtime(result, {
        "runtime": {
            "stage": "RUNNING",
            "domains": [
                {"domain": "szlholdings-a11oy.hf.space", "stage": "READY"},
                {"domain": "a-11-oy.com", "stage": "PENDING"},
            ],
        }
    })
    assert result["custom_domain"] == {
        "domain": "a-11-oy.com",
        "provider_stage": "PENDING",
        "state": "DEGRADED",
        "source": "hf-api",
    }
    result.update({"app_reachable": True, "contract_state": "LIVE"})
    assert surface._space_health_state(result) == "DEGRADED"


if __name__ == "__main__":
    test_audited_inventory_is_exact_and_in_lockstep()
    test_sdk_selects_the_canonical_hugging_face_host()
    test_every_audited_shortcut_hands_off_to_an_isolated_origin()
    test_unknown_identifiers_fail_closed()
    test_tiles_and_fallback_render_every_audited_title_without_runtime_claims()
    test_registered_shortcuts_redirect_without_proxying_content()
    test_health_aggregate_and_cache_states_are_explicit()
    print("test_szl_spaces_inventory: 7 focused offline tests passed")
