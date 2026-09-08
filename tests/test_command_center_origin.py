# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Wiring and quarantine guards for the bound /command surface.

/command serves the reviewed public Command Center. The dormant Elite Console
must not enter candidate resolution or the runtime image until its independent
browser-safety, API-schema, and evidence contracts are release-ready.
/command-v2 remains additive; /console and host-root /brain retain their owners.
"""
import fnmatch
import json
import posixpath
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEGACY_SPA = ROOT / "pages" / "command-center.html"
ELITE_SPA = ROOT / "web" / "elite_console.html"
V2_PAGE = ROOT / "pages" / "command-v2.html"
MOD = ROOT / "a11oy_command_center.py"
SERVE = ROOT / "serve.py"
DOCKER = ROOT / "Dockerfile"
FLOW_ROLLOUT = ROOT / "scripts" / "rollout_frontend_flow_shell.py"
FLOW_STATE = ROOT / "docs" / "frontend-flow-shell-state.json"


def _docker_image_sources(dockerfile: Path) -> set[str]:
    parser = runpy.run_path(str(ROOT / "tests" / "test_dockerfile_layer_budget.py"))
    parser["_logical_instructions"].__globals__["DOCKERFILE"] = dockerfile
    return {
        source.replace("\\", "/")
        for _line, instruction in parser["_logical_instructions"]()
        if instruction.upper().startswith(("COPY ", "ADD "))
        for source in parser["_copy_sources"](instruction)
    }


def _source_can_include(source: str, target: str) -> bool:
    candidate = source.replace("\\", "/")
    while candidate.startswith("./"):
        candidate = candidate[2:]
    candidate = candidate.lstrip("/")
    normalized = posixpath.normpath(candidate or ".")
    if normalized == "." or normalized == ".." or normalized.startswith("../"):
        return True
    if any(marker in normalized for marker in "*?["):
        return fnmatch.fnmatchcase(target, normalized)
    normalized = normalized.rstrip("/")
    return target == normalized or target.startswith(normalized + "/")


def test_dormant_elite_asset_is_not_a_command_candidate() -> None:
    assert ELITE_SPA.is_file(), "quarantined source remains auditable in the repository"
    src = MOD.read_text(encoding="utf-8")
    assert 'here / "web" / "elite_console.html"' not in src
    assert 'Path("/app/web/elite_console.html")' not in src
    assert "dormant elite excluded" in src


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


def test_v2_owns_one_reviewed_nonduplicative_navigation_shell() -> None:
    html = V2_PAGE.read_text(encoding="utf-8")
    rollout = FLOW_ROLLOUT.read_text(encoding="utf-8")
    state = json.loads(FLOW_STATE.read_text(encoding="utf-8"))

    assert 'SELF_CONTAINED_PATHS = {"pages/command-v2.html", "pages/wires.html"}' in rollout
    assert "pages/command-v2.html" in state["self_contained_documents"]
    assert "pages/command-v2.html" not in state["injected_documents"]
    assert 'data-szl-flow-asset="style"' not in html
    assert 'data-szl-flow-asset="script"' not in html
    for marker in (
        'aria-label="Command rooms"',
        'aria-label="Mobile command rooms"',
        'aria-modal="true"',
        "palette",
    ):
        assert marker in html


def test_reviewed_public_spa_is_the_canonical_command_source() -> None:
    html = LEGACY_SPA.read_text(encoding="utf-8")
    assert html.startswith("<!DOCTYPE html>")
    assert 'rel="canonical" href="https://a-11-oy.com/command"' in html
    assert "a11oy.net" in html
    assert "Conjecture 1" in html


def test_module_uses_reviewed_spa_and_does_not_steal_console() -> None:
    src = MOD.read_text(encoding="utf-8")
    assert "def register(app" in src
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
    assert 'REQUIRED_PAGES = {"command-v2.html"}' in src
    assert '"status": "UNAVAILABLE" if required else "NOT_FOUND"' in src
    assert "status_code=503 if required else 404" in src
    assert "does not steal /console" in src


def test_serve_imports_and_calls_register() -> None:
    src = SERVE.read_text(encoding="utf-8")
    assert src.count("import a11oy_command_center as _a11oy_command_center") == 1
    assert src.count('_a11oy_command_center.register(app, ns="a11oy")') == 1
    assert 'for _cc_path in ("/command", "/command-center")' not in src


def test_dockerfile_copies_command_and_quarantines_elite_asset() -> None:
    src = DOCKER.read_text(encoding="utf-8")
    assert "a11oy_command_center.py" in src
    assert "COPY pages/ ./pages/" in src
    sources = _docker_image_sources(DOCKER)
    elite = "web/elite_console.html"
    assert not any(_source_can_include(source, elite) for source in sources)


def test_elite_quarantine_detects_broad_and_wildcard_copy_sources(tmp_path: Path) -> None:
    elite = "web/elite_console.html"
    unsafe_instructions = (
        "COPY . /app",
        "COPY ./ /app",
        "COPY web/ /app/web/",
        "COPY /web/ /app/web/",
        "COPY / /app",
        "COPY web/*.html /app/web/",
        'COPY ["./web/../", "/app/"]',
        "ADD . /app",
    )
    for index, instruction in enumerate(unsafe_instructions):
        dockerfile = tmp_path / f"Dockerfile.{index}"
        dockerfile.write_text(f"FROM scratch AS runtime\n{instruction}\n", encoding="utf-8")
        sources = _docker_image_sources(dockerfile)
        assert any(_source_can_include(source, elite) for source in sources), instruction


def test_module_selftest_if_starlette_present() -> None:
    try:
        import starlette  # noqa: F401
    except ImportError:
        return
    import a11oy_command_center as module

    module._selftest()


def test_dormant_elite_route_fails_closed_if_backend_is_registered() -> None:
    try:
        from fastapi import FastAPI
        from starlette.testclient import TestClient
    except ImportError:
        return
    import szl_elite_console

    app = FastAPI()
    szl_elite_console.register(app, [], {})
    response = TestClient(app).get("/elite-console")

    assert response.status_code == 503
    assert response.headers["cache-control"] == "no-store"
    assert "Elite Console: UNAVAILABLE" in response.text
    assert 'href="/command"' in response.text
    assert "20-tab" not in response.text
