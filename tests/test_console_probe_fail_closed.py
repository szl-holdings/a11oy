"""Probe failure must not paint UP/LIVE.

HTTP errors and catch blocks are UNAVAILABLE. They are not a green fleet.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONSOLES = (
    ROOT / "console" / "index.html",
    ROOT / "pages" / "console.html",
    ROOT / "pages_console.html",
)


def test_probe_catch_does_not_paint_up() -> None:
    for path in CONSOLES:
        text = path.read_text(encoding="utf-8")
        assert 'badge b-live">UP' not in text, path
        assert "b-err\">UNAVAILABLE" in text, path


def _catch_of(text: str, fn: str) -> str:
    start = text.index(f"async function {fn}(")
    body = text[start:]
    catch = body.split("}catch(e){", 1)[1]
    return catch.split("}}", 1)[0]


def test_mesh_and_org_catch_paint_unavailable_not_green_ok() -> None:
    for path in CONSOLES:
        text = path.read_text(encoding="utf-8")
        assert "status:'ok',latency_ms:0,http_code:200" not in text, path
        mesh = _catch_of(text, "mesh_load")
        org = _catch_of(text, "organism_load")
        for block in (mesh, org):
            assert 'badge b-live">ok' not in block, path
            assert "b-err\">UNAVAILABLE" in block, path
