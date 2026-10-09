"""The Article 12 source map has an exact, honest read-only page route."""

from pathlib import Path

from fastapi.testclient import TestClient

import serve


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "pages" / "eu-ai-act.html"
CLIENT = TestClient(serve.app)


def test_article_12_page_get_head_and_soft_404_boundary() -> None:
    get = CLIENT.get("/eu-ai-act")
    head = CLIENT.head("/eu-ai-act")
    assert get.status_code == head.status_code == 200
    # The product shell injects its shared flow assets into HTML responses.
    # Check the actual Article 12 content instead of assuming byte identity.
    assert "EU AI Act Article 12: a technical logging map." in get.text
    assert "2 December 2027" in get.text
    assert "The profile is a self-assessment artifact" in get.text
    assert get.headers.get("X-SZL-Route-State") != "SPA_FALLBACK"
    assert head.content == b""
    assert get.headers["content-type"].startswith("text/html")
    assert get.headers["cache-control"] == head.headers["cache-control"] == "no-store"

    undeclared = CLIENT.get("/eu-ai-act-unknown")
    assert undeclared.status_code == 404
    assert undeclared.json()["status"] == "NOT_FOUND"


def test_article_12_page_missing_asset_fails_closed(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(serve, "PAGES_DIR", tmp_path)
    response = CLIENT.get("/eu-ai-act")
    assert response.status_code == 404
    assert response.json()["status"] == "UNAVAILABLE"
    assert not response.headers["content-type"].startswith("text/html")


def test_article_12_copy_stays_within_source_evidence() -> None:
    page = PAGE.read_text(encoding="utf-8")
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY pages/ ./pages/" in dockerfile
    assert "2 December 2027" in page
    assert "2 August 2028" in page
    assert "https://eur-lex.europa.eu/eli/reg/2024/1689/2026-07-27/eng" in page
    assert "evidence/conformance/eu-ai-act-article-12.v1.yaml" in page
    assert "DECLARED" in page and "UNKNOWN" in page
    for unsupported in (
        "full application for Annex III",
        "The deadline is not upcoming. It passed.",
        "Every required audit-trail field",
        "MEASURED",
        "64 held proof-of-concept attacks",
        "€35M or 7%",
    ):
        assert unsupported not in page
