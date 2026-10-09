# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Retired product paths land on a real page, and the sitemap lists only real destinations.

On 2026-10-06 ten retired paths (/defense, /care, /boardroom, ...) redirected to /about, and
/about answered a JSON 404 because the module that was meant to serve it is not in the image.
These tests boot the real app in-process, as the demo-critical route guard does.
"""
import re
import warnings
from pathlib import Path

import pytest

warnings.filterwarnings("ignore")
pytest.importorskip("starlette.testclient")

from starlette.testclient import TestClient  # noqa: E402

import serve  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RETIRED = (
    "/defense", "/weaponized-intel", "/atlas-shield", "/swarm-orchestrator", "/playbook-engine",
    "/karpathy-evolution", "/trust-exchange", "/care", "/boardroom", "/a11oy-code",
)
BROWSER = {"Accept": "text/html,application/xhtml+xml"}


@pytest.fixture(scope="module")
def client():
    return TestClient(serve.app, raise_server_exceptions=False)


def test_about_lands_on_the_company_page(client):
    first = client.get("/about", headers=BROWSER, follow_redirects=False)
    assert first.status_code == 307
    assert first.headers["location"] == "/company"
    page = client.get("/about", headers=BROWSER)
    assert page.status_code == 200
    assert page.headers["content-type"].startswith("text/html")


@pytest.mark.parametrize("path", RETIRED)
def test_retired_paths_reach_a_real_html_page(client, path):
    response = client.get(path, headers=BROWSER)
    assert response.status_code == 200, path
    assert response.headers["content-type"].startswith("text/html"), path


def test_sitemap_lists_registered_pages_and_no_redirects(client):
    # Many page handlers read image paths such as /app/pages, so a source checkout cannot
    # render every page. What holds everywhere: each URL is a registered route, not a redirect.
    sitemap = (ROOT / "console" / "sitemap.xml").read_text(encoding="utf-8")
    paths = re.findall(r"<loc>https://a-11-oy\.com(/[^<]*)</loc>", sitemap)
    assert len(paths) == len(set(paths))
    registered = {getattr(route, "path", None) for route in serve.app.router.routes}
    for path in paths:
        assert path in registered, f"{path} has no route"
        response = client.get(path, headers=BROWSER, follow_redirects=False)
        assert response.status_code not in {301, 302, 303, 307, 308}, f"{path} redirects"
