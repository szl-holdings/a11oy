# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Series A holographic models+kernels estate — honest Hub bind, no invented green."""

from __future__ import annotations

from pathlib import Path

import a11oy_model_intel as intel


ROOT = Path(__file__).resolve().parents[1]
CONSOLE = (ROOT / "pages" / "console.html").read_text(encoding="utf-8")
ESTATE_PAGE = (ROOT / "pages" / "estate.html").read_text(encoding="utf-8")
BAR_JS = (ROOT / "static" / "shared" / "szl_command_bar.js").read_text(encoding="utf-8")
BAR_CSS = (ROOT / "static" / "shared" / "szl_command_bar.css").read_text(encoding="utf-8")
SERVE = (ROOT / "serve.py").read_text(encoding="utf-8")
DOCKER = (ROOT / "Dockerfile").read_text(encoding="utf-8")

PINNED_TITLES = (
    "SZL-Khipu-1.5B",
    "Sovereign router",
    "KHIPU-R2",
    "WILLAY",
    "YARQA-ATTN",
    "A11OY-MINI",
    "Chaski",
    "Qantu",
    "Waman",
    "Chakana",
    "Tinku",
)
SHIPPED_KERNELS = ("szl-receipt-attn", "szl-maskmod", "szl-block-kv")


def test_catalog_pins_series_a_ids_and_excludes_killinchu() -> None:
    titles = [card["title"] for card in intel.SERIES_A_CARDS]
    ids = [card["id"] for card in intel.SERIES_A_CARDS]
    hubs = [str(card.get("hub_id") or "") for card in intel.SERIES_A_CARDS]
    for title in PINNED_TITLES:
        assert title in titles
    for kid in SHIPPED_KERNELS:
        assert kid in ids
    blob = " ".join(ids + hubs + titles).lower()
    assert "killinchu" not in blob
    sage = intel.SERIES_A_ROADMAP_KERNELS[0]
    assert sage["id"] == "sage-int8-fp8"
    assert sage["shipped"] is False
    assert sage["cut"] == "ROADMAP"
    yarqa = next(card for card in intel.SERIES_A_CARDS if card["id"] == "yarqa-attn")
    assert yarqa["lane"] == "kernel"
    assert yarqa["owner"] == "KERNEL"
    assert yarqa["not_triton_stack"] is True
    mini = next(card for card in intel.SERIES_A_CARDS if card["id"] == "a11oy-mini")
    assert mini["expect_gguf"] is True


def test_series_a_bind_is_reported_or_unavailable_never_operational(monkeypatch) -> None:
    live = [
        {
            "repository_id": "SZLHOLDINGS/A11OY-MINI",
            "revision": "a" * 40,
            "pipeline_tag": "text-generation",
            "library_name": "llama.cpp",
            "gguf_files": ["a11oy-mini-f16.gguf", "a11oy-mini-q4_k_m.gguf"],
            "has_card": True,
            "has_adapter": False,
            "weight_bearing_from_filenames": True,
            "file_count": 4,
            "last_modified": "2026-08-28T18:53:24.000Z",
        },
        {
            "repository_id": "SZLHOLDINGS/qantu",
            "revision": "b" * 40,
            "pipeline_tag": None,
            "gguf_files": [],
            "has_card": True,
            "has_adapter": False,
            "weight_bearing_from_filenames": False,
            "file_count": 2,
        },
        {
            "repository_id": "SZLHOLDINGS/szl-receipt-attn",
            "revision": "c" * 40,
            "library_name": "kernels",
            "gguf_files": [],
            "has_card": True,
            "has_adapter": False,
            "weight_bearing_from_filenames": False,
            "file_count": 6,
        },
    ]

    def fake_fetch(key, url, ttl, parser=None, params=None):
        if "spaces" in str(url) or "llm-router-live" in str(url):
            return {
                "value": {
                    "repository_id": "SZLHOLDINGS/llm-router-live",
                    "revision": "d" * 40,
                    "sdk": "docker",
                    "has_card": True,
                    "gguf_files": [],
                    "weight_bearing_from_filenames": False,
                    "file_count": 0,
                },
                "freshness": {"status": "live", "age_s": 0.0},
            }
        return {"value": live, "freshness": {"status": "live", "age_s": 0.0}}

    monkeypatch.setattr(intel, "_cached_fetch", fake_fetch)
    payload = intel.get_series_a_estate()
    assert payload["operational"] is False
    assert payload["killinchu_excluded"] is True
    assert payload["yarqa_attn_is_kernel_owned_not_triton_stack"] is True
    assert payload["locked_formula_count_source"] == "/api/a11oy/v1/honest"
    assert set(payload["shipped_kernels"]) == set(SHIPPED_KERNELS)
    assert payload["roadmap_kernels"][0]["cut"] == "ROADMAP"
    assert payload["lambda"]["theorem"] is False
    mini = next(card for card in payload["cards"] if card["id"] == "a11oy-mini")
    assert mini["operational"] is False
    assert mini["listing"]["label"] == "REPORTED"
    assert "a11oy-mini-f16.gguf" in mini["artifacts"]["gguf_files"]
    assert mini["evals"]["label"] == "ROADMAP"
    assert "none" in mini["evals"]["note"].lower()
    qantu = next(card for card in payload["cards"] if card["id"] == "qantu")
    assert qantu["artifacts"]["label"] == "ROADMAP"
    router = next(card for card in payload["cards"] if card["id"] == "sovereign-router")
    assert router["listing"]["label"] == "REPORTED"
    assert router["hub_kind"] == "space"
    yarqa = next(card for card in payload["cards"] if card["id"] == "yarqa-attn")
    assert yarqa["lane"] == "kernel"
    assert yarqa["not_triton_stack"] is True
    assert yarqa["github"].endswith("/YARQA-ATTN")
    for card in payload["cards"]:
        assert card["operational"] is False
        assert card["lambda"]["theorem"] is False
        assert card["listing"]["label"] in {"REPORTED", "UNAVAILABLE", "ROADMAP"}
        assert "OPERATIONAL" not in (card["listing"]["note"] + card["artifacts"]["note"])


def test_series_a_fetch_fail_is_unavailable_not_invented(monkeypatch) -> None:
    monkeypatch.setattr(
        intel,
        "_cached_fetch",
        lambda *args, **kwargs: {
            "value": None,
            "freshness": {"status": "unavailable", "error": "Timeout"},
        },
    )
    payload = intel.get_series_a_estate()
    assert payload["state"] == "UNAVAILABLE"
    mini = next(card for card in payload["cards"] if card["id"] == "a11oy-mini")
    assert mini["listing"]["label"] == "UNAVAILABLE"
    assert mini["operational"] is False


def test_surfaces_wire_shared_bar_and_dedicated_page() -> None:
    assert 'id="szl-series-a-cards"' in CONSOLE
    assert "V.estate=" in CONSOLE
    assert '["estate"' in CONSOLE
    assert "Models + Kernels" in CONSOLE
    assert "SZLEstate.mount" in CONSOLE
    assert "pages/estate.html" in SERVE
    assert '"/estate"' in SERVE
    # /models remains the 1392 ecosystem atlas deep-link; this PR does not steal it.
    assert "for _estate_path in (\"/estate\", \"/models\")" not in SERVE
    assert "SZLEstate" in BAR_JS
    assert "/api/a11oy/v1/models/series-a" in BAR_JS
    assert "--void:#080c14" in BAR_CSS
    assert ".szl-holo-card" in BAR_CSS
    assert "bp3-" not in BAR_CSS
    assert "palantir" not in BAR_CSS.lower()
    assert "nvidia" not in ESTATE_PAGE.lower()
    assert "blueprint" not in ESTATE_PAGE.lower()
    assert "killinchu" not in ESTATE_PAGE.lower()
    assert "locked_formula_count===8" in ESTATE_PAGE
    assert "Conjecture 1" in ESTATE_PAGE
    assert "live runtime" in ESTATE_PAGE
    assert "pages/estate.html" not in DOCKER


def test_estate_routes_serve_html_not_spa_stub() -> None:
    import pytest
    from starlette.testclient import TestClient

    pytest.importorskip("starlette.testclient")
    import serve

    client = TestClient(serve.app, follow_redirects=False)
    response = client.get("/estate")
    assert response.status_code == 200
    ctype = response.headers.get("content-type") or ""
    assert "text/html" in ctype
    body = response.text
    assert "szl-estate-full" in body
    assert "Conjecture 1" in body
    assert "<!DOCTYPE html>" in body
    assert "caught_by" not in body
    head = client.head("/estate")
    assert head.status_code == 200


def test_no_copied_foreign_chrome_tokens() -> None:
    joined = BAR_CSS + BAR_JS + ESTATE_PAGE
    assert " Palantir " not in joined
    assert "cursor-glass" not in joined.lower()
    assert "huggingface.co/nvidia" not in joined.lower()
    assert "logo-nvidia" not in joined.lower()
    assert "bp3-navbar" not in joined
    assert "bp3-" not in joined
