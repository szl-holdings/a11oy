#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Apply the bounded browser-compatible investor-smoke transport repair.

The live smoke gate continues to probe the canonical product origin and keeps
all S1-S12 verdicts fail-closed. This patch only aligns its public GET/HEAD
transport with the repository's established Cloudflare-compatible probe
contract. No credential, cookie, bypass header, or alternate origin is added.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GATE = ROOT / "scripts" / "investor_smoke_gate.py"
TESTS = ROOT / "tests" / "test_investor_smoke_gate.py"

OLD_UA = 'USER_AGENT = "a11oy-investor-smoke-gate/1.0 (+https://github.com/szl-holdings/a11oy)"'
NEW_UA = '''USER_AGENT = (
    "Mozilla/5.0 (compatible; a11oy-investor-smoke-gate/1.1; "
    "+https://github.com/szl-holdings/a11oy)"
)'''

OLD_HEADERS = '        headers={"User-Agent": USER_AGENT, "Accept": "*/*"},'
NEW_HEADERS = '''        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },'''

TEST_MARKER = "cloudflare-compatible browser headers"
TEST_BLOCK = r'''

def test_http_request_uses_cloudflare_compatible_browser_headers(monkeypatch):
    captured = {}

    class _Opener:
        def open(self, req, timeout=20):
            captured.update({key.lower(): value for key, value in req.header_items()})
            return _FakeHttpResp()

    monkeypatch.setattr(
        gate.urllib.request, "build_opener", lambda *_a, **_k: _Opener()
    )
    got = gate.http_request("https://example.invalid/healthz")
    assert got.status == 200
    assert captured["user-agent"].startswith("Mozilla/5.0")
    assert "a11oy-investor-smoke-gate/1.1" in captured["user-agent"]
    assert captured["accept-language"] == "en-US,en;q=0.9"
    assert captured["cache-control"] == "no-cache"
    assert captured["pragma"] == "no-cache"
    assert "authorization" not in captured
    assert "cookie" not in captured
'''


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected exactly one anchor in {path}, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def append_test_once(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if TEST_MARKER in text:
        raise RuntimeError(f"test marker already present in {path}")
    path.write_text(text.rstrip() + TEST_BLOCK.rstrip() + "\n", encoding="utf-8")


def main() -> int:
    replace_once(GATE, OLD_UA, NEW_UA)
    replace_once(GATE, OLD_HEADERS, NEW_HEADERS)
    append_test_once(TESTS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
