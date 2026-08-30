#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""One-shot, branch-only remint of the clean demo-critical surface recovery.

The rejected PR #1512 carried useful reviewed presentation bytes but an
unacceptable commit ancestry and three material review findings.  This script
applies only its presentation/readiness delta onto the current protected-main
base, preserves the current loadLockedKernel implementation, repairs mobile
clearance and canonical KANCHAY tokens, and makes narrowly-scoped additive
runtime registrations in serve.py.  It never updates main directly.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

EXPECTED_MAIN = "bb065e8c6669cf8afd51e3141f57ecf9f46b4c36"
REJECTED_BASE = "0798d91a36306ae508d3a22cfce0171104a37025"
REVIEWED_HEAD = "934cc4c12827408c4c5be5c95e9f7cb07befcfea"
PR_REMOTE = "refs/remotes/origin/pr-1512"
PRESENTATION_PATHS = (
    "a11oy_landing.html",
    "a11oy_nav_wireup.py",
    "pages/console.html",
    "pages/landing.html",
    "tools/readiness-harness/tabs.json",
)


def run(*args: str, capture: bool = False) -> str:
    proc = subprocess.run(
        args,
        check=True,
        text=True,
        stdout=subprocess.PIPE if capture else None,
    )
    return proc.stdout if capture else ""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    require(count == 1, f"{label}: expected one anchor, found {count}")
    return text.replace(old, new, 1)


def regex_once(text: str, pattern: str, replacement: str, label: str) -> str:
    out, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
    require(count == 1, f"{label}: expected one regex anchor, found {count}")
    return out


def git_show(ref: str, path: str) -> str:
    return run("git", "show", f"{ref}:{path}", capture=True)


def main() -> None:
    run("git", "fetch", "--no-tags", "origin", "main")
    run(
        "git",
        "fetch",
        "--no-tags",
        "origin",
        f"pull/1512/head:{PR_REMOTE}",
    )

    actual_main = run("git", "rev-parse", "origin/main", capture=True).strip()
    actual_reviewed = run("git", "rev-parse", PR_REMOTE, capture=True).strip()
    require(actual_main == EXPECTED_MAIN, f"protected main moved: {actual_main}")
    require(actual_reviewed == REVIEWED_HEAD, f"PR #1512 head moved: {actual_reviewed}")

    original_console = Path("pages/console.html").read_text(encoding="utf-8")
    locked_start = original_console.index("async function loadLockedKernel(name){")
    locked_end = original_console.index("async function previewPrompt(", locked_start)
    locked_block = original_console[locked_start:locked_end]

    patch = run(
        "git",
        "diff",
        "--binary",
        REJECTED_BASE,
        REVIEWED_HEAD,
        "--",
        *PRESENTATION_PATHS,
        capture=True,
    )
    require(bool(patch.strip()), "reviewed presentation patch is empty")
    patch_path = Path(".git/remint-demo-critical.patch")
    patch_path.write_text(patch, encoding="utf-8")
    run("git", "apply", "--3way", str(patch_path))

    console_path = Path("pages/console.html")
    console = console_path.read_text(encoding="utf-8")
    require("async function loadLockedKernel(name){" not in console, "reviewed candidate unexpectedly retained loadLockedKernel")
    console = replace_once(
        console,
        "async function previewPrompt(",
        locked_block + "async function previewPrompt(",
        "restore loadLockedKernel",
    )
    for old, new, label in (
        ("--teal:#19efc6;", "--teal:#3af4c8;", "KANCHAY teal"),
        ("--proof:#2dd4bf;", "--proof:#3af4c8;", "KANCHAY proof"),
        ("--ground:#060910;", "--ground:#080c14;", "KANCHAY ground"),
        ("--lattice:#818cf8;", "--lattice:#5b8dee;", "KANCHAY lattice"),
    ):
        require(old in console, f"{label}: old token not found")
        console = console.replace(old, new)
    console = replace_once(
        console,
        "@media(max-width:600px){\n  .rail{display:none}",
        "@media(max-width:600px){\n  .content{padding-bottom:104px}\n  .rail{display:none}",
        "mobile nav-dock clearance",
    )
    console_path.write_text(console, encoding="utf-8")

    landing_path = Path("a11oy_landing.html")
    landing = landing_path.read_text(encoding="utf-8")
    require("loadKernelLocked" in landing, "reviewed landing rename anchor missing")
    landing = landing.replace("loadKernelLocked", "loadLockedKernel")
    landing_path.write_text(landing, encoding="utf-8")

    serve_path = Path("serve.py")
    serve = serve_path.read_text(encoding="utf-8")
    serve = regex_once(
        serve,
        r'^PAGES_DIR = Path\("/app/pages"\)$',
        '_IMAGE_PAGES_DIR = Path("/app/pages")\n_LOCAL_PAGES_DIR = Path(__file__).resolve().parent / "pages"\nPAGES_DIR = _IMAGE_PAGES_DIR if (_IMAGE_PAGES_DIR / "console.html").is_file() else _LOCAL_PAGES_DIR',
        "runtime/local pages selection",
    )
    serve = regex_once(
        serve,
        r'^_SHARED_DIR = Path\("/app/static/shared"\)$',
        '_IMAGE_SHARED_DIR = Path("/app/static/shared")\n_LOCAL_SHARED_DIR = Path(__file__).resolve().parent / "static" / "shared"\n_SHARED_DIR = _IMAGE_SHARED_DIR if _IMAGE_SHARED_DIR.is_dir() else _LOCAL_SHARED_DIR',
        "runtime/local shared-asset selection",
    )
    serve = regex_once(
        serve,
        r'^(?P<indent>\s*)"szl_holo3d\.js": _VENDOR_JS_CT,$',
        r'\g<indent>"szl_holo3d.js": _VENDOR_JS_CT,\n\g<indent>"szl_command_bar.js": _VENDOR_JS_CT,\n\g<indent>"szl_command_bar.css": _VENDOR_CSS_CT,',
        "command-bar allowlist",
    )

    catchall = '@app.get("/{full_path:path}")\nasync def spa_fallback(full_path: str):'
    additive_routes = '''# Public-front classification is explicit so operator-only navigation is never
# injected into investor-facing landing and trust surfaces.
class _PublicFrontClassificationMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http":
            p = scope.get("path") or ""
            _is_public_front = False
            if p == "/" or p == "/landing":
                _is_public_front = True
            elif p == "/trust" or p.startswith("/trust/"):
                _is_public_front = True
            if _is_public_front:
                scope.setdefault("state", {})["a11oy_public_front"] = True
        await self.app(scope, receive, send)


app.add_middleware(_PublicFrontClassificationMiddleware)


async def _investor_view_redirect() -> Response:
    return _PTG_Redirect(url="/console?view=investor", status_code=307)


app.add_api_route(
    "/investor",
    _investor_view_redirect,
    methods=["GET", "HEAD"],
    include_in_schema=False,
)


async def _series_a_estate_page() -> Response:
    f = PAGES_DIR / "estate.html"
    if f.is_file():
        return FileResponse(f, media_type="text/html")
    return FileResponse(INDEX_HTML, media_type="text/html")


app.add_api_route(
    "/estate",
    _series_a_estate_page,
    methods=["GET", "HEAD"],
    include_in_schema=False,
)


try:
    import a11oy_khipu_chat as _a11oy_khipu_chat

    _A11OY_KHIPU_CHAT_DIAG = _a11oy_khipu_chat.register(app)
except Exception as _a11oy_khipu_chat_error:
    _A11OY_KHIPU_CHAT_DIAG = (
        "a11oy_khipu_chat unavailable: "
        f"{type(_a11oy_khipu_chat_error).__name__}: {_a11oy_khipu_chat_error}"
    )


'''
    serve = replace_once(serve, catchall, additive_routes + catchall, "front-moved public/Khipu routes")
    serve_path.write_text(serve, encoding="utf-8")

    checks = {
        "pages/console.html": (
            "--teal:#3af4c8",
            "--ground:#080c14",
            "--proof:#3af4c8",
            "--lattice:#5b8dee",
            "padding-bottom:104px",
            "async function loadLockedKernel(name){",
            "V.investor=",
            "go('investor')",
            "Verify on a11oy.net",
            "function emptyUnknown(kind, detail)",
            "function szlViewFromLocation()",
        ),
        "a11oy_landing.html": (
            '<a href="/console">Command</a>',
            "Proof registry ↗",
            "loadLockedKernel",
            "h.locked_formula_count",
        ),
        "serve.py": (
            '"szl_command_bar.js": _VENDOR_JS_CT',
            '"szl_command_bar.css": _VENDOR_CSS_CT',
            'url="/console?view=investor"',
            'app.add_api_route(\n    "/investor"',
            'app.add_api_route(\n    "/estate"',
            "a11oy_khipu_chat.register(app)",
            'if p == "/" or p == "/landing":',
            "_is_public_front",
        ),
    }
    for path, required in checks.items():
        text = Path(path).read_text(encoding="utf-8")
        missing = [needle for needle in required if needle not in text]
        require(not missing, f"{path}: missing source contracts {missing}")

    require("tier_counts['LOCKED-PROVEN']" not in console, "genome tier count still drives kernel chip")
    require("loadKernelLocked" not in landing, "landing function rename not repaired")

    run("python3", "-m", "py_compile", "serve.py", "a11oy_nav_wireup.py", "a11oy_khipu_chat.py")
    run("git", "diff", "--check")
    run("git", "add", *PRESENTATION_PATHS, "serve.py")
    require(bool(run("git", "diff", "--cached", "--name-only", capture=True).strip()), "no staged recovery")

    run("git", "config", "user.name", "SZL GitHub Recovery")
    run("git", "config", "user.email", "stephenlutar2@gmail.com")
    run(
        "git",
        "commit",
        "-m",
        "fix(runtime): restore demo-critical surface ownership\n\nRemint the independently useful presentation bytes from closed PR #1512 onto current protected main without carrying its ancestry. Preserve loadLockedKernel, add mobile dock clearance, restore canonical KANCHAY tokens, wire exact investor/estate/Khipu routes, and serve real local/runtime page assets.\n\nSigned-off-by: Stephen Lutar <stephenlutar2@gmail.com>",
    )
    branch = run("git", "branch", "--show-current", capture=True).strip()
    require(branch == "fix/demo-critical-surface-recovery-20260830", f"unexpected branch {branch}")
    run("git", "push", "origin", f"HEAD:{branch}")


if __name__ == "__main__":
    main()
