#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Every same-origin subresource of the rendered homepage is an installed file.

The homepage stylesheet returned 404 on every origin while every source-tree
test passed: the exact front-door route read ``console/assets/...``, which the
image never ships (``COPY console/ ./static/``), and it shadowed the /assets
mount that would have served the file. Source-tree tests cannot see that class
of defect, so this suite projects the runtime /app tree from the Dockerfile
COPY set and .dockerignore, boots the real serve.py inside that tree, renders
``/``, and requires each subresource the browser would fetch to come back as
the bytes of the installed file at that URL.
"""
import base64
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests import image_layout as L

ROOT = Path(__file__).resolve().parents[1]
HELPER = Path(L.__file__).resolve()
HOMEPAGE_CSS = "static/assets/a11oy-homepage.css"
MARKER = "@@IMAGE-LAYOUT-REPORT@@"
_CHILD = (
    "import importlib.util, sys\n"
    "spec = importlib.util.spec_from_file_location('_szl_image_layout_probe', sys.argv[1])\n"
    "module = importlib.util.module_from_spec(spec)\n"
    "spec.loader.exec_module(module)\n"
    "module.child_main(sys.argv[2:])\n"
)


# -- projection of the image tree ------------------------------------------

def test_image_installs_console_at_static_and_ships_no_console_tree():
    layout = L.installed_layout(ROOT)
    assert layout[HOMEPAGE_CSS] == "console/assets/a11oy-homepage.css"
    assert layout["static/index.html"] == "console/index.html"
    assert layout["a11oy_landing.html"] == "a11oy_landing.html"
    assert layout["serve.py"] == "serve.py"
    # The defect: a handler resolving <module dir>/console/... finds nothing.
    assert not [path for path in layout if path.startswith("console/")]
    # Build-only inputs and ignored paths never enter /app.
    assert not [path for path in layout if path.startswith("tests/")]
    assert "scripts/fetch_owned_khipu_wheel.py" not in layout


def test_runtime_copy_parser_fails_closed_on_unmodelled_forms():
    head = "FROM python:3 AS builder\nCOPY a /b\nFROM python:3 AS runtime\nWORKDIR /app\n"
    assert L.runtime_copies(head + "COPY x.py y.py ./\n") == [(["x.py", "y.py"], "/app/")]
    for tail in ("ADD x.py ./\n", "COPY --from=builder /b ./\n", "COPY static/*.js ./static/\n",
                 'COPY ["x.py", "./"]\n', "COPY x.py y.py ./dest\n"):
        with pytest.raises(L.LayoutError):
            L.runtime_copies(head + tail)
    with pytest.raises(L.LayoutError):
        L.runtime_copies("FROM python:3 AS runtime\nCOPY x.py ./\n")


def test_dockerignore_patterns_are_root_anchored_like_docker():
    ignored = L.dockerignore_matcher("test\n**/node_modules\n*.log\ndata/*.db\nkhipu/**/*.ndjson\n")
    assert ignored("test/case.py")
    assert not ignored("pkg/test/case.py")
    assert ignored("pkg/node_modules/x.js")
    assert ignored("root.log") and not ignored("logs/inner.log")
    assert ignored("data/store.db") and not ignored("data/genome.json")
    assert ignored("khipu/a/b/c.ndjson")
    with pytest.raises(L.LayoutError):
        L.dockerignore_matcher("!keep.txt\n")


# -- what the browser fetches ----------------------------------------------

def test_subresource_extraction_covers_fetches_and_skips_navigation():
    html = (
        '<link rel="icon" href="/i.svg"><link rel="canonical" href="https://a-11-oy.com/">'
        '<link rel="stylesheet" href="https://a-11-oy.com/a.css?v=1">'
        '<script src="/s.js"></script><img src="/m.svg" srcset="/m1.svg 1x, /m2.svg 2x">'
        '<a href="/page">nav</a><script>f.src = "/static/x.html"; g.src = "https://example.invalid/y";</script>'
        '<meta property="og:image" content="https://a-11-oy.com/og.png">'
    )
    assert L.subresource_paths(html) == ["/a.css?v=1", "/i.svg", "/m.svg", "/m1.svg", "/m2.svg",
                                         "/og.png", "/s.js", "/static/x.html"]
    with pytest.raises(L.LayoutError):
        L.subresource_paths('<script src="relative.js"></script>')


def test_verdict_rejects_fallbacks_wrong_types_and_foreign_bytes(tmp_path):
    (tmp_path / "static" / "assets").mkdir(parents=True)
    css = b"html{color:red}\n"
    page = b"<html>\n<body>\n<p>x</p>\n</body>\n</html>\n"
    index = b"<!doctype html><div id=root></div>\n"
    (tmp_path / HOMEPAGE_CSS).write_bytes(css)
    (tmp_path / "static" / "page.html").write_bytes(page)
    (tmp_path / "static" / "index.html").write_bytes(index)
    layout = {path: path for path in (HOMEPAGE_CSS, "static/page.html", "static/index.html")}
    url = "/assets/a11oy-homepage.css?v=1"
    assert L.asset_verdict(url, 200, "text/css; charset=utf-8", css, layout, tmp_path) is None
    assert L.asset_verdict(url, 404, "application/json", b"{}", layout, tmp_path) == "HTTP 404"
    assert "content-type" in L.asset_verdict(url, 200, "text/html", index, layout, tmp_path)
    assert "not the installed bytes" in L.asset_verdict(url, 200, "text/css", b"x", layout, tmp_path)
    assert "COPY set" in L.asset_verdict("/assets/gone.css", 200, "text/css", css, layout, tmp_path)
    # A missing document answered by the SPA shell is not the requested file.
    assert L.asset_verdict("/static/other.html", 200, "text/html", index, layout, tmp_path)
    injected = page.replace(b"</body>", b"<script src=/w.js></script></body>")
    assert L.asset_verdict("/static/page.html", 200, "text/html", injected, layout, tmp_path) is None
    altered = page.replace(b"<p>x</p>", b"<p>y</p>")
    assert L.asset_verdict("/static/page.html", 200, "text/html", altered, layout, tmp_path)


# -- the real app inside the projected image ---------------------------------

@pytest.fixture(scope="module")
def image_report(tmp_path_factory):
    pytest.importorskip("fastapi")
    pytest.importorskip("starlette.testclient")
    layout = L.installed_layout(ROOT)
    image_root = L.materialize(ROOT, layout, tmp_path_factory.mktemp("a11oy-image") / "app")
    env = {key: value for key, value in os.environ.items() if not key.startswith("PYTHON")}
    completed = subprocess.run(
        [sys.executable, "-B", "-E", "-s", "-c", _CHILD, str(HELPER),
         str(image_root / HOMEPAGE_CSS)],
        cwd=image_root, env=env, capture_output=True, timeout=900,
    )
    stdout = completed.stdout.decode("utf-8", "replace")
    lines = [line for line in stdout.splitlines() if line.startswith(MARKER)]
    assert completed.returncode == 0 and len(lines) == 1, (
        "serve.py did not boot from the projected image tree:\n"
        + completed.stderr.decode("utf-8", "replace")[-4000:])
    return image_root, layout, json.loads(lines[0][len(MARKER):])


def _body(probe):
    return base64.b64decode(probe["body"])


def test_projected_image_resolves_its_own_static_root(image_report):
    image_root, _, report = image_report
    assert Path(report["static_dir"]).resolve() == (image_root / "static").resolve()


def test_front_door_is_the_installed_landing(image_report):
    _, _, report = image_report
    door = report["front_door"]
    assert L.asset_verdict("/a11oy_landing.html", door["status"], door["content_type"],
                           _body(door), {"a11oy_landing.html": "a11oy_landing.html"}, ROOT) is None


def test_every_homepage_subresource_is_served_from_the_image_copy_set(image_report):
    _, layout, report = image_report
    seen = report["subresources"]
    stylesheets = [path for path in seen if path.split("?", 1)[0].endswith(".css")]
    assert len(stylesheets) >= 5, seen
    assert any(path.startswith("/assets/a11oy-homepage.css") for path in seen), seen
    failures = {}
    for path in seen:
        probe = report["assets"][path]
        reason = L.asset_verdict(path, probe["status"], probe["content_type"], _body(probe),
                                 layout, ROOT)
        if reason:
            failures[path] = reason
    assert failures == {}


def test_guard_detects_a_referenced_file_missing_from_the_image(image_report):
    # The child deleted the installed stylesheet; the source checkout still has
    # console/assets/a11oy-homepage.css, exactly the pre-fix blind spot.
    _, layout, report = image_report
    assert (ROOT / "console/assets/a11oy-homepage.css").is_file()
    failed = set()
    for path, probe in report["after_removal"].items():
        if L.asset_verdict(path, probe["status"], probe["content_type"], _body(probe),
                           layout, ROOT):
            failed.add(path)
    assert failed == {path for path in report["subresources"]
                      if path.startswith("/assets/a11oy-homepage.css")}
