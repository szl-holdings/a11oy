# SPDX-License-Identifier: Apache-2.0
"""Static contracts for the Anatomy v5 read-only digital twin.

These checks intentionally inspect the shipped HTML instead of duplicating its
browser logic.  They prevent an attractive visualization from silently losing a
real evidence source, collapsing the genome and wired-index views, or turning a
failed probe into fabricated healthy state.
"""
from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ANATOMY_PAGE = ROOT / "pages" / "anatomy-v5.html"
ECOSYSTEM_PAGE = ROOT / "pages" / "ecosystem.html"

REQUIRED_ENDPOINTS = {
    "/api/a11oy/v1/ecosystem/atlas",
    "/api/a11oy/v1/brain/pulse",
    "/api/a11oy/v1/router/stats",
    "/api/a11oy/v1/mesh/state",
    "/api/a11oy/v1/spaces/health",
    "/api/a11oy/v1/genome",
    "/api/a11oy/v1/formulas/index",
    "/api/a11oy/v1/wire-d/status",
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_anatomy_v5_is_a_real_versioned_page_linked_from_the_atlas() -> None:
    assert ANATOMY_PAGE.is_file(), "the /anatomy-v5 route must have a real page asset"
    html = _read(ANATOMY_PAGE)
    ecosystem = _read(ECOSYSTEM_PAGE)

    assert "<title>Anatomy v5" in html
    assert '<link rel="canonical" href="https://a-11-oy.com/anatomy-v5">' in html
    assert 'href="/anatomy-v5"' in ecosystem
    assert "Anatomy v5" in ecosystem


def test_anatomy_v5_references_all_eight_same_origin_evidence_sources() -> None:
    html = _read(ANATOMY_PAGE)
    referenced = set(re.findall(r"['\"](/(?:api/|v1/)[^'\"]+)['\"]", html))

    assert REQUIRED_ENDPOINTS <= referenced
    # Router may use its established same-origin alias as a fallback, but none
    # of the eight primary probes may be replaced with a cross-origin browser URL.
    assert "/v1/router/stats" in referenced
    endpoints_block = html.split("const endpoints={", 1)[1].split("};", 1)[0]
    assert "http://" not in endpoints_block
    assert "https://" not in endpoints_block


def test_genome_and_wired_formula_index_remain_distinct_sources() -> None:
    html = _read(ANATOMY_PAGE)
    formula_source = _read(ROOT / "a11oy_formula_endpoints.py")

    assert "genome:['/api/a11oy/v1/genome']" in html
    assert "formulas:['/api/a11oy/v1/formulas/index']" in html
    assert "genomeRows" in html and "wiredRows" in html
    assert "GENOME |" in html and "WIRED" in html
    assert 'href="/api/a11oy/v1/genome"' in html
    assert 'href="/api/a11oy/v1/formulas/index"' in html
    assert "mergeFormulaRows" in html
    assert "wiredMap" in html and "seen.has(key)" in html
    assert "GENOME_ONLY" in html and "WIRED_ONLY" in html
    assert "genome + runtime registry" in html
    assert "UNION |" in html
    assert '"state": "AVAILABLE"' in formula_source
    assert "not a live execution signal" in formula_source


def test_failed_or_degraded_sources_keep_honest_state_labels() -> None:
    html = _read(ANATOMY_PAGE)

    # The endpoint's declared state is preserved. A failed request has no data
    # and is explicitly UNAVAILABLE; it is never converted to a successful row.
    assert "classifyProbe(name,hit.data)" in html
    assert "hit.data?.state||hit.data?.status||'LIVE'" not in html
    assert "return declared||'OBSERVED'" in html
    assert "HONEST_STUB_CATALOG" in html and "return 'MODELED'" in html
    assert "name==='formulas'||name==='genome'" in html
    assert "state:'UNAVAILABLE',data:null" in html
    assert "failed probe stays visibly unavailable" in html
    assert "Red means unavailable" in html
    assert "Runtime reachability is not model quality" in html
    assert "No entries were invented" in html

    # These are the evidence states the atlas may return. Keeping the literal
    # vocabulary in the page makes the browser show the state rather than infer
    # a stronger claim from a count or a successful HTTP response.
    for label in (
        "LIVE", "CACHED", "STALE_CACHE", "SNAPSHOT", "MODELED",
        "OBSERVED", "AVAILABLE", "DEGRADED", "UNCONFIGURED",
        "READY_UNMEASURED", "MEASURED", "CONFLICT", "UNAVAILABLE",
    ):
        assert label in html
    assert "source-derived" in html
    assert "read-only digital twin" in html
    assert "does not train models, mutate datasets, or mint receipts on GET" in html


def test_empty_formula_and_route_states_do_not_create_placeholder_records() -> None:
    html = _read(ANATOMY_PAGE)

    assert "Router did not expose a route array" in html
    assert "No formula rows are available for this filter" in html
    assert "rows.map" in html
    assert "if(!rows.length)" in html
    # No static formula or route object array is embedded as a substitute for
    # either endpoint. The only source declarations are URL arrays.
    endpoints_block = html.split("const endpoints={", 1)[1].split("};", 1)[0]
    assert "model:" not in endpoints_block
    assert "formula:" not in endpoints_block


def test_brain_lit_fields_are_numeric_leaf_paths_not_the_lit_object() -> None:
    html = _read(ANATOMY_PAGE)

    assert "lit.surfaces_lit" in html
    assert "lit.organs_lit" in html
    assert "surfacesLit+' surfaces'" in html
    assert "organsLit+' organs'" in html
    assert "['lit.count','lit'" not in html


def test_tabs_follow_the_aria_keyboard_pattern() -> None:
    html = _read(ANATOMY_PAGE)

    for name in ("organism", "nervous", "wire-d", "genome", "evidence"):
        assert f'id="tab-{name}"' in html
        assert f'aria-controls="view-{name}"' in html
        assert f'role="tabpanel" aria-labelledby="tab-{name}"' in html
    assert 'aria-selected="true"' in html
    assert 'aria-selected="false"' in html
    assert "setAttribute('aria-selected',String(selected))" in html
    for key in ("ArrowRight", "ArrowLeft", "Home", "End"):
        assert key in html


def test_wire_d_panel_keeps_v5_current_and_requires_an_explicit_closed_registry_post() -> None:
    html = _read(ANATOMY_PAGE)
    provenance = _read(ROOT / "szl_provenance.py")

    assert "Anatomy v5 remains current" in html
    assert "A future v6 is not claimed here" in html
    assert "future v6" not in html.split("<title>", 1)[1].split("</title>", 1)[0]
    assert 'wireD:[\'/api/a11oy/v1/wire-d/status\']' in html
    assert "fetch('/api/a11oy/v1/wire-d/probe',{method:'POST'" in html
    assert "body:JSON.stringify({target})" in html
    assert 'id="wire-d-target"' in html
    assert 'id="wire-d-url"' not in html
    assert "Targets come from the closed server registry" in html
    assert "GET is read-only" in html

    assert '@app.get(f"{base}/v1/wire-d/status")' in provenance
    assert '@app.post(f"{base}/v1/wire-d/probe")' in provenance
    assert '"receipt_minted_on_get": False' in provenance
    assert '"v6": "NOT_CLAIMED"' in provenance
    assert "A11OY_WIRE_D_TARGETS" in provenance
    assert "A11OY_WIRE_D_ALLOWED_HOSTS" in provenance


def test_cached_snapshot_and_observed_states_render_amber() -> None:
    html = _read(ANATOMY_PAGE)

    for css_class in (
        ".badge.cached", ".badge.stalecache", ".badge.snapshot",
        ".badge.modeled", ".badge.observed", ".badge.available", ".badge.degraded",
        ".organ.cached", ".organ.stalecache", ".organ.snapshot",
        ".organ.modeled", ".organ.observed", ".organ.available", ".organ.degraded",
    ):
        assert css_class in html


def test_docker_image_copies_registrar_and_pages_and_serve_registers_it() -> None:
    dockerfile = _read(ROOT / "Dockerfile")
    serve = _read(ROOT / "serve.py")

    assert re.search(r"(?m)^COPY\s+pages/\s+\./pages/\s*$", dockerfile), (
        "pages/ecosystem.html and pages/anatomy-v5.html must enter the image"
    )
    assert re.search(
        r"(?m)^COPY\s+a11oy_ecosystem_atlas\.py\s+\./a11oy_ecosystem_atlas\.py\s*$",
        dockerfile,
    )
    assert "import a11oy_ecosystem_atlas as _a11oy_ecosystem_atlas" in serve
    assert '_a11oy_ecosystem_atlas.register(app, ns="a11oy")' in serve
