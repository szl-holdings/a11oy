from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_mobile_band_wrap_keeps_inline_padding():
    text = (ROOT / "a11oy_landing.html").read_text(encoding="utf-8")
    assert "section.band{padding-block:64px}" in text
    assert "section.band{padding:64px 0}" not in text
    assert ".wrap{padding-inline:16px}" in text


def test_build_info_head_is_fail_closed_and_source_bound():
    text = (ROOT / "szl_brain_capabilities.py").read_text(encoding="utf-8")
    assert '@app.head("/api/build-info"' in text
    assert 'os.environ.get("SZL_GIT_SHA")' in text
    assert 'os.environ.get("A11OY_GIT_SHA")' in text
    assert 'status_code=200 if source_bound else 503' in text
    assert 'def _build_info_head():\n        return Response(status_code=200' not in text
