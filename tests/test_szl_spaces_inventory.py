"""Regression coverage for the audited Hugging Face Spaces inventory.

These tests are deliberately offline: runtime health remains the responsibility of the
honest probe endpoint, while this suite locks identity, SDK host selection, and the
canonical-origin isolation boundary.
"""

import szl_spaces_proxy as proxy
import szl_spaces_surface as surface


EXPECTED = [
    ("a11oy", "a11oy", "a11oy — Command Center", "docker"),
    ("anatomy", "anatomy", "SZL Living Anatomy", "docker"),
    ("cosmos", "cosmos", "SZL Cosmos", "docker"),
    ("david-leads", "david-leads", "David Leads — Sovereign Insurance Intelligence", "docker"),
    ("energy-attest-holo", "energy-attest-holo", "Energy Attestation Holo", "static"),
    ("energy-attested-runs", "energy-attested-runs", "Energy-Attested Inference Runs", "gradio"),
    ("governed-norm-holo", "governed-norm-holo", "Governed Norms — WILLAY classifiers", "static"),
    ("governed-receipt-verifier", "governed-receipt-verifier", "Governed Receipt Verifier", "static"),
    ("guardrail-receipt", "guardrail-receipt", "Guardrail Decision-Receipt", "gradio"),
    ("hatun-mcp", "hatun-mcp", "hatun — MCP Server", "docker"),
    ("holographic", "holographic", "Holographic Estate", "docker"),
    ("immune", "immune", "IMMUNE — Verifiable AI Defense Matrix", "docker"),
    ("killinchu", "killinchu", "killinchu — Andean Drone Intelligence", "docker"),
    ("lambda-gate-holo", "lambda-gate-holo", "Λ Gate — Conjecture 1, never green", "static"),
    ("llm-router-live", "llm-router-live", "SZL LLM Router", "docker"),
    ("README", "readme", "SZL Holdings — Governed-AI Command Platform", "static"),
    ("receipt-chain-live", "receipt-chain-live", "Receipt Chain Live", "static"),
    ("sda", "sda", "SZL SDA", "docker"),
    ("szl-blocked-live", "szl-blocked-live", "szl-blocked-live", "static"),
    ("szl-estate-live", "szl-estate-live", "Khipu Loom — Governed AI Estate", "static"),
    ("szl-forge-lab", "szl-forge-lab", "SZL Forge Lab", "gradio"),
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

    # Hub API identity is case-sensitive even though the local route is lowercase.
    assert surface.hf_api_url("readme") == "https://huggingface.co/api/spaces/SZLHOLDINGS/README"


def test_every_audited_shortcut_hands_off_to_an_isolated_origin():
    expected_slugs = {row[1] for row in EXPECTED}
    assert set(proxy.ALL_SPACES) == expected_slugs
    assert set(proxy.HANDOFF_SPACES) == expected_slugs
    assert len(proxy.HANDOFF_SPACES) == 26
    for name, _slug, _title, _sdk in EXPECTED:
        assert surface.canonical_url(name) == surface.hf_url(name)
        assert surface.proxy_url(name) == surface.hf_url(name)  # compatibility alias
    assert proxy._canonical_target("readme") == "https://szlholdings-readme.static.hf.space"
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

    nested = client.get("/spaces/readme/assets/app.js?v=1&mode=full")
    assert nested.status_code == 307
    assert nested.headers["location"] == (
        "https://szlholdings-readme.static.hf.space/assets/app.js?v=1&mode=full"
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


if __name__ == "__main__":
    test_audited_inventory_is_exact_and_in_lockstep()
    test_sdk_selects_the_canonical_hugging_face_host()
    test_every_audited_shortcut_hands_off_to_an_isolated_origin()
    test_unknown_identifiers_fail_closed()
    test_tiles_and_fallback_render_every_audited_title_without_runtime_claims()
    test_registered_shortcuts_redirect_without_proxying_content()
    test_health_aggregate_and_cache_states_are_explicit()
    print("test_szl_spaces_inventory: 7 focused offline tests passed")
