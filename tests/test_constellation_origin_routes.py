#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Constellation and Second Brain must beat the /command SPA catch-all."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from a11oy_command_center import register  # noqa: E402


def test_specific_command_tabs_precede_catchall():
    from starlette.applications import Starlette
    from starlette.responses import HTMLResponse
    from starlette.routing import Route
    from starlette.testclient import TestClient

    async def _hickok(_req):
        return HTMLResponse("<html><body>Hickok Dual-Stream</body></html>")

    app = Starlette(routes=[Route("/brain", _hickok)])
    register(app, ns="a11oy")
    paths = [getattr(r, "path", None) for r in app.router.routes]
    catch = paths.index("/command/{rest:path}")
    assert paths.index("/command/constellation") < catch
    assert paths.index("/command/brain") < catch
    assert paths.index("/constellation") < catch
    assert paths.index("/second-brain") < catch
    client = TestClient(app)
    assert "Hickok" in client.get("/brain").text
    page = ROOT / "pages" / "constellation.html"
    if page.is_file():
        body = client.get("/constellation").text
        assert "Constellation" in body
        assert "governed-receipt-verifier" in body
