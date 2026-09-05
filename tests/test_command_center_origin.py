# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Static wiring guards for the bound command surfaces on a-11-oy.com.

/command remains the canonical 20-tab Elite Console. /command-v2 is an
additive, source-controlled instrument. /console remains the operator runtime.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEGACY_SPA = ROOT / "pages" / "command-center.html"
COMMAND_V2 = ROOT / "pages" / "command-v2.html"
ELITE_SPA = ROOT / "web" / "elite_console.html"
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


def test_command_v2_is_accessible_honest_and_dependency_free() -> None:
    html = COMMAND_V2.read_text(encoding="utf-8")
    assert html.startswith("<!DOCTYPE html>")
    assert "<main" in html
    assert 'name="viewport"' in html
    assert 'aria-label="Command rooms"' in html
    assert 'role="dialog"' in html
    assert "prefers-reduced-motion" in html
    assert "forced-colors" in html
    assert "Conjecture 1" in html
    assert "The interface will not invent missing values." in html
    assert "ms.tabs||141" not in html
    assert "cdnjs" not in html and "googleapis" not in html and "jsdelivr" not in html


def test_legacy_public_spa_remains_available_as_fallback() -> None:
    html = LEGACY_SPA.read_text(encoding="utf-8")
    assert html.startswith("<!DOCTYPE html>")
    assert 'rel="canonical" href="https://a-11-oy.com/command"' in html
    assert "a11oy.net" in html
    assert "Conjecture 1" in html


def test_module_prefers_elite_and_does_not_steal_console() -> None:
    src = MOD.read_text(encoding="utf-8")
    assert "def register(app" in src
    assert 'here / "web" / "elite_console.html"' in src
    assert 'Path("/app/web/elite_console.html")' in src
    assert 'here / "pages" / "command-center.html"' in src
    assert 'here / "pages" / "command-v2.html"' in src
    assert 'Path("/app/pages/command-v2.html")' in src
    assert '"/command"' in src
    assert '"/command-v2"' in src
    assert "/command stays on elite_console.html" in src
    assert "/brain and /console untouched" in src


def test_serve_imports_and_calls_register() -> None:
    src = SERVE.read_text(encoding="utf-8")
    assert "import a11oy_command_center as _a11oy_command_center" in src
    assert '_a11oy_command_center.register(app, ns="a11oy")' in src
    assert 'for _cc_path in ("/command", "/command-center")' not in src


def test_dockerfile_copies_command_assets() -> None:
    src = DOCKER.read_text(encoding="utf-8")
    assert "a11oy_command_center.py" in src
    # Both command-center.html and command-v2.html ride the explicit pages closure.
    assert "COPY pages/ ./pages/" in src
    assert "COPY web/ ./web/" in src or "web/elite_console.html" in src


def test_module_selftest_if_starlette_present() -> None:
    try:
        import starlette  # noqa: F401
    except ImportError:
        return
    import a11oy_command_center as mod

    mod._selftest()
