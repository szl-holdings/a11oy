#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Restore the latest historically valid Try Khipu panel into current console.

The panel is a permanent source contract, but a later console rewrite dropped its
HTML/JavaScript block while leaving the route and regression tests intact. Rather
than reimplementing or hardcoding a stale copy, scan repository history for the
newest panel that satisfies today's contract and insert that exact block before
current ``</body>``. The one-shot controller removes this script after testing.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONSOLE = ROOT / "pages" / "console.html"
PATH_IN_GIT = "pages/console.html"
BEGIN = "/* try-khipu-panel"
END = "/* end try-khipu-panel */"

REQUIRED = (
    "Try Khipu",
    "/api/a11oy/v1/khipu/status",
    "/api/a11oy/v1/khipu/chat",
    "UNSIGNED",
    "Conjecture 1",
    "READY",
    "FAILED",
    "record_sha256",
    "URLSearchParams",
    "ROADMAP",
    "SNAPSHOT",
    "SIMULATED",
    "MEASURED",
    "not-a-secret",
    "https://szlholdings-szl-model-inference-lab.hf.space/v1",
    "not a trainer",
    "not Serve Studio",
    "8/8",
    "not a live control plane",
)
FORBIDDEN = (
    "tokens/s",
    "tok/s",
    "tokens_per_second",
    "tokens per second",
    "szl-forge-lab.hf.space",
)


def git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=ROOT, text=True, encoding="utf-8", errors="strict"
    )


def extract_panel(html: str) -> str | None:
    marker = html.find(BEGIN)
    end_marker = html.find(END, marker + 1)
    if marker < 0 or end_marker <= marker:
        return None
    script_start = html.rfind("<script", 0, marker)
    script_end = html.find("</script>", end_marker)
    if script_start < 0 or script_end < 0:
        return None
    script_end += len("</script>")
    block = html[script_start:script_end]
    lowered = block.lower()
    if any(value not in block for value in REQUIRED):
        return None
    if not ("V.command" in block or "command.render" in block):
        return None
    if not (
        "currentView()!=='command'" in block
        or 'currentView()!=="command"' in block
    ):
        return None
    if not ("get('view')" in block or 'get("view")' in block):
        return None
    if any(value in lowered for value in FORBIDDEN):
        return None
    return block


current = CONSOLE.read_text(encoding="utf-8")
if BEGIN in current or END in current or 'id="try-khipu-panel"' in current:
    raise SystemExit("Try Khipu panel already exists; refusing duplicate injection")

commits = git("log", "--all", "--date-order", "--format=%H", "--", PATH_IN_GIT).splitlines()
selected_sha = ""
selected_block: str | None = None
for sha in commits:
    try:
        historical = git("show", f"{sha}:{PATH_IN_GIT}")
    except subprocess.CalledProcessError:
        continue
    block = extract_panel(historical)
    if block is not None:
        selected_sha = sha
        selected_block = block
        break

if selected_block is None:
    raise SystemExit("no historical Try Khipu panel satisfies the current contract")

closing = current.rfind("</body>")
if closing < 0:
    raise SystemExit("closing body tag not found")
restored = current[:closing] + selected_block + "\n\n" + current[closing:]
CONSOLE.write_text(restored, encoding="utf-8", newline="\n")
print(f"restored Try Khipu panel from {selected_sha}")
