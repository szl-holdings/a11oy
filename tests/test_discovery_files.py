# SPDX-License-Identifier: Apache-2.0
"""Contracts for crawler and security discovery files served outside the SPA."""
from pathlib import Path
import struct


ROOT = Path(__file__).resolve().parents[1]


def test_robots_and_sitemap_are_real_machine_readable_files() -> None:
    robots = (ROOT / "console" / "robots.txt").read_text(encoding="utf-8")
    sitemap = (ROOT / "console" / "sitemap.xml").read_text(encoding="utf-8")

    assert "User-agent: *" in robots
    assert "Sitemap: https://a-11-oy.com/sitemap.xml" in robots
    assert sitemap.startswith('<?xml version="1.0" encoding="UTF-8"?>')
    assert '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' in sitemap
    for path in (
        "/ecosystem", "/anatomy-v5", "/models", "/kernels",
        "/ecosystem/brain", "/ecosystem/anatomy", "/ecosystem/holographic", "/spaces",
    ):
        assert f"<loc>https://a-11-oy.com{path}</loc>" in sitemap
    assert "<!doctype html>" not in robots.lower()
    assert "<!doctype html>" not in sitemap.lower()


def test_security_txt_is_canonical_and_copied_into_runtime_static_tree() -> None:
    security = (ROOT / ".well-known" / "security.txt").read_text(encoding="utf-8")
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "Contact: mailto:security@szlholdings.ai" in security
    assert "Encryption:" not in security, "do not advertise a nonexistent public key"
    assert "Canonical: https://a-11-oy.com/.well-known/security.txt" in security
    assert "Policy: https://github.com/szl-holdings/a11oy/blob/main/SECURITY.md" in security
    assert (
        "COPY .well-known/security.txt ./static/.well-known/security.txt" in dockerfile
    )


def test_social_preview_is_honest_discoverable_and_exact_size() -> None:
    landing = (ROOT / "a11oy_landing.html").read_text(encoding="utf-8")
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    svg = (ROOT / "console" / "social-preview-v5.svg").read_text(encoding="utf-8")
    png = (ROOT / "console" / "social-preview-v5.png").read_bytes()

    assert 'width="1280" height="640" viewBox="0 0 1280 640"' in svg
    assert "Evidence in. Receipts out." in svg
    assert "https://a-11-oy.com/social-preview-v5.png" in landing
    assert 'property="og:image:width" content="1280"' in landing
    assert 'property="og:image:height" content="640"' in landing
    assert '<link rel="icon" type="image/svg+xml" href="/social-preview-v5.svg"' in landing
    assert "COPY console/ ./static/" in dockerfile

    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert png[12:16] == b"IHDR"
    assert struct.unpack(">II", png[16:24]) == (1280, 640)
