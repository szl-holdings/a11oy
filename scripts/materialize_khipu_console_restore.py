#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Repair the Investor Smoke false negative for the live Try Khipu panel.

The current console still contains the source-backed panel, but its DOM node is
constructed by JavaScript rather than emitted as literal ``id=\"...\"`` markup.
The smoke gate used that one serialization as its only proof and therefore
reported a missing panel. Replace the brittle check with a fail-closed source
contract and add a regression over the current console plus an incomplete fake.
The one-shot workflow removes this materializer after verification.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "scripts" / "investor_smoke_gate.py"
TESTS = ROOT / "tests" / "test_investor_smoke_gate.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one anchor, found {count}")
    return text.replace(old, new, 1)


gate = GATE.read_text(encoding="utf-8")
helper_anchor = '''\ndef static_s_verdicts(root: Path = ROOT) -> list[Verdict]:\n'''
helper = '''\ndef has_try_khipu_panel_source(console: str) -> bool:\n    """Return true only for the complete source-backed Command Center panel.\n\n    The panel is injected by JavaScript, so literal HTML attribute quoting is not\n    a stable contract. Require both delimiters, both same-origin routes, the\n    Command-only/deep-link guards, and the honesty labels instead.\n    """\n    begin = console.find("/* try-khipu-panel")\n    end = console.find("/* end try-khipu-panel */", begin + 1)\n    if begin < 0 or end <= begin:\n        return False\n    panel = console[begin:end]\n    required = (\n        "Try Khipu",\n        "/api/a11oy/v1/khipu/status",\n        "/api/a11oy/v1/khipu/chat",\n        "UNSIGNED",\n        "Conjecture 1",\n        "READY",\n        "FAILED",\n        "record_sha256",\n        "URLSearchParams",\n        "currentView",\n        "V.command",\n        "ROADMAP",\n        "SNAPSHOT",\n        "SIMULATED",\n        "MEASURED",\n        "not-a-secret",\n    )\n    if not all(token in panel for token in required):\n        return False\n    view_guard = (\n        "currentView()!=='command'" in panel\n        or 'currentView()!=="command"' in panel\n    )\n    deep_link_guard = "get('view')" in panel or 'get("view")' in panel\n    return view_guard and deep_link_guard\n\n\ndef static_s_verdicts(root: Path = ROOT) -> list[Verdict]:\n'''
gate = replace_once(gate, helper_anchor, helper, "helper insertion")
old_check = '''    console = _read(root, "pages/console.html")\n    khipu_ok = 'id="try-khipu-panel"' in console and "Try Khipu" in console\n    # Console Try Khipu is source-backed after #1390; live HTML is re-probed in live mode.\n'''
new_check = '''    console = _read(root, "pages/console.html")\n    khipu_ok = has_try_khipu_panel_source(console)\n    # Console Try Khipu is source-backed after #1390; live HTML is re-probed in live mode.\n'''
gate = replace_once(gate, old_check, new_check, "Khipu source check")
GATE.write_text(gate, encoding="utf-8", newline="\n")


tests = TESTS.read_text(encoding="utf-8")
test_anchor = '''\nclass _FakeHttpResp:\n'''
new_tests = '''\ndef test_try_khipu_source_contract_accepts_current_dynamic_dom_panel():\n    console = (ROOT / "pages" / "console.html").read_text(encoding="utf-8")\n    assert gate.has_try_khipu_panel_source(console) is True\n\n\ndef test_try_khipu_source_contract_rejects_marker_only_stub():\n    incomplete = """\n    /* try-khipu-panel */\n    Try Khipu /api/a11oy/v1/khipu/status /api/a11oy/v1/khipu/chat\n    /* end try-khipu-panel */\n    """\n    assert gate.has_try_khipu_panel_source(incomplete) is False\n\n\nclass _FakeHttpResp:\n'''
tests = replace_once(tests, test_anchor, new_tests, "regression tests")
TESTS.write_text(tests, encoding="utf-8", newline="\n")

print("repaired Try Khipu Investor Smoke source contract")
