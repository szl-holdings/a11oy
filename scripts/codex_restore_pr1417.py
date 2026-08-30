#!/usr/bin/env python3
"""Three-way inverse merge for the stale-source overwrite in merged PR #1417.

Base is the bad #1417 result, ours is current protected-main-derived source, and
other is #1417's parent. This reapplies only the parent->bad inverse while
preserving later edits in conflict regions. It never pushes or mutates remotes.
"""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

BAD = "37753ef139e79f595b54e4420796e24297501d6b"
GOOD = "f58d6cd2648ab2a7590674dc4678f85af95f4dc9"
FILES = (
    "a11oy_landing.html",
    "pages/console.html",
    "pages/landing.html",
    "serve.py",
)


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(args, check=check, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def show(revision: str, path: str) -> bytes:
    return run("git", "show", f"{revision}:{path}").stdout


def merge_path(path: str) -> None:
    target = Path(path)
    current = target.read_bytes()
    base = show(BAD, path)
    other = show(GOOD, path)
    with tempfile.TemporaryDirectory(prefix="estate-v10-") as td:
        root = Path(td)
        ours_path = root / "current"
        base_path = root / "base"
        other_path = root / "other"
        ours_path.write_bytes(current)
        base_path.write_bytes(base)
        other_path.write_bytes(other)
        merged = run(
            "git",
            "merge-file",
            "--ours",
            "-p",
            str(ours_path),
            str(base_path),
            str(other_path),
            check=False,
        )
        if merged.returncode not in (0, 1):
            raise RuntimeError(
                f"merge-file failed for {path}: {merged.stderr.decode('utf-8', 'replace')}"
            )
        content = merged.stdout
        if b"<<<<<<<" in content or b">>>>>>>" in content or b"|||||||" in content:
            raise RuntimeError(f"unresolved conflict marker in {path}")
        target.write_bytes(content)


def require(text: str, needle: str, path: str) -> None:
    if needle not in text:
        raise RuntimeError(f"restoration contract missing in {path}: {needle}")


def main() -> int:
    for path in FILES:
        merge_path(path)

    console = Path("pages/console.html").read_text(encoding="utf-8")
    landing = Path("a11oy_landing.html").read_text(encoding="utf-8")
    serve = Path("serve.py").read_text(encoding="utf-8")

    for needle in (
        '--teal:#3af4c8',
        'id="szl-series-a-cards"',
        'V.estate=',
        "go('investor')",
        "u.searchParams.set('view', view)",
        'Verify on a11oy.net',
        'function emptyUnknown(kind, detail)',
        'locked_formula_count===8',
        'LOCKED-PROVEN (catalog)',
        '["Home"', '["Operate"', '["Build"', '["Observe"',
        '["Govern"', '["Research"', '["More"',
    ):
        require(console, needle, "pages/console.html")
    if "tier_counts['LOCKED-PROVEN']" in console:
        raise RuntimeError("console still binds kernel count to genome catalog")

    for needle in (
        '<a href="/console">Command</a>',
        'Proof registry ↗',
        'loadLockedKernel',
        'h.locked_formula_count',
        'aria-expanded',
    ):
        require(landing, needle, "a11oy_landing.html")

    for needle in (
        '"szl_command_bar.js": _VENDOR_JS_CT',
        '"szl_command_bar.css": _VENDOR_CSS_CT',
        'url="/console?view=investor"',
        'app.add_api_route("/investor"',
        'pages/estate.html',
        '"/estate"',
        'import a11oy_khipu_chat',
        '_resolve_llm_registry_module',
        'allow_methods=["GET", "HEAD", "POST", "OPTIONS"]',
        'if p == "/" or p == "/landing":',
        '_is_public_front',
    ):
        require(serve, needle, "serve.py")

    print("PR #1417 inverse three-way restoration contracts: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
