# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Static wiring guards for the bound /command SPA on a-11-oy.com.

Not a landing-door rewrite. Product door stays Products / Catalog / Proof.
/console stays the operator runtime.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPA = ROOT / "pages" / "command-center.html"
MOD = ROOT / "a11oy_command_center.py"
SERVE = ROOT / "serve.py"
DOCKER = ROOT / "Dockerfile"
LANDING = ROOT / "a11oy_landing.html"


def test_command_center_spa_is_product_origin() -> None:
    html = SPA.read_text(encoding="utf-8")
    assert html.startswith("<!DOCTYPE html>")
    assert 'rel="canonical" href="https://a-11-oy.com/command"' in html
    assert "a11oy.net" in html
    assert "cdnjs" not in html and "googleapis" not in html
    assert "jsdelivr" not in html
    assert 'href="/console"' in html
    assert 'href="/command/zk"' in html
    assert 'href="/command/invest"' in html
    assert 'href="/command/build"' in html
    assert 'href="/command/census"' in html
    assert "Conjecture 1" in html
    assert "MEASURED" in html  # local circuit SAT only
    assert "Hub RUNNING" in html


def test_module_does_not_steal_console() -> None:
    src = MOD.read_text(encoding="utf-8")
    assert "def register(app" in src
    assert '"/console"' not in src or "does not steal" in src
    assert "Does not steal existing /console" in src
    assert '"/command"' in src
    assert "not a landing door" in src


def test_serve_imports_and_calls_register() -> None:
    src = SERVE.read_text(encoding="utf-8")
    assert "import a11oy_command_center as _a11oy_command_center" in src
    assert '_a11oy_command_center.register(app, ns="a11oy")' in src
    assert 'for _cc_path in ("/command", "/command-center")' not in src
    assert "command-center.html" in src


def test_dockerfile_copies_module() -> None:
    src = DOCKER.read_text(encoding="utf-8")
    assert "a11oy_command_center.py" in src
    assert "COPY pages/ ./pages/" in src


def test_landing_door_is_not_rewritten() -> None:
    html = LANDING.read_text(encoding="utf-8")
    nav = html.split('<nav class="nav-links" id="site-nav">', 1)[1].split("</nav>", 1)[0]
    assert 'aria-label="Open the command center"' in nav
    assert 'href="/console"' in nav
    assert 'href="/command"' not in nav


def test_module_selftest_if_starlette_present() -> None:
    try:
        import starlette  # noqa: F401
    except ImportError:
        return
    import a11oy_command_center as mod

    mod._selftest()
