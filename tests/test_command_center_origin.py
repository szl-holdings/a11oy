# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Static wiring guards for A11oy's bound command surfaces.

/command remains the canonical 20-tab Elite Console. /command-v2 is an
additive, source-derived eight-room skin. /console remains the separate
operator runtime and host-root /brain remains Hickok dual-stream.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEGACY_SPA = ROOT / "pages" / "command-center.html"
ELITE_SPA = ROOT / "web" / "elite_console.html"
V2_PAGE = ROOT / "pages" / "command-v2.html"
MOD = ROOT / "a11oy_command_center.py"
SERVE = ROOT / "serve.py"
DOCKER = ROOT / "Dockerfile"


def test_elite_command_center_is_real_api_bound_surface() -> None:
    html = ELITE_SPA.read_text(encoding="utf-8")
    assert html.startswith("<!DOCTYPE html>") or "<!DOCTYPE html>" in html[:400]
    assert "Elite Console" in html
    assert "20 fully-functional tabs" in html
    assert "zero mocks" in html.lower()
    assert "/api/a11oy/" in html
    assert "Conjecture 1" in html
    assert "cdnjs" not in html and "googleapis" not in html and "jsdelivr" not in html


def test_v2_is_additive_source_derived_and_mobile_safe() -> None:
    html = V2_PAGE.read_text(encoding="utf-8")
    assert html.startswith("<!doctype html>")
    assert '<meta name="viewport"' in html
    assert "A11oy Command" in html
    assert "Conjecture 1" in html
    assert "source-derived" in html.lower()
    assert 'cache:"no-store"' in html
    assert 'credentials:"omit"' in html
    assert "min-height:44px" in html
    assert "prefers-reduced-motion" in html
    assert "forced-colors" in html
    assert "aria-modal=\"true\"" in html
    assert "cdnjs" not in html and "googleapis" not in html and "jsdelivr" not in html
    for endpoint in (
        "/api/a11oy/v1/honest",
        "/api/a11oy/v1/lambda",
        "/api/a11oy/v1/ledger",
        "/api/a11oy/v1/signing-status",
        "/api/hatun/evidence",
        "/api/build-info",
    ):
        assert endpoint in html


def test_legacy_public_spa_remains_available_as_fallback() -> None:
    html = LEGACY_SPA.read_text(encoding="utf-8")
    assert html.startswith("<!DOCTYPE html>")
    assert 'rel="canonical" href="https://a-11-oy.com/command"' in html
    assert "a11oy.net" in html
    assert "Conjecture 1" in html


def test_module_prefers_elite_and_preserves_existing_operator_routes() -> None:
    src = MOD.read_text(encoding="utf-8")
    assert "def register(app" in src
    assert 'here / "web" / "elite_console.html"' in src
    assert 'Path("/app/web/elite_console.html")' in src
    assert 'here / "pages" / "command-center.html"' in src
    for route in (
        '"/command"',
        '"/command-v2"',
        '"/command/constellation"',
        '"/command/brain"',
        '"/command/ops"',
        '"/operator-pane"',
    ):
        assert route in src
    assert '"command-v2.html"' in src
    assert "does not steal /console" in src


def test_serve_imports_and_calls_register() -> None:
    src = SERVE.read_text(encoding="utf-8")
    assert "import a11oy_command_center as _a11oy_command_center" in src
    assert '_a11oy_command_center.register(app, ns="a11oy")' in src
    assert 'for _cc_path in ("/command", "/command-center")' not in src


def test_dockerfile_copies_command_assets() -> None:
    src = DOCKER.read_text(encoding="utf-8")
    assert "a11oy_command_center.py" in src
    assert "COPY pages/ ./pages/" in src
    assert "COPY web/ ./web/" in src or "web/elite_console.html" in src


def test_module_selftest_if_starlette_present() -> None:
    try:
        import starlette  # noqa: F401
    except ImportError:
        return
    import a11oy_command_center as module

    module._selftest()
