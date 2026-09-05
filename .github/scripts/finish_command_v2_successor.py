#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Materialize the reviewed Command Centre v2 onto current protected-main source."""
from __future__ import annotations

import subprocess
from pathlib import Path

OLD_SOURCE_SHA = "1eb42aa27ba0f26f6ec9db7618398283834ca1cd"


def replace_once(text: str, old: str, new: str, *, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one replacement target, found {count}")
    return text.replace(old, new, 1)


def git_show(path: str) -> str:
    return subprocess.check_output(
        ["git", "show", f"{OLD_SOURCE_SHA}:{path}"],
        text=True,
        encoding="utf-8",
    )


def materialize_command_module() -> None:
    path = Path("a11oy_command_center.py")
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "  GET+HEAD /command\n  GET+HEAD /command/constellation\n",
        "  GET+HEAD /command\n  GET+HEAD /command-v2\n  GET+HEAD /command/constellation\n",
        label="command-v2 route documentation",
    )
    text = replace_once(
        text,
        "Host-root /brain is Hickok dual-stream. Do not steal it.\n\"\"\"",
        "Host-root /brain is Hickok dual-stream. Do not steal it.\n"
        "/command stays on elite_console.html until an explicit flag flips it.\n\"\"\"",
        label="command-v2 promotion boundary",
    )
    text = replace_once(
        text,
        'MOUNTS = ("/command",)\nSPECIFIC = (\n',
        'MOUNTS = ("/command",)\nV2_MOUNTS = ("/command-v2",)\nSPECIFIC = (\n',
        label="command-v2 route constant",
    )
    text = replace_once(
        text,
        '    return here / "web" / "elite_console.html"\n\n\ndef _page(name: str) -> Path:\n',
        '    return here / "web" / "elite_console.html"\n\n\n'
        'def _v2_path() -> Path:\n'
        '    here = Path(__file__).resolve().parent\n'
        '    candidates = (\n'
        '        here / "web" / "command_v2.html",\n'
        '        Path("/app/web/command_v2.html"),\n'
        '    )\n'
        '    for cand in candidates:\n'
        '        if cand.is_file():\n'
        '            return cand\n'
        '    return here / "web" / "command_v2.html"\n\n\n'
        'def _page(name: str) -> Path:\n',
        label="command-v2 path resolver",
    )
    text = replace_once(
        text,
        '    async def _spa(_request=None, rest: str = ""):\n'
        '        del rest\n'
        '        return FileResponse(spa, media_type="text/html; charset=utf-8")\n\n'
        '    def _file(name: str):\n',
        '    async def _spa(_request=None, rest: str = ""):\n'
        '        del rest\n'
        '        return FileResponse(spa, media_type="text/html; charset=utf-8")\n\n'
        '    async def _v2(_request=None):\n'
        '        page = _v2_path()\n'
        '        if page.is_file():\n'
        '            return FileResponse(page, media_type="text/html; charset=utf-8")\n'
        '        return JSONResponse(\n'
        '            {\n'
        '                "status": "UNAVAILABLE",\n'
        '                "reason": "command_v2.html missing from image",\n'
        '                "page": "web/command_v2.html",\n'
        '            },\n'
        '            status_code=503,\n'
        '        )\n\n'
        '    def _file(name: str):\n',
        label="command-v2 handler",
    )
    text = replace_once(
        text,
        "    _drop_paths(app, specific_paths)\n",
        "    _drop_paths(app, specific_paths | set(V2_MOUNTS))\n",
        label="command-v2 route replacement",
    )
    text = replace_once(
        text,
        '    for path in MOUNTS:\n'
        '        _add(path, _spa, ["GET", "HEAD"])\n'
        '    for path, name in SPECIFIC:\n',
        '    for path in MOUNTS:\n'
        '        _add(path, _spa, ["GET", "HEAD"])\n'
        '    for path in V2_MOUNTS:\n'
        '        _add(path, _v2, ["GET", "HEAD"])\n'
        '    for path, name in SPECIFIC:\n',
        label="command-v2 registration",
    )
    text = replace_once(
        text,
        '    _front_move(app, [path for path, _name in SPECIFIC] + list(MOUNTS))\n'
        '    registered.append("command-center on /command (constellation/brain/ops beat catch-all; /brain and /operator host-root untouched)")\n',
        '    _front_move(\n'
        '        app,\n'
        '        list(V2_MOUNTS) + [path for path, _name in SPECIFIC] + list(MOUNTS),\n'
        '    )\n'
        '    registered.append(\n'
        '        "command-center on /command; /command-v2 additive; "\n'
        '        "constellation/brain/ops beat catch-all; "\n'
        '        "/brain and /operator host-root untouched"\n'
        '    )\n',
        label="command-v2 route ordering",
    )
    text = replace_once(
        text,
        '    assert any("/command" in row for row in out), out\n'
        '    c = TestClient(app)\n',
        '    assert any("/command" in row for row in out), out\n'
        '    assert any("/command-v2" in row for row in out), out\n'
        '    c = TestClient(app)\n',
        label="command-v2 registration self-test",
    )
    text = replace_once(
        text,
        '    for path in ("/command", "/command/anatomy", "/command/honest"):\n'
        '        r = c.get(path)\n'
        '        assert r.status_code == 200, (path, r.status_code)\n'
        '    if _page("constellation.html").is_file():\n',
        '    for path in ("/command", "/command/anatomy", "/command/honest"):\n'
        '        r = c.get(path)\n'
        '        assert r.status_code == 200, (path, r.status_code)\n'
        '    v2 = c.get("/command-v2")\n'
        '    assert v2.status_code == 200, ("/command-v2", v2.status_code)\n'
        '    assert "a11oy" in v2.text.lower() and "Command" in v2.text\n'
        '    assert "cdnjs" not in v2.text and "googleapis" not in v2.text\n'
        '    if _page("constellation.html").is_file():\n',
        label="command-v2 route self-test",
    )
    text = replace_once(
        text,
        '    print("a11oy_command_center: ALL OK (constellation beats catch-all; /brain host-root untouched)")\n',
        '    print(\n'
        '        "a11oy_command_center: ALL OK "\n'
        '        "(v2 additive; constellation/ops beat catch-all; "\n'
        '        "/brain host-root untouched)"\n'
        '    )\n',
        label="command-v2 self-test receipt",
    )
    path.write_text(text, encoding="utf-8")


def materialize_html() -> None:
    path = Path("web/command_v2.html")
    path.parent.mkdir(parents=True, exist_ok=True)
    html = git_show("web/command_v2.html")
    accessibility = """
button,.btn,.room,.hit,input{min-height:44px}
button:focus-visible,a:focus-visible,input:focus-visible{outline:2px solid var(--ink);outline-offset:2px}
html,body{max-width:100%;overflow-x:hidden}
@media (prefers-reduced-motion:reduce){*{scroll-behavior:auto!important;animation-duration:.001ms!important;transition-duration:.001ms!important}}
@media (forced-colors:active){*{forced-color-adjust:auto}.card,.btn,.chip,.kbtn{border:1px solid CanvasText}}
"""
    html = replace_once(
        html,
        "</style>",
        accessibility + "</style>",
        label="command-v2 accessibility CSS",
    )
    html = replace_once(
        html,
        '<div class="palette" id="palette" role="dialog"><div class="pal"><input id="q" placeholder="Open a room or tab…" autocomplete="off" />',
        '<div class="palette" id="palette" role="dialog" aria-modal="true" aria-label="Command palette"><div class="pal"><input id="q" aria-label="Open a room or tab" placeholder="Open a room or tab…" autocomplete="off" />',
        label="command-v2 palette accessibility",
    )
    path.write_text(html, encoding="utf-8")


def materialize_container_contract() -> None:
    path = Path("Dockerfile")
    text = path.read_text(encoding="utf-8")
    marker = "COPY pages/ ./pages/\n"
    addition = (
        marker
        + "# Additive Command Centre v2 candidate; /command remains on the elite skin.\n"
        + "COPY web/command_v2.html ./web/command_v2.html\n"
    )
    text = replace_once(text, marker, addition, label="Command v2 Docker COPY")
    path.write_text(text, encoding="utf-8")


def materialize_docs_and_tests() -> None:
    docs = Path("docs/audits/COMMAND_V2_SHIP_PATH.md")
    docs.parent.mkdir(parents=True, exist_ok=True)
    docs.write_text(
        """# Command Centre v2 ship path

Product origin: `https://a-11-oy.com`

The surface is additive at `/command-v2`. `/command` and `/console` remain unchanged.

## Source and image contract

- `web/command_v2.html` is committed source.
- `a11oy_command_center.py` registers GET and HEAD before the `/command/{rest:path}` catch-all.
- `Dockerfile` copies the exact HTML into `/app/web/command_v2.html`.
- A missing file returns an honest HTTP 503 `UNAVAILABLE`; it is never represented as a successful HTML surface.
- The candidate reads existing same-origin A11oy and Hatun evidence routes and grants no execution authority.

## Accessibility boundary

The page preserves 44-pixel controls, visible keyboard focus, responsive two-column and one-column collapse, reduced-motion handling, forced-colors handling, and zero third-party CDN dependencies.

## Promotion boundary

Do not move this candidate onto `/command` without a separate reviewed release decision and live exact-source verification.
""",
        encoding="utf-8",
    )

    tests = Path("tests/test_command_v2_shipping.py")
    tests.write_text(
        '''# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import ast
from pathlib import Path

COMMAND = Path("a11oy_command_center.py")
DOCKER = Path("Dockerfile")
HTML = Path("web/command_v2.html")


def test_command_v2_is_registered_before_the_command_catchall() -> None:
    source = COMMAND.read_text(encoding="utf-8")
    ast.parse(source)
    assert 'V2_MOUNTS = ("/command-v2",)' in source
    assert 'for path in V2_MOUNTS:' in source
    assert 'list(V2_MOUNTS) + [path for path, _name in SPECIFIC]' in source
    assert 'status_code=503' in source
    assert source.index('V2_MOUNTS = ("/command-v2",)') < source.index('CATCHALL = "/command/{rest:path}"')


def test_command_v2_exact_source_is_in_the_runtime_image() -> None:
    docker = DOCKER.read_text(encoding="utf-8")
    assert docker.count("COPY web/command_v2.html ./web/command_v2.html") == 1
    assert docker.index("COPY web/command_v2.html ./web/command_v2.html") < docker.index("COPY serve.py ./")


def test_command_v2_surface_is_mobile_keyboard_and_truth_safe() -> None:
    html = HTML.read_text(encoding="utf-8")
    for room in (
        'id:"command"',
        'id:"evidence"',
        'id:"governance"',
        'id:"telemetry"',
        'id:"defense"',
        'id:"markets"',
        'id:"models"',
        'id:"diligence"',
    ):
        assert room in html
    for contract in (
        "viewport-fit=cover",
        "min-height:44px",
        "focus-visible",
        "prefers-reduced-motion:reduce",
        "forced-colors:active",
        'aria-modal="true"',
        "Conjecture 1",
        "SAMPLE",
        "UNAVAILABLE",
    ):
        assert contract in html
    for external in ("cdnjs", "googleapis", "jsdelivr", "unpkg.com"):
        assert external not in html
''',
        encoding="utf-8",
    )


def main() -> int:
    subprocess.run(
        ["git", "fetch", "--no-tags", "--depth=1", "origin", OLD_SOURCE_SHA],
        check=True,
    )
    materialize_command_module()
    materialize_html()
    materialize_container_contract()
    materialize_docs_and_tests()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
