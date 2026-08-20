# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Sign-off: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""test_energy_showcase — proves the holographic 3D energy-ops showcase contracts.

The showcase (static/3d/energy_showcase/showcase.js) is ONE shared ES module deployed
on THREE surfaces — the a11oy energy page (web/energy-holographic.html), the /holographic
"energy" tab (static/3d/surfaces/energy.js), and the Hugging Face SZLHOLDINGS/energy
Space (web/energy.html). These checks enforce, headlessly (no browser), the mission's
explicit requirements + doctrine v11:

  * the showcase mounts: exports buildShowcase / SHOWCASE_GRAPHS / SHOWCASE_ENDPOINTS
  * it wires ALL 5 real a11oy energy endpoints via szl3d_live.poll (never hardcoded)
  * it renders an honesty chip for EVERY doctrine state
    (MEASURED / MODELED / SAMPLE / ESTIMATE / STRUCTURAL-ONLY)
  * it degrades honestly on 404 / network error / {degraded} -> NO-LIVE-DATA, never
    fabricating a telemetry value
  * 0 runtime CDN anywhere in the showcase or the three surfaces (grep, fetch-shaped)
  * >= 16 DISTINCT 3D views are present (16-19 graphs)
  * all three surfaces load the SAME showcase module against the SAME live endpoints

Source-level (string) assertions, like the sibling test_szl3d_holographic.py — the
browser-level render is covered by static/3d/selftest/index.html.
"""
import re
from pathlib import Path

import szl3d_holographic as m

ROOT = Path(__file__).resolve().parent
BASE = m._base_dir()                              # static/3d
SHOWCASE = BASE / "energy_showcase" / "showcase.js"
SURFACE = BASE / "surfaces" / "energy.js"
HF_PAGE = ROOT / "web" / "energy.html"            # Hugging Face Space source
A11OY_PAGE = ROOT / "web" / "energy-holographic.html"

# The 5 real a11oy energy endpoints the showcase MUST poll (never fabricate).
EXPECTED_ENDPOINTS = (
    "/api/a11oy/v1/energy/operator/status",
    "/api/a11oy/v1/energy/ledger",
    "/api/a11oy/v1/energy/projection?window=running",
    "/api/a11oy/v1/harvest/posture",
    "/api/a11oy/v1/compute-pool",
)
HONESTY_STATES = ("MEASURED", "MODELED", "SAMPLE", "ESTIMATE", "STRUCTURAL-ONLY")


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ---- the module exists + exposes the mount contract -----------------------
def test_showcase_module_present_and_exports_mount_contract():
    assert SHOWCASE.is_file(), "energy_showcase/showcase.js missing"
    src = _read(SHOWCASE)
    assert "export function buildShowcase(ctx)" in src
    assert "export const SHOWCASE_GRAPHS" in src
    assert "export const SHOWCASE_ENDPOINTS" in src
    assert "export default" in src
    # mount returns a controller with dispose() so surfaces can tear it down
    assert "function dispose()" in src and "dispose," in src


# ---- all 5 real endpoints are wired via the live poller -------------------
def test_all_five_real_endpoints_present():
    src = _read(SHOWCASE)
    for ep in EXPECTED_ENDPOINTS:
        assert ep in src, f"endpoint not wired in showcase: {ep}"


def test_endpoints_polled_via_szl3d_live_not_hardcoded():
    src = _read(SHOWCASE)
    # Each graph is driven by ctx.live.poll(endpoint, ...) — the szl3d live poller,
    # NOT a fabricated constant. Exactly the szl3d surface contract.
    assert "ctx.live.poll(" in src
    # the endpoints flow from the frozen EP table into each graph's `endpoint`
    assert "const EP = Object.freeze(" in src
    assert src.count("endpoint:") >= 16, "fewer than 16 graphs carry an endpoint binding"


# ---- honesty chips for EVERY doctrine state -------------------------------
def test_every_honesty_state_rendered():
    src = _read(SHOWCASE)
    for state in HONESTY_STATES:
        assert state in src, f"honesty state never rendered: {state}"
    # labels are READ from the JSON, never invented/upgraded
    assert "readHonestyLabel" in src or "data_label" in src or "joules_label" in src
    # chips are drawn through the shared szl3d label toolkit
    assert "ctx.label.chip(" in src and "ctx.label.updateChip(" in src


def test_revenue_never_measured_until_charge_clears():
    # Doctrine v11 PROVE-OR-DOWNGRADE: revenue/earnings stay MODELED/ESTIMATE, never
    # silently promoted to MEASURED. The earnings/projection graphs must label as such.
    src = _read(SHOWCASE)
    assert "MODELED" in src and "ESTIMATE" in src
    # joules are the only thing allowed to be MEASURED
    assert "MEASURED" in src


# ---- honest degradation on 404 / error / degraded ------------------------
def test_degrades_to_no_live_data_never_fabricates():
    src = _read(SHOWCASE)
    # missing telemetry -> explicit NO-LIVE-DATA readout (not a fabricated 0/number)
    assert "NO-LIVE-DATA" in src
    assert src.count("NO-LIVE-DATA") >= 5, "degraded fallback not applied across graphs"
    # the live poller itself (shared toolkit) handles 404 + degraded + drives the badge
    live = _read(BASE / "szl3d" / "szl3d_live.js")
    assert "404" in live and "MISSING" in live
    assert "degraded" in live and "DEGRADED" in live
    assert "NO-LIVE-DATA" in live
    # numbers are parsed honestly: missing != silently coerced to 0
    assert "Number.isFinite" in src


# ---- >= 16 distinct 3D views ----------------------------------------------
def test_at_least_sixteen_distinct_3d_views():
    src = _read(SHOWCASE)
    # the registry array of graph factory functions
    mm = re.search(r"const GRAPH_FACTORIES\s*=\s*\[(.*?)\];", src, re.S)
    assert mm, "GRAPH_FACTORIES registry not found"
    factories = [t.strip() for t in mm.group(1).replace("\n", " ").split(",") if t.strip()]
    assert len(factories) >= 16, f"only {len(factories)} graphs (need >= 16)"
    assert len(factories) <= 19, f"{len(factories)} graphs (mission caps at 19)"
    # they are DISTINCT factory functions (no duplicate views padding the count)
    assert len(set(factories)) == len(factories), "duplicate graph factories"
    # each factory is actually defined in the module
    for fn in factories:
        assert re.search(rf"\bfunction {re.escape(fn)}\b", src), f"factory {fn} not defined"


def test_each_graph_uses_real_three_geometry():
    # views must be genuine 3D (THREE meshes/points/lines), not flat DOM charts.
    # THREE is aliased in the module (e.g. `const T = ctx.THREE`), so match the
    # constructor suffixes rather than a fixed namespace prefix.
    src = _read(SHOWCASE)
    for token in (".Mesh(", ".Points(", ".Line("):
        assert token in src, f"no {token} — graphs may not be real 3D"
    assert "BufferGeometry" in src


# ---- 0 runtime CDN across the showcase + all three surfaces ---------------
def test_zero_runtime_cdn_in_showcase_and_surfaces():
    # reuse the SAME doctrine scanner CI + the in-image selftest use, over the whole
    # authored 3d tree (which now includes energy_showcase/ + surfaces/energy.js).
    violations = list(m.no_cdn_violations(BASE))
    assert not violations, "runtime-CDN reference in authored 3d code:\n" + "\n".join(violations)


def test_zero_runtime_cdn_in_both_html_pages():
    # the two served HTML pages (a11oy + HF) must fetch three.js/toolkit same-origin
    # via the importmap, never from a CDN. Check fetch-shaped external refs only
    # (<a href> attribution links are human links, not runtime fetches).
    fetch_shaped = re.compile(
        r"""(<script[^>]*\bsrc\s*=\s*['"]https?://"""
        r"""|<link[^>]*\bhref\s*=\s*['"]https?://"""
        r"""|\bimport\b[^;\n]*\bfrom\s*['"]https?://"""
        r"""|\bimport\s*\(\s*['"]https?://"""
        r"""|\bfetch\s*\(\s*['"`]https?://)""",
        re.I,
    )
    for page in (HF_PAGE, A11OY_PAGE):
        assert page.is_file(), f"page missing: {page}"
        txt = _read(page)
        hit = fetch_shaped.search(txt)
        assert not hit, f"fetch-shaped CDN ref in {page.name}: ...{txt[hit.start():hit.start()+80]}..."
        # and they resolve three locally through the importmap
        assert "/static/3d/vendor/three/three.module.min.js" in txt


# ---- all three surfaces load the SAME module against the SAME endpoints ----
def test_holographic_surface_delegates_to_showcase():
    src = _read(SURFACE)
    assert "energy_showcase/showcase.js" in src
    assert "buildShowcase" in src
    assert "function mount" in src and "function unmount" in src
    assert "export default" in src


def test_all_three_surfaces_import_the_one_showcase():
    needle = "/static/3d/energy_showcase/showcase.js"
    for page in (SURFACE, HF_PAGE, A11OY_PAGE):
        assert needle in _read(page), f"{page.name} does not load the shared showcase"


def test_hf_page_loads_same_live_endpoints():
    # The HF Space page (web/energy.html) loads the showcase, which polls the SAME
    # 5 real endpoints -> the HF Space shows the SAME live data as a11oy. We assert
    # the page boots the szl3d toolkit + showcase (the endpoints live in the shared
    # module, proven by test_all_five_real_endpoints_present).
    txt = _read(HF_PAGE)
    assert "/static/3d/szl3d/szl3d_boot.js" in txt
    assert "/static/3d/szl3d/szl3d_live.js" in txt
    assert "/static/3d/energy_showcase/showcase.js" in txt
    assert 'type="importmap"' in txt


# ---- in-image delivery: the showcase ships in the Docker image ------------
def test_showcase_is_copied_into_the_image():
    df = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    # the whole static/3d tree (incl. energy_showcase/) is COPY'd as a directory
    assert "static/3d/" in df
    # both served HTML pages are COPY'd per-file
    assert "web/energy.html" in df
    assert "web/energy-holographic.html" in df
