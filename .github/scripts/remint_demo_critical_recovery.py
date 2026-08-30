#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Prepare a clean, current-main demo-critical surface recovery.

This one-shot builder transports only the reviewed presentation delta from closed
PR #1512 onto the exact protected-main base, then applies two bounded current
repairs: canonical KANCHAY tokens/mobile clearance and 44 px hit-target floors.
It never commits, pushes, merges, deploys, or reads secret values. Publication is
performed separately by the protected workflow with GitHub createCommitOnBranch.
"""
from __future__ import annotations

import hashlib
import json
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
CANDIDATE_PATHS = PRESENTATION_PATHS + (
    "serve.py",
    "scripts/hf_universal_frontend_control.py",
)
ESSENTIAL_PATHS = {
    "a11oy_landing.html",
    "pages/console.html",
    "serve.py",
    "scripts/hf_universal_frontend_control.py",
}
REPORT_DIR = Path("reports/demo-critical-recovery")


def run(*args: str, capture: bool = False, check: bool = True) -> str:
    proc = subprocess.run(
        args,
        check=False,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )
    if check and proc.returncode:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(f"command failed ({proc.returncode}): {' '.join(args)}\n{detail}")
    return proc.stdout if capture else ""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    require(count == 1, f"{label}: expected one anchor, found {count}")
    return text.replace(old, new, 1)


def ensure_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    return replace_once(text, old, new, label)


def regex_once(text: str, pattern: str, replacement: str, label: str) -> str:
    out, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
    require(count == 1, f"{label}: expected one regex anchor, found {count}")
    return out


def apply_reviewed_delta() -> None:
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


def repair_console() -> None:
    path = Path("pages/console.html")
    text = path.read_text(encoding="utf-8")

    replacements = (
        ("--teal:#19efc6;", "--teal:#3af4c8;", "KANCHAY teal"),
        ("--proof:#2dd4bf;", "--proof:#3af4c8;", "KANCHAY proof"),
        ("--ground:#060910;", "--ground:#080c14;", "KANCHAY ground"),
        ("--lattice:#818cf8;", "--lattice:#5b8dee;", "KANCHAY lattice"),
    )
    for old, new, label in replacements:
        if old in text:
            text = text.replace(old, new)
        require(new in text, f"{label}: canonical token missing")

    text = ensure_once(
        text,
        "@media(max-width:600px){\n  .rail{display:none}",
        "@media(max-width:600px){\n  .content{padding-bottom:104px}\n  .rail{display:none}",
        "mobile nav-dock clearance",
    )

    required = (
        "--teal:#3af4c8",
        "--ground:#080c14",
        "--proof:#3af4c8",
        "--lattice:#5b8dee",
        "padding-bottom:104px",
        "V.investor=",
        "go('investor')",
        "Verify on a11oy.net",
        "function emptyUnknown(kind, detail)",
        "function szlViewFromLocation()",
        'id="szl-series-a-cards"',
        "locked_formula_count===8",
        "window.API+'/v1/honest'",
    )
    missing = [needle for needle in required if needle not in text]
    require(not missing, f"console missing recovered contracts: {missing}")
    require("tier_counts['LOCKED-PROVEN']" not in text, "genome catalog still drives locked-kernel claim")
    require("data-szl-command-bar" in text, "holographic command bar is not mounted")
    path.write_text(text, encoding="utf-8")


def repair_landing() -> None:
    path = Path("a11oy_landing.html")
    text = path.read_text(encoding="utf-8")

    # Preserve the established function name consumed by the investor smoke contract.
    text = text.replace("loadKernelLocked", "loadLockedKernel")

    text = ensure_once(
        text,
        ".nav .wrap{display:flex;align-items:center;gap:18px;height:64px}",
        ".nav .wrap{display:flex;align-items:center;flex-wrap:wrap;gap:18px;min-height:64px;height:auto}",
        "landing navigation wrap",
    )
    text = ensure_once(
        text,
        ".nav nav a{display:inline-flex;align-items:center;justify-content:center;min-height:48px;padding:8px 13px;border-radius:10px;color:var(--sub);font-size:14px;font-weight:500;transition:.15s}",
        ".nav nav a{display:inline-flex;align-items:center;justify-content:center;min-width:44px;min-height:44px;height:auto;padding:10px 14px;border-radius:10px;color:var(--sub);font-size:14px;font-weight:500;transition:.15s;position:relative;z-index:1;pointer-events:auto;touch-action:manipulation}",
        "landing navigation hit target",
    )
    text = ensure_once(
        text,
        ".nav .wrap{position:relative;height:64px;padding-inline:14px;gap:10px}",
        ".nav .wrap{position:relative;min-height:64px;height:auto;padding-inline:14px;gap:10px}",
        "landing mobile navigation wrap",
    )
    text = ensure_once(
        text,
        "  .btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;padding:11px 21px;border-radius:9px;",
        "  #fw-hash-btn{display:inline-flex;align-items:center;justify-content:center;min-width:44px;min-height:44px;padding:10px 14px;touch-action:manipulation}\n  .btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;padding:11px 21px;border-radius:9px;",
        "fourth-wall hash control CSS",
    )
    old_button = 'id="fw-hash-btn" style="margin-left:8px;background:transparent;border:1px solid #3AF4C8;color:#3AF4C8;padding:2px 10px;border-radius:3px;font:inherit;cursor:pointer"'
    new_button = 'id="fw-hash-btn" style="margin-left:8px;background:transparent;border:1px solid #3AF4C8;color:#3AF4C8;min-width:44px;min-height:44px;padding:10px 14px;border-radius:3px;font:inherit;cursor:pointer;touch-action:manipulation"'
    text = ensure_once(text, old_button, new_button, "fourth-wall hash control inline floor")

    required = (
        '<a href="/console">Command</a>',
        "Proof registry ↗",
        "loadLockedKernel",
        "h.locked_formula_count",
        'aria-expanded="false"',
        "min-width:44px;min-height:44px",
    )
    missing = [needle for needle in required if needle not in text]
    require(not missing, f"landing missing recovered contracts: {missing}")
    require("loadKernelLocked" not in text, "stale landing function alias remains")
    path.write_text(text, encoding="utf-8")


def repair_universal_frontend() -> None:
    path = Path("scripts/hf_universal_frontend_control.py")
    text = path.read_text(encoding="utf-8")
    old = 'button, [role="button"], input, select, textarea, a.sz-control {{ min-height: 44px; }}'
    new = 'button, [role="button"], input, select, textarea, a.sz-control, nav a, header a, #fw-hash-btn {{ min-height: 44px; min-width: 44px; }}'
    text = ensure_once(text, old, new, "universal 44px target floor")
    path.write_text(text, encoding="utf-8")


def repair_serve() -> None:
    path = Path("serve.py")
    text = path.read_text(encoding="utf-8")

    if '_IMAGE_PAGES_DIR = Path("/app/pages")' not in text:
        text = regex_once(
            text,
            r'^PAGES_DIR = Path\("/app/pages"\)$',
            '_IMAGE_PAGES_DIR = Path("/app/pages")\n_LOCAL_PAGES_DIR = Path(__file__).resolve().parent / "pages"\nPAGES_DIR = _IMAGE_PAGES_DIR if (_IMAGE_PAGES_DIR / "console.html").is_file() else _LOCAL_PAGES_DIR',
            "runtime/local pages selection",
        )
    if '_IMAGE_SHARED_DIR = Path("/app/static/shared")' not in text:
        text = regex_once(
            text,
            r'^_SHARED_DIR = Path\("/app/static/shared"\)$',
            '_IMAGE_SHARED_DIR = Path("/app/static/shared")\n_LOCAL_SHARED_DIR = Path(__file__).resolve().parent / "static" / "shared"\n_SHARED_DIR = _IMAGE_SHARED_DIR if _IMAGE_SHARED_DIR.is_dir() else _LOCAL_SHARED_DIR',
            "runtime/local shared-asset selection",
        )
    if '"szl_command_bar.js": _VENDOR_JS_CT' not in text:
        text = regex_once(
            text,
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
    if 'a11oy_khipu_chat.register(app)' not in text:
        text = replace_once(text, catchall, additive_routes + catchall, "front-moved public/Khipu routes")

    required = (
        '"szl_command_bar.js": _VENDOR_JS_CT',
        '"szl_command_bar.css": _VENDOR_CSS_CT',
        'url="/console?view=investor"',
        'app.add_api_route(\n    "/investor"',
        'app.add_api_route(\n    "/estate"',
        "a11oy_khipu_chat.register(app)",
        'if p == "/" or p == "/landing":',
        "_is_public_front",
    )
    missing = [needle for needle in required if needle not in text]
    require(not missing, f"serve.py missing recovered contracts: {missing}")
    path.write_text(text, encoding="utf-8")


def write_manifest() -> None:
    changed = sorted(
        line.strip()
        for line in run(
            "git", "diff", "--name-only", EXPECTED_MAIN, "--", *CANDIDATE_PATHS, capture=True
        ).splitlines()
        if line.strip()
    )
    require(ESSENTIAL_PATHS.issubset(changed), f"essential candidate files did not change: {sorted(ESSENTIAL_PATHS - set(changed))}")
    require(set(changed).issubset(CANDIDATE_PATHS), f"unexpected candidate paths: {sorted(set(changed) - set(CANDIDATE_PATHS))}")
    for rel in changed:
        require(Path(rel).is_file(), f"candidate path missing or not a regular file: {rel}")

    run("git", "diff", "--check", EXPECTED_MAIN, "--", *changed)
    payload = {
        "schema": "szl.demo-critical-surface-recovery/v2",
        "repository": "szl-holdings/a11oy",
        "base_sha": EXPECTED_MAIN,
        "reviewed_pr": 1512,
        "reviewed_base": REJECTED_BASE,
        "reviewed_head": REVIEWED_HEAD,
        "changed_paths": changed,
        "files": {
            rel: {
                "sha256": hashlib.sha256(Path(rel).read_bytes()).hexdigest(),
                "size": Path(rel).stat().st_size,
            }
            for rel in changed
        },
        "secret_values_read": False,
        "secret_values_emitted": False,
        "remote_mutations_performed": False,
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "candidate-manifest.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> None:
    run("git", "fetch", "--no-tags", "origin", "main")
    run("git", "fetch", "--no-tags", "origin", f"pull/1512/head:{PR_REMOTE}")
    actual_main = run("git", "rev-parse", "origin/main", capture=True).strip()
    actual_reviewed = run("git", "rev-parse", PR_REMOTE, capture=True).strip()
    require(actual_main == EXPECTED_MAIN, f"protected main moved: {actual_main}")
    require(actual_reviewed == REVIEWED_HEAD, f"PR #1512 head moved: {actual_reviewed}")

    apply_reviewed_delta()
    repair_console()
    repair_landing()
    repair_universal_frontend()
    repair_serve()

    run("python3", "-m", "py_compile", "serve.py", "a11oy_nav_wireup.py", "a11oy_khipu_chat.py")
    write_manifest()


if __name__ == "__main__":
    main()
