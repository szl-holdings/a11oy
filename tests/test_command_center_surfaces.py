"""Declared Command Center surfaces: /run, /eval, /eval-arena, /estate.

Origin previously refused undeclared GET /run and GET /eval with
{"status":"NOT_FOUND","reason":"undeclared path refused SPA fallback"}.
This guard keeps the pages in-tree (0 CDN) and the exact routes wired
through szl_hub.register, the same registrar that already serves /atelier.
"""
from __future__ import annotations

import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
PAGES = ROOT / "pages"

REQUIRED_PAGES = {
    "run.html": ("Governed inference theater", "Conjecture 1", "HASH-LINKED", "Deny by default"),
    "eval.html": ("Eval arena", "POST /api/a11oy/v1/eval/run", "Conjecture 1", "undeclared path"),
    "estate.html": ("Models and kernels", "Conjecture 1"),
    "atelier.html": ("Atelier",),
    "hub.html": ("/run", "/eval"),
}

CDN_HOSTS = (
    "cdn.jsdelivr.net",
    "unpkg.com",
    "cdnjs.cloudflare.com",
    "fonts.googleapis.com",
    "fonts.gstatic.com",
)


def test_origin_pages_exist_and_stay_honest():
    for name, needles in REQUIRED_PAGES.items():
        path = PAGES / name
        assert path.is_file(), f"missing declared page {name}"
        text = path.read_text(encoding="utf-8", errors="replace")
        assert "SPDX-License-Identifier: Apache-2.0" in text or "Apache-2.0" in text
        low = text.lower()
        for host in CDN_HOSTS:
            assert host not in low, f"{name} loads runtime CDN {host}"
        assert not re.search(r'<script\b[^>]*\bsrc\s*=\s*["\']https?://', text, re.I)
        for needle in needles:
            assert needle in text, f"{name} missing honest copy {needle!r}"


def test_run_page_hard_denies_lambda_as_theorem():
    text = (PAGES / "run.html").read_text(encoding="utf-8")
    assert "a11oy-lambda" in text
    assert "Never painted green" in text
    assert "LOCKED-8" in text or "locked-8" in text.lower() or "F1" in text


def test_szl_hub_declares_command_center_routes():
    src = (ROOT / "szl_hub.py").read_text(encoding="utf-8")
    for route in ('("/run", "run")', '("/eval", "eval")', '("/eval-arena", "eval")', '("/estate", "estate")'):
        assert route in src, f"szl_hub.py must declare {route}"
    for tab in ('"/run"', '"/eval"', '"/estate"'):
        assert tab in src


def test_assembled_app_registers_exact_command_center_paths():
    pytest.importorskip("starlette.testclient")
    import serve  # noqa: WPS433 — same pattern as tests/test_demo_critical_routes.py

    paths = {getattr(route, "path", None) for route in serve.app.router.routes}
    missing = [p for p in ("/run", "/eval", "/eval-arena", "/estate", "/atelier", "/hub") if p not in paths]
    assert not missing, f"command-center paths missing from assembled table: {missing}"
