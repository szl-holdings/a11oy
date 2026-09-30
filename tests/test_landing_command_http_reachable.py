# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""HTTP 200 is REACHABLE or UNAVAILABLE, never MEASURED/ALLOW from r.ok."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANDING = ROOT / "landing" / "index.html"
COMMAND = ROOT / "pages" / "command-center.html"


def test_landing_http_200_is_reachable_not_allow() -> None:
    text = LANDING.read_text(encoding="utf-8")
    assert "ALLOW ✓" not in text
    assert "data.decision === 'allow'" not in text
    assert "setStatus('ok', 'REACHABLE')" in text
    assert "setStatus('err', 'UNAVAILABLE')" in text
    assert "setStatus('ok', label" not in text
    assert "setStatus('err', 'error')" not in text
    assert "setStatus('ok', 'MEASURED')" not in text
    assert "setStatus('ok', 'ALLOW')" not in text
    assert "HTTP 200 is REACHABLE, never MEASURED/ALLOW from r.ok." in text


def test_command_center_http_ok_is_not_measured_or_allow() -> None:
    text = COMMAND.read_text(encoding="utf-8")
    assert "if(!r.ok) return null;" in text
    assert "HTTP 200 is REACHABLE, never MEASURED/ALLOW from r.ok." in text
    assert "HTTP 200 is not ALLOW" in text
    assert "ok?`MEASURED ${r.length} receipts" not in text
    assert 'r.ok ? "MEASURED"' not in text
    assert 'r.ok ? "ALLOW"' not in text
    assert "catch(_err){ return null; }" in text
    assert "SOFTWARE ${r.length} receipts. Local chain intact. Not MEASURED." in text
    assert ':"UNAVAILABLE"' in text.split("$(\"#verify\").onclick=async()=>{", 1)[1]
