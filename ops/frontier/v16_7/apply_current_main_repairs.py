#!/usr/bin/env python3
"""Apply the narrow, current-main-native Frontier v16.7 source repairs.

This is deterministic source surgery, not an AI-agent workflow.  It never reads or
prints credentials, never performs Git operations, and refuses ambiguous source.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Callable

VERSION = "16.7.0"


class RepairError(RuntimeError):
    pass


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def exact(text: str, old: str, new: str, label: str, changes: list[str]) -> str:
    old_count = text.count(old)
    new_count = text.count(new)
    if old_count == 1 and new_count == 0:
        changes.append(label)
        return text.replace(old, new, 1)
    if old_count == 0 and new_count == 1:
        return text
    if old_count == 0 and new_count > 1:
        raise RepairError(f"{label}: repaired form appears {new_count} times")
    raise RepairError(
        f"{label}: expected exactly one old form or one repaired form; "
        f"old={old_count} repaired={new_count}"
    )


def remove_exact_line(text: str, line: str, label: str, changes: list[str]) -> str:
    token = line + "\n"
    count = text.count(token)
    if count == 1:
        changes.append(label)
        return text.replace(token, "", 1)
    if count == 0:
        return text
    raise RepairError(f"{label}: line occurs {count} times")


def repair_html(text: str, changes: list[str]) -> str:
    replacements = [
        (
            '<span id="updated" aria-live="polite">Not observed yet</span>',
            '<span id="updated" aria-live="polite">UNKNOWN · no observation yet</span>',
            "series-a SSR observation state is terminal",
        ),
        (
            '<strong data-key="estate">CHECKING</strong>',
            '<strong data-key="estate">UNKNOWN</strong>',
            "series-a SSR estate state is terminal",
        ),
        (
            '<strong data-key="trust">CHECKING</strong>',
            '<strong data-key="trust">UNKNOWN</strong>',
            "series-a SSR trust state is terminal",
        ),
        (
            '<strong data-key="signer">CHECKING</strong>',
            '<strong data-key="signer">UNKNOWN</strong>',
            "series-a SSR signer state is terminal",
        ),
        (
            '<ol id="events" aria-live="polite"><li>CONNECTING</li></ol>',
            '<ol id="events" aria-live="polite"><li data-placeholder="true">UNKNOWN · no governed events observed</li></ol>',
            "series-a SSR event state is terminal",
        ),
        (
            '<ol id="receipts"><li>CHECKING</li></ol>',
            '<ol id="receipts"><li>UNKNOWN · no signed receipts observed</li></ol>',
            "series-a SSR receipt state is terminal",
        ),
    ]
    for old, new, label in replacements:
        text = exact(text, old, new, label, changes)
    return text


def repair_app_js(text: str, changes: list[str]) -> str:
    old_catch = '''    } catch (error) {
      ["estate", "trust", "signer"].forEach(key => set(key, error.name === "AbortError" ? "TIMED_OUT" : "UNAVAILABLE"));
      document.getElementById("updated").textContent = error.name === "AbortError" ? "Timed out after 8 seconds" : String(error.message || error);
    }
'''
    new_catch = '''    } catch (error) {
      const state = error.name === "AbortError" ? "TIMED_OUT" : "UNAVAILABLE";
      ["estate", "repos", "prs", "spaces", "models", "datasets", "trust", "signer"].forEach(key => set(key, state));
      currentEvidence = null;
      invalidateAuthorization();
      document.getElementById("updated").textContent = error.name === "AbortError" ? "Timed out after 8 seconds" : String(error.message || error);
      document.getElementById("receipts").innerHTML = `<li>${state} · receipts endpoint did not produce a current observation</li>`;
    }
'''
    text = exact(
        text,
        old_catch,
        new_catch,
        "series-a fetch failure terminalizes every status card",
        changes,
    )

    old_decl = '''  const eventRail = document.getElementById("events");
  const seenEvents = new Set();
'''
    new_decl = '''  const eventRail = document.getElementById("events");
  const eventPlaceholder = () => eventRail.firstElementChild?.dataset.placeholder === "true";
  const seenEvents = new Set();
  const setEventTerminal = (text) => {
    if (seenEvents.size) return;
    const item = document.createElement("li");
    item.dataset.placeholder = "true";
    item.textContent = text;
    eventRail.replaceChildren(item);
  };
'''
    text = exact(
        text,
        old_decl,
        new_decl,
        "series-a event rail gains explicit placeholder semantics",
        changes,
    )
    text = exact(
        text,
        '    if (eventRail.firstElementChild?.textContent === "CONNECTING") eventRail.replaceChildren();',
        '    if (eventPlaceholder()) eventRail.replaceChildren();',
        "series-a event arrival clears any terminal placeholder",
        changes,
    )

    old_open = '''    source.addEventListener("open", () => {
      if (eventRail.firstElementChild?.textContent === "CONNECTING") {
        eventRail.firstElementChild.textContent = "CONNECTED · waiting for governed events";
      }
    });
    source.addEventListener("error", () => {
      if (!eventRail.children.length) eventRail.innerHTML = "<li>RECONNECTING</li>";
    });
'''
    new_open = '''    source.addEventListener("open", () => {
      setEventTerminal("CONNECTED · waiting for governed events");
    });
    source.addEventListener("error", () => {
      setEventTerminal("UNAVAILABLE · event stream disconnected");
    });
'''
    text = exact(
        text,
        old_open,
        new_open,
        "series-a event stream reaches explicit connected or unavailable state",
        changes,
    )
    return text


def repair_console_page(text: str, changes: list[str]) -> str:
    replacements = [
        (
            '>initializing&hellip;</div>',
            '>UNKNOWN · awaiting first measured observation</div>',
            "console bootguard starts in a terminal unknown state",
        ),
        (
            '<span id="runtime-status-text">CHECKING</span>',
            '<span id="runtime-status-text">UNKNOWN</span>',
            "console runtime starts in a terminal unknown state",
        ),
        (
            '<main class="content" id="content"><div class="view-sub">loading…</div></main>',
            '<main class="content" id="content"><div class="view-sub">UNKNOWN · no measured console view has rendered</div></main>',
            "console main shell is terminal before JavaScript",
        ),
        (
            "msg.innerHTML='live meter reconnecting&hellip; <span style=\"color:#5fb3a3\">shell ready</span>';",
            "msg.innerHTML='STATUS UNAVAILABLE · shell ready';",
            "console reconnect stall is explicit and terminal",
        ),
    ]
    for old, new, label in replacements:
        text = exact(text, old, new, label, changes)
    return text


def repair_root_console(text: str, changes: list[str]) -> str:
    return exact(
        text,
        '<main class="content" id="content"><div class="view-sub">loading…</div></main>',
        '<main class="content" id="content"><div class="view-sub">UNKNOWN · no measured root view has rendered</div></main>',
        "root console shell is terminal before JavaScript",
        changes,
    )


def repair_readme(text: str, changes: list[str]) -> str:
    new = (
        "| Signed receipts on every governed action | **CONFIGURATION-BOUND** · SIGNED only "
        "when the persistent production key is present; otherwise explicitly UNSIGNED |"
    )
    pattern = re.compile(
        r"(?m)^\s*\|?\s*Signed receipts on every governed action\s*\|\s*"
        r"(?:\*\*)?LIVE(?:\*\*)?\s*\|?\s*$"
    )
    repaired_pattern = re.compile(
        r"(?m)^\s*\|?\s*Signed receipts on every governed action\s*\|\s*"
        r"(?:\*\*)?CONFIGURATION-BOUND(?:\*\*)?\s*·\s*SIGNED\s+only\s+"
        r"when\s+the\s+persistent\s+production\s+key\s+is\s+present;\s*"
        r"otherwise\s+explicitly\s+UNSIGNED\s*\|?\s*$"
    )
    matches = list(pattern.finditer(text))
    repaired_matches = list(repaired_pattern.finditer(text))
    if not matches and len(repaired_matches) == 1:
        return text
    if len(matches) != 1 or repaired_matches:
        raise RepairError(
            "README receipt claim: expected one unconditional LIVE line or the repaired line"
        )
    changes.append("README receipt claim is configuration-bound")
    return pattern.sub(new, text, count=1)


def repair_future_annotations(text: str, changes: list[str], label: str) -> str:
    return remove_exact_line(
        text,
        "from __future__ import annotations",
        label,
        changes,
    )


TRANSFORMS: dict[str, Callable[[str, list[str]], str]] = {
    "routers/series_a_web/index.html": repair_html,
    "routers/series_a_web/app.js": repair_app_js,
    "pages/console.html": repair_console_page,
    "console/index.html": repair_root_console,
    "README.md": repair_readme,
    "routers/frontier_reads.py": lambda text, changes: repair_future_annotations(
        text, changes, "frontier route removes postponed annotations"
    ),
    "routers/series_a_control_plane.py": lambda text, changes: repair_future_annotations(
        text, changes, "Series-A route removes postponed annotations"
    ),
}


def atomic_write(path: Path, data: bytes) -> None:
    mode = path.stat().st_mode & 0o777
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        tmp = Path(handle.name)
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(tmp, mode)
    os.replace(tmp, path)


def process(root: Path, apply: bool) -> tuple[dict, bool]:
    report: dict = {
        "schema": "szl.frontier.current-main-repair/v16.7",
        "version": VERSION,
        "recorded_at": utc_now(),
        "repository_root": str(root),
        "mode": "apply" if apply else "check",
        "files": [],
        "secret_values_read": False,
        "secret_values_printed": False,
    }
    would_change = False
    staged: list[tuple[Path, bytes]] = []

    for rel, transform in TRANSFORMS.items():
        path = root / rel
        if not path.is_file() or path.is_symlink():
            raise RepairError(f"missing or unsafe required source file: {rel}")
        before = path.read_bytes()
        try:
            source = before.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise RepairError(f"{rel}: not UTF-8") from exc
        changes: list[str] = []
        after_text = transform(source, changes)
        after = after_text.encode("utf-8")
        changed = after != before
        would_change |= changed
        staged.append((path, after))
        report["files"].append(
            {
                "path": rel,
                "before_sha256": sha256(before),
                "after_sha256": sha256(after),
                "changed": changed,
                "repairs": changes,
            }
        )

    if apply:
        for path, data in staged:
            if path.read_bytes() != data:
                atomic_write(path, data)
    report["changed_file_count"] = sum(1 for item in report["files"] if item["changed"])
    report["status"] = (
        "APPLIED" if apply and would_change else
        "ALREADY_COMPLIANT" if not would_change else
        "REPAIRS_REQUIRED"
    )
    return report, would_change


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--report")
    args = parser.parse_args()

    root = Path(args.repo).expanduser().resolve(strict=True)
    try:
        report, would_change = process(root, args.apply)
    except RepairError as exc:
        report = {
            "schema": "szl.frontier.current-main-repair/v16.7",
            "version": VERSION,
            "recorded_at": utc_now(),
            "repository_root": str(root),
            "mode": "apply" if args.apply else "check",
            "status": "BLOCKED_SOURCE_DRIFT",
            "error": str(exc),
            "secret_values_read": False,
            "secret_values_printed": False,
        }
        if args.report:
            Path(args.report).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(report, sort_keys=True))
        return 3

    if args.report:
        Path(args.report).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))
    if args.check and would_change:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
