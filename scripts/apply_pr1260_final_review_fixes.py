#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

LANDING = Path("a11oy_landing.html")
BRAIN = Path("szl_brain_capabilities.py")
TEST = Path("tests/test_pr1260_final_review_contracts.py")

OLD_MOBILE = "    section.band{padding:64px 0}\n"
NEW_MOBILE = "    section.band{padding-block:64px}\n"

OLD_HEAD = '''    @app.head("/api/build-info", include_in_schema=False)\n    def _build_info_head():\n        return Response(status_code=200, headers={"Cache-Control": "no-store"})\n'''
NEW_HEAD = '''    @app.head("/api/build-info", include_in_schema=False)\n    def _build_info_head():\n        import os\n        import re\n\n        revision = (\n            os.environ.get("SZL_GIT_SHA")\n            or os.environ.get("A11OY_GIT_SHA")\n            or ""\n        ).strip().lower()\n        source_bound = bool(re.fullmatch(r"[0-9a-f]{40}", revision))\n        return Response(\n            status_code=200 if source_bound else 503,\n            headers={"Cache-Control": "no-store"},\n        )\n'''

TEST_CONTENT = '''from __future__ import annotations\n\nfrom pathlib import Path\n\nROOT = Path(__file__).resolve().parents[1]\n\n\ndef test_mobile_band_wrap_keeps_inline_padding():\n    text = (ROOT / "a11oy_landing.html").read_text(encoding="utf-8")\n    assert "section.band{padding-block:64px}" in text\n    assert "section.band{padding:64px 0}" not in text\n    assert ".wrap{padding-inline:16px}" in text\n\n\ndef test_build_info_head_is_fail_closed_and_source_bound():\n    text = (ROOT / "szl_brain_capabilities.py").read_text(encoding="utf-8")\n    assert '@app.head("/api/build-info"' in text\n    assert 'os.environ.get("SZL_GIT_SHA")' in text\n    assert 'os.environ.get("A11OY_GIT_SHA")' in text\n    assert 'status_code=200 if source_bound else 503' in text\n    assert 'def _build_info_head():\\n        return Response(status_code=200' not in text\n'''


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        if text.count(new) != 1:
            raise RuntimeError(f"{label}: successor duplicated")
        return text
    if text.count(old) != 1:
        raise RuntimeError(f"{label}: expected one old anchor, found {text.count(old)}")
    return text.replace(old, new, 1)


def main() -> int:
    landing = LANDING.read_text(encoding="utf-8")
    landing = replace_once(landing, OLD_MOBILE, NEW_MOBILE, "mobile-band-padding")
    LANDING.write_text(landing, encoding="utf-8")

    brain = BRAIN.read_text(encoding="utf-8")
    brain = replace_once(brain, OLD_HEAD, NEW_HEAD, "build-info-head")
    BRAIN.write_text(brain, encoding="utf-8")

    TEST.write_text(TEST_CONTENT, encoding="utf-8")

    final_landing = LANDING.read_text(encoding="utf-8")
    final_brain = BRAIN.read_text(encoding="utf-8")
    if OLD_MOBILE in final_landing or NEW_MOBILE not in final_landing:
        raise RuntimeError("mobile contract not materialized")
    if OLD_HEAD in final_brain or NEW_HEAD not in final_brain:
        raise RuntimeError("HEAD build identity contract not materialized")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
