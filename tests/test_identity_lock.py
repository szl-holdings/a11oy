# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
"""Identity-lock contracts: product canonicals, forbidden third-party host, HEAD.

The unhyphenated furniture-shop host must never appear as canonical / og:url /
twitter:url / sameAs / JSON-LD url. Trust Center on this app is a product route
(https://a-11-oy.com/trust). HEAD and GET must agree on HTML document routes.

Hugging Face runtime.domains may report a-11-oy.com PENDING while Cloudflare
still serves the apex. That is KALLPA/Stephen DNS. HTML canonicals stay on
the public product origin; they are not rewritten to *.hf.space.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# Third-party furniture shop. Built at runtime so this file can name the
# prohibition without a literal href= canonical stamp.
_FURNITURE_HOST = "a11oy" + ".com"
_FORBIDDEN_ATTR = re.compile(
    r"""
    (?:
        rel\s*=\s*["']canonical["'][^>]*href\s*=\s*["']https?://(?:www\.)?a11oy\.com
        | href\s*=\s*["']https?://(?:www\.)?a11oy\.com[^"']*["'][^>]*rel\s*=\s*["']canonical["']
        | property\s*=\s*["']og:url["'][^>]*content\s*=\s*["']https?://(?:www\.)?a11oy\.com
        | name\s*=\s*["']twitter:url["'][^>]*content\s*=\s*["']https?://(?:www\.)?a11oy\.com
        | ["']sameAs["']\s*:\s*\[?[^\]]*"https?://(?:www\.)?a11oy\.com
        | ["']url["']\s*:\s*["']https?://(?:www\.)?a11oy\.com
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)
_SKIP_PARTS = {
    ".git",
    "node_modules",
    "dist",
    "vendor",
    "__pycache__",
    ".venv",
    "live_snapshots",
}
_SCAN_SUFFIXES = {".html", ".htm", ".json", ".xml", ".xhtml"}
_HTML_DOCUMENT_PATHS = ("/", "/console", "/trust", "/assurance", "/robots.txt", "/sitemap.xml")


def _should_scan(path: Path) -> bool:
    if path.suffix.lower() not in _SCAN_SUFFIXES:
        return False
    return not any(part in _SKIP_PARTS for part in path.parts)


def test_no_file_emits_furniture_host_as_canonical_og_or_sameas():
    hits = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or not _should_scan(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if _FORBIDDEN_ATTR.search(text):
            hits.append(path.relative_to(ROOT).as_posix())
    assert hits == [], (
        "these files stamp the third-party furniture host as canonical/og/sameAs: "
        + ", ".join(hits)
    )


def test_trust_center_canonical_is_the_product_origin():
    """Product HTML stays on a-11-oy.com even if HF runtime.domains is PENDING.

    PENDING is KALLPA/Stephen DNS, not an HTML rewrite to *.hf.space.
    """
    html = (ROOT / "web" / "trust.html").read_text(encoding="utf-8")
    assert 'rel="canonical" href="https://a-11-oy.com/trust"' in html
    assert _FURNITURE_HOST not in html
    assert 'property="og:url" content="https://a-11-oy.com/trust"' in html


def test_assurance_canonical_is_the_product_origin():
    html = (ROOT / "pages" / "assurance.html").read_text(encoding="utf-8")
    assert 'rel="canonical" href="https://a-11-oy.com/assurance"' in html
    assert _FURNITURE_HOST not in html
    assert 'property="og:url" content="https://a-11-oy.com/assurance"' in html


def test_product_html_canonicals_are_not_rewritten_to_the_hf_space():
    """HF PENDING custom-domain state is not papered over in HTML.

    Hugging Face injects Link rel=canonical to the Space URL at the proxy.
    Product pages must keep <link rel="canonical"> on https://a-11-oy.com.
    """
    pages = (
        ROOT / "web" / "trust.html",
        ROOT / "pages" / "assurance.html",
        ROOT / "a11oy_landing.html",
        ROOT / "pages" / "console.html",
    )
    href_re = re.compile(
        r'rel\s*=\s*["\']canonical["\'][^>]*href\s*=\s*["\']([^"\']+)["\']'
        r'|href\s*=\s*["\']([^"\']+)["\'][^>]*rel\s*=\s*["\']canonical["\']',
        re.IGNORECASE,
    )
    for path in pages:
        html = path.read_text(encoding="utf-8")
        match = href_re.search(html)
        assert match, f"{path.relative_to(ROOT)} missing rel=canonical"
        href = match.group(1) or match.group(2)
        assert href.startswith("https://a-11-oy.com"), (
            f"{path.name} canonical must stay on the public product origin, got {href}"
        )
        assert "hf.space" not in href
        assert "huggingface.co" not in href
        assert _FURNITURE_HOST not in href


def test_app_does_not_export_net_as_sunset():
    import a11oy_canonical_domain as cd

    assert not hasattr(cd, "SUNSET_DOMAIN")
    assert cd.REGISTRY_HOST == "a11oy.net"
    assert cd.CANONICAL_HOST == "a-11-oy.com"
    assert cd.FORBIDDEN_PUBLIC_HOST == _FURNITURE_HOST


def _methods(path: str) -> set[str]:
    import serve

    return {
        method
        for route in serve.app.router.routes
        if getattr(route, "path", None) == path
        for method in getattr(route, "methods", set()) or set()
    }


@pytest.mark.parametrize("path", _HTML_DOCUMENT_PATHS + (
    "/healthz",
    "/readyz",
    "/api/health",
    "/api/a11oy/healthz",
    "/api/a11oy/v1/health",
))
def test_html_document_routes_declare_head(path):
    assert {"GET", "HEAD"}.issubset(_methods(path)), (
        f"{path} must accept HEAD as well as GET (crawlers/monitors use HEAD)"
    )


_QHAPAQ_HEAD_PATHS = (
    "/",
    "/verify",
    "/console",
    "/trust",
    "/assurance",
    "/robots.txt",
    "/sitemap.xml",
    "/healthz",
    "/readyz",
    "/api/health",
    "/api/a11oy/healthz",
    "/api/a11oy/v1/health",
)


@pytest.mark.parametrize("path", _QHAPAQ_HEAD_PATHS)
def test_qhapaq_probes_accept_head(path):
    """QHAPAQ S1–S12: HEAD must match GET (not 405, not proxy 404)."""
    from starlette.testclient import TestClient

    import serve

    client = TestClient(serve.app, raise_server_exceptions=False)
    get_r = client.get(path)
    head_r = client.head(path)
    assert head_r.status_code not in (404, 405), (
        f"{path} HEAD must not 404/405 (got {head_r.status_code}; GET {get_r.status_code})"
    )
    assert head_r.content in (b"", None) or len(head_r.content) == 0
    if get_r.status_code == 200:
        assert head_r.status_code == 200
        get_ct = (get_r.headers.get("content-type") or "").split(";")[0]
        head_ct = (head_r.headers.get("content-type") or "").split(";")[0]
        if get_ct:
            assert head_ct == get_ct
    else:
        assert head_r.status_code == get_r.status_code


def test_trust_get_body_uses_product_canonical():
    from starlette.testclient import TestClient

    import serve

    response = TestClient(serve.app, raise_server_exceptions=False).get("/trust")
    assert response.status_code == 200
    body = response.content
    assert b"https://a-11-oy.com/trust" in body
    assert _FURNITURE_HOST.encode("ascii") not in body
    assert b"a11oy.net" in body
    assert b"/verify" in body


def test_http_link_canonical_is_product_origin_not_hf_space():
    """Crawlers must not see huggingface.co/spaces as the product canonical."""
    from starlette.testclient import TestClient

    import serve

    client = TestClient(serve.app, raise_server_exceptions=False)
    expected = {
        "/": "https://a-11-oy.com/",
        "/console": "https://a-11-oy.com/console",
        "/trust": "https://a-11-oy.com/trust",
        "/sitemap.xml": "https://a-11-oy.com/sitemap.xml",
    }
    for path, url in expected.items():
        response = client.get(path)
        assert response.status_code == 200, path
        links = response.headers.get_list("link") if hasattr(response.headers, "get_list") else [response.headers.get("link") or ""]
        joined = " ".join(links)
        assert f"<{url}>" in joined, path
        assert "canonical" in joined.lower()
        assert "huggingface.co/spaces/" not in joined.lower()
        assert _FURNITURE_HOST not in joined


def test_options_on_documents_declares_allow_and_methods():
    from starlette.testclient import TestClient

    import serve

    client = TestClient(serve.app, raise_server_exceptions=False)
    for path in ("/", "/console"):
        response = client.options(path)
        assert response.status_code == 200, path
        allow = response.headers.get("allow") or ""
        acam = response.headers.get("access-control-allow-methods") or ""
        assert "GET" in allow and "HEAD" in allow and "OPTIONS" in allow
        assert "GET" in acam and "HEAD" in acam


def test_verify_page_is_the_interactive_tool_not_the_registry():
    html = (ROOT / "pages" / "verify.html").read_text(encoding="utf-8")
    assert "a-11-oy.com" in html
    assert "a11oy.net" in html
    assert "RECORD" in html
    assert _FURNITURE_HOST not in html


def test_landing_does_not_imply_killinchu_live():
    html = (ROOT / "a11oy_landing.html").read_text(encoding="utf-8")
    card = html.split("<h3>killinchu</h3>", 1)[1].split("<div class=\"vcard\">", 1)[0]
    assert "UNAVAILABLE" in card
    assert "timed out" in card.lower()
    assert "markKillinchuUnavailable" in html
    assert 'href="/elite">killinchu' not in html
    assert "huggingface.co/spaces/SZLHOLDINGS/killinchu" in html


def test_killinchu_path_bridge_labels_runtime_unavailable():
    from starlette.testclient import TestClient

    import serve

    client = TestClient(serve.app, raise_server_exceptions=False)
    response = client.get("/killinchu", follow_redirects=False)
    assert response.status_code == 307
    location = response.headers.get("location") or ""
    assert location.startswith("https://huggingface.co/spaces/SZLHOLDINGS/killinchu")
    assert "szlholdings-killinchu.hf.space" not in location
    assert response.headers.get("X-SZL-Route-State") == "UNAVAILABLE_RUNTIME"
    hub = response.headers.get("X-SZL-Killinchu-Hub") or ""
    assert hub.startswith("https://huggingface.co/spaces/SZLHOLDINGS/killinchu")
    link = response.headers.get("Link") or ""
    assert "rel=\"alternate\"" in link
    assert "rel=\"canonical\"" not in link.lower()


def test_empty_observability_dag_is_unavailable_not_a_live_zero():
    import a11oy_warhacker_obs as who
    import szl_observability as obs

    assert who.observability_dag_state(None) == "UNAVAILABLE"
    assert who.observability_dag_state({"available": False, "depth": 0}) == "UNAVAILABLE"
    assert who.observability_dag_state({"available": True, "depth": 0, "spans": []}) == "UNAVAILABLE"
    assert who.observability_dag_state({"available": True, "depth": 3, "spans": [{}, {}, {}]}) == "OBSERVED"

    ring = obs.TraceRing(capacity=8)
    obs.TRACES = ring
    summary = obs.health_summary()
    assert summary["state"] == "UNAVAILABLE"
    assert "last 0 traces" in summary["window"]


def test_observability_summary_does_not_feed_sample_depth_or_invent_organs():
    """SAMPLE chain depth 24 and inventory organ counts are not live."""
    from starlette.testclient import TestClient

    import serve

    body = TestClient(serve.app, raise_server_exceptions=False).get(
        "/api/a11oy/v1/observability/summary"
    ).json()
    state = body.get("observation_state") or body.get("state")
    melt = ((body.get("melt") or {}).get("metrics")) or {}
    assert melt.get("dag_depth") != 24
    assert body.get("dag_depth") != 24
    if state in ("inventory", "UNAVAILABLE", "IDLE") or body.get("observed") is False:
        assert melt.get("organs_reachable") is None
        assert body.get("dag_depth") is None


def test_pages_landing_does_not_treat_killinchu_or_organs_as_live():
    html = (ROOT / "pages" / "landing.html").read_text(encoding="utf-8")
    assert 'href="https://szlholdings-killinchu.hf.space/"' not in html
    assert "huggingface.co/spaces/SZLHOLDINGS/killinchu" in html
    assert "UNAVAILABLE" in html
    assert "<h4>Live</h4>" not in html
    assert "observation_state" in html
    assert "organs_reachable" in html


def test_empty_compute_fabric_status_is_unavailable(monkeypatch):
    import szl_backend_hardening as bh
    import szl_frontier_manifest as manifest

    monkeypatch.setattr(
        bh,
        "probe_fabric_pool",
        lambda: {
            "nodes": [
                {"reachable": False, "kind": "gpu"},
                {"reachable": False, "kind": "cpu"},
            ],
            "cached_at": None,
        },
    )
    tile = manifest._tile_compute_fabric()
    assert "UNAVAILABLE" in tile["status"]
    assert "IDLE" not in tile["status"]
    assert tile["nodes_reachable"] == 0


def test_lean_health_json_signer_is_absent_not_dsse_live():
    """QHAPAQ: only /api/a11oy/healthz rollup.signer may stamp DSSE-LIVE."""
    from starlette.testclient import TestClient

    import serve

    client = TestClient(serve.app, raise_server_exceptions=False)
    for path in ("/healthz", "/api/health", "/api/a11oy/v1/health"):
        body = client.get(path).json()
        signer = body.get("signer") or {}
        assert signer.get("status") in ("ABSENT", "UNAVAILABLE"), path
        assert signer.get("status") != "DSSE-LIVE"
        assert signer.get("signing_available") is False
        assert signer.get("scheme") == "UNAVAILABLE"

    rollup = client.get("/api/a11oy/healthz").json()["rollup"]["signer"]
    assert "status" in rollup
    assert "signing_available" in rollup
    if rollup.get("signing_available") is True:
        assert rollup["status"] == "DSSE-LIVE"
        assert "DSSE" in str(rollup.get("scheme") or "")
    else:
        assert rollup["status"] in ("UNSIGNED-LOCAL", "UNAVAILABLE", "ABSENT")
        assert rollup["status"] != "DSSE-LIVE"


def test_iss_position_numbers_are_labeled_or_unavailable():
    import a11oy_live_feeds as feeds

    labeled = feeds.label_iss_data(
        {"latitude": 41.2, "longitude": -73.4, "altitude": 420.1, "velocity": 27580.0}
    )
    assert labeled is not None
    assert labeled["units"]["latitude"] == "degrees"
    assert labeled["units"]["longitude"] == "degrees"
    assert labeled["units"]["altitude"] == "km"
    assert labeled["units"]["velocity"] == "km/h"
    assert feeds.label_iss_data({"latitude": 41.2}) is None
    closed = feeds._iss_envelope({"data": {"foo": 1}})
    assert closed["state"] == "UNAVAILABLE"
    assert closed["data"] is None
    assert closed["mode"] == "unavailable"


def test_live_fetch_status_stays_honest_404():
    """Do not invent GET /v1/live-fetch/status. Undeclared path → honest 404."""
    from starlette.testclient import TestClient

    import serve

    response = TestClient(serve.app, raise_server_exceptions=False).get(
        "/v1/live-fetch/status"
    )
    assert response.status_code == 404
    body = response.json()
    assert body.get("status") == "NOT_FOUND"
    assert "undeclared path refused SPA fallback" in (body.get("reason") or "")


_LOCKED8_IDS = ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]


def test_honest_v1_surfaces_kernel_locked_eight():
    """QHAPAQ S7: kernel locked-proven is Lean-8 on /honest. Do not change 8."""
    from starlette.testclient import TestClient

    import serve

    body = TestClient(serve.app, raise_server_exceptions=False).get(
        "/api/a11oy/v1/honest"
    ).json()
    assert body["locked_formula_count"] == 8
    assert body["locked_formula_ids"] == _LOCKED8_IDS
    lock = body.get("doctrine_lock") or {}
    assert lock.get("locked_formula_count") == 8
    assert lock.get("locked_formula_ids") == _LOCKED8_IDS


def test_genome_catalog_locked_proven_stays_25_of_144():
    """QHAPAQ S7: genome catalog tag LOCKED-PROVEN is 25 of 144. Do not change 25."""
    import json
    from collections import Counter

    entries = json.loads((ROOT / "data" / "genome.json").read_text(encoding="utf-8"))
    tags = Counter((e or {}).get("tag", "untagged") for e in entries)
    assert len(entries) == 144
    assert tags["LOCKED-PROVEN"] == 25
    assert tags["LOCKED-PROVEN"] != 8


def test_overview_splits_kernel_locked_from_genome_catalog():
    import szl_org_lambda as org

    overview = org.org_overview()
    tiers = overview["proof_tiers"]
    assert tiers["locked"] == 8
    assert tiers["kernel_locked_ids"] == _LOCKED8_IDS
    assert tiers["genome_locked_proven"] == 25
    assert tiers["locked"] != tiers["genome_locked_proven"]
    assert overview["genome_count"] == 144


def test_ui_does_not_bind_kernel_locked_proven_to_genome_tier():
    """Kernel chips (#cnt-locked, #pt-locked, locked-8 rows, publications) must
    not read genome.tier_counts.LOCKED-PROVEN. Catalog may still name that tag.
    """
    trust = (ROOT / "web" / "trust.html").read_text(encoding="utf-8")
    landing = (ROOT / "a11oy_landing.html").read_text(encoding="utf-8")
    console = (ROOT / "pages" / "console.html").read_text(encoding="utf-8")
    formulas = (ROOT / "a11oy_formulas_page.py").read_text(encoding="utf-8")

    assert "/api/a11oy/v1/honest" in trust
    assert "locked_formula_count" in trust
    assert "$('cnt-locked').firstChild.nodeValue=(tc['LOCKED-PROVEN']??'N/A')" not in trust
    assert "if(e.tag!=='LOCKED-PROVEN')continue" not in trust

    assert "loadKernelLocked" in landing
    assert 'getJSON("/api/a11oy/v1/honest")' in landing
    assert 'locked: tc["LOCKED-PROVEN"]' not in landing
    assert "locked: tc['LOCKED-PROVEN']" not in landing
    set_tiers = re.search(r"function setTiers\(t\)\{.*?\n  \}", landing, re.S)
    assert set_tiers, "setTiers missing"
    assert '$("pt-locked")' not in set_tiers.group(0)
    assert "$('pt-locked')" not in set_tiers.group(0)

    pubs = console[console.find("async function renderPublications"):]
    pubs = pubs[: pubs.find("c.innerHTML=h")]
    assert "/v1/honest" in pubs
    assert "LOCKED-PROVEN" not in pubs

    assert "genome LOCKED-PROVEN" in formulas
    assert "lp + ' locked-proven'" not in formulas
    assert "gt.className = 'badge ok'" not in formulas


def test_ayni_lock_does_not_drift():
    """AYNI: product Link canonical, no .net 301, HEAD is the app, orange-cloud.

    Do not grey-cloud the apex. Do not stamp HF custom domain LIVE. This repo
    does not change DNS. Stephen may add the HF verify TXT later without
    dropping the Cloudflare proxy. Does not merge PR 1363.
    """
    texts = {
        "canon": (ROOT / "a11oy_canonical_domain.py").read_text(encoding="utf-8"),
        "sync": (ROOT / ".github" / "workflows" / "hf-sync.yml").read_text(encoding="utf-8"),
        "runbook": (ROOT / "docs" / "runbook.md").read_text(encoding="utf-8"),
        "spaces": (ROOT / "docs" / "SPACES_HEALTH_OPERATIONS.md").read_text(encoding="utf-8"),
        "serve": (ROOT / "serve.py").read_text(encoding="utf-8"),
        "gotchas": (ROOT / "KNOWN_GOTCHAS.md").read_text(encoding="utf-8"),
        "agents": (ROOT / "AGENTS.md").read_text(encoding="utf-8"),
    }
    def _flat(text: str) -> str:
        return " ".join(text.split())

    for name in ("canon", "sync", "runbook", "spaces", "gotchas", "agents", "serve"):
        blob = _flat(texts[name])
        assert "orange-cloud" in blob, name
        assert "do not grey-cloud" in blob.lower(), name
        assert "PENDING" in blob, name

    canon = texts["canon"]
    assert "huggingface.co/spaces is never the product canonical" in canon
    assert "This app does not change DNS" in canon
    assert "SUNSET_DOMAIN" not in canon
    import a11oy_canonical_domain as cd

    assert not hasattr(cd, "SUNSET_DOMAIN")
    assert cd.product_canonical_url("/trust") == "https://a-11-oy.com/trust"
    assert "huggingface.co" not in cd.product_canonical_url("/console")
    furniture = "a11oy.com"
    assert furniture not in cd.product_canonical_url("/console").replace("a-11-oy.com", "")

    sync = texts["sync"]
    assert "This workflow does not change DNS" in sync
    assert "Do not stamp LIVE" in sync

    serve = texts["serve"]
    assert 'allow_methods=["GET", "HEAD", "POST", "OPTIONS"]' in serve
    assert '@app.api_route("/robots.txt", methods=["GET", "HEAD"])' in serve
    assert '@app.api_route("/sitemap.xml", methods=["GET", "HEAD"])' in serve
    assert "the app, not Cloudflare" in serve
    assert "HEAD 405 is the app" in serve or "Same HEAD 405" in serve

