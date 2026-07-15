"""Responsive and honesty guards for the unified Frontier page.

These are source-level UI contract checks: the live surface registry remains the
single source of truth, every fetched surface remains filterable, and the browser
only renders a bounded page so the catalog does not dominate the viewport.
"""

from __future__ import annotations

import a11oy_frontier_page as frontier


def _html() -> str:
    return frontier._page_html("a11oy")


def test_fixed_banner_uses_measured_height_and_mobile_overflow_guards():
    html = _html()
    for marker in (
        "--honest-banner-h",
        "new ResizeObserver(syncBannerOffset)",
        "overflow-x:clip",
        "overflow-x:hidden",
        "overflow-wrap:anywhere",
        "min-width:0",
        "@media (max-width:720px)",
        "@media (max-width:420px)",
    ):
        assert marker in html


def test_surface_catalog_is_filterable_paginated_and_keyboard_reachable():
    html = _html()
    for marker in (
        'id="surface-filters"',
        'role="tablist"',
        'id="surface-search"',
        'id="surfaces-list" role="list"',
        'id="surface-prev"',
        'id="surface-next"',
        'id="surface-page-status"',
        "const SURFACE_PAGE_SIZE = 12",
        "filtered.slice(start, start + SURFACE_PAGE_SIZE)",
        "aria-controls=\"surfaces-list\"",
        "ArrowRight",
        "ArrowLeft",
        "Home",
        "End",
    ):
        assert marker in html


def test_every_registry_surface_stays_in_the_client_catalog_and_has_a_deep_link():
    manifest = frontier.build_surfaces_manifest("a11oy")
    assert manifest["ok"] is True
    assert manifest["count"] > 12
    assert manifest["count"] == len(manifest["surfaces"])
    assert len({surface["id"] for surface in manifest["surfaces"]}) == manifest["count"]

    html = _html()
    assert "allSurfaces = surfaces" in html
    assert "renderSurfaceTabs(lc)" in html
    assert "renderSurfaceCatalog()" in html
    assert "'/holographic#' + encodeURIComponent(surface.id || '')" in html
    assert "surfaces.map(su" not in html, "legacy render-all path returned"


def test_reduced_motion_and_mobile_canvas_do_not_run_continuous_animation():
    html = _html()
    assert "prefers-reduced-motion: reduce" in html
    assert "compactCanvas = matchMedia('(max-width: 720px)')" in html
    assert "document.hidden || reducedMotion.matches || compactCanvas.matches" in html
    assert "controls.autoRotate = !(reducedMotion.matches || compactCanvas.matches)" in html
    assert "compactCanvas.matches ? 1 : 2" in html


def test_evidence_brain_is_live_grounded_and_makes_no_latency_or_uplift_promise():
    html = _html()
    for marker in (
        "/api/a11oy/v1/brain/stats",
        "/api/a11oy/v1/brain/health/corpus-sources",
        "/api/a11oy/v1/brain/ask",
        'id="brain-query-form"',
        '<span class="badge unavailable" id="brain-label">UNAVAILABLE</span>',
        "performance.now()",
        "payload.cited_node_ids",
        "No generated prose was available; nothing fabricated",
        "NOT MEASURED",
        'href="/formulas"',
    ):
        assert marker in html
    assert "answers in 2 seconds" not in html.lower()


def test_surface_honesty_labels_are_preserved_verbatim():
    manifest = frontier.build_surfaces_manifest("a11oy")
    allowed = set(frontier._VALID_LABELS) | {frontier.UNAVAILABLE}
    assert all(surface["label"] in allowed for surface in manifest["surfaces"])
    html = _html()
    assert "const label = surface.label || 'UNAVAILABLE'" in html
    assert "esc(label)" in html
    assert "No result fabricated" in html
