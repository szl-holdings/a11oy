#!/usr/bin/env python3
"""Catch broken local image references in the a11oy docs before they ship.

The VitePress build does NOT fail on a missing navbar logo, a missing hero
image, or a broken ``![](...)`` ref in a README that lives OUTSIDE its srcDir
(``docs/site/docs/``). A build-only CI guard therefore cannot catch the class of
bug from #719 (a footer avatar / navbar logo pointing at an image file that was
never committed anywhere).

This guard scans the whole ``docs/site`` tree (the documentation site that ships)
for LOCAL image references and fails when any referenced image does not resolve
to a committed (git-tracked) file:

  * markdown images           ``![alt](path "title")``
  * inline HTML               ``<img ... src="path">`` / ``<source ... src="path">``
  * config / frontmatter      ``logo:`` / ``thumbnail:`` / ``favicon:`` /
                              ``image:`` / ``src:`` values ending in an image
                              extension (VitePress ``config.mjs`` navbar logo,
                              the home-page ``hero.image.src``, etc.)

Remote references (``http://``, ``https://``, protocol-relative ``//``,
``data:``) are ignored — only local asset paths are checked. Each reference is
resolved both relative to the referencing file and, for ``/``-absolute refs,
against the VitePress ``public/`` directory and the repo root, mirroring how
VitePress and GitHub render them. A reference passes if ANY of those candidate
resolutions is a committed file; a file that exists on disk but was never
``git add``-ed still fails (that is exactly the "forgot to commit the asset"
mistake we want to catch).

See ``scripts/check_local_image_refs.test.sh`` for the offline
negative-fixture self-test.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from typing import Dict, List, Optional, Set, Tuple

IMAGE_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif",
    ".svg", ".ico", ".bmp", ".tif", ".tiff", ".apng",
}

# File types we look inside for image references.
SCANNED_EXTS = {
    ".md", ".markdown", ".mjs", ".js", ".cjs", ".ts",
    ".json", ".json5", ".yml", ".yaml", ".html", ".htm", ".vue",
}

REMOTE_PREFIXES = ("http://", "https://", "//", "data:", "mailto:", "tel:")

# ![alt](url "optional title")  — url may be wrapped in <...>
MD_IMAGE_RE = re.compile(
    r"!\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+[\"'][^\"']*[\"'])?\s*\)"
)
# <img ... src="url">  /  <source ... src="url">
HTML_SRC_RE = re.compile(
    r"<(?:img|source)\b[^>]*?\bsrc\s*=\s*[\"']([^\"']+)[\"']",
    re.IGNORECASE,
)
# config / frontmatter:   key: 'value'   (one line at a time)
ASSET_KEY_RE = re.compile(
    r"""\b(?P<key>logo|thumbnail|image|favicon|src)\s*:\s*"""
    r"""['"]?(?P<val>[^'"#\n,}\]]+?)['"]?\s*(?:[,}\]]|$)"""
)
ASSET_KEYS = {"logo", "thumbnail", "image", "favicon", "src"}


def norm(p: str) -> str:
    return os.path.normpath(p).replace(os.sep, "/")


def is_remote(ref: str) -> bool:
    low = ref.strip().lower()
    return low.startswith(REMOTE_PREFIXES) or low.startswith("#")


def has_image_ext(ref: str) -> bool:
    base = ref.split("?", 1)[0].split("#", 1)[0]
    return os.path.splitext(base)[1].lower() in IMAGE_EXTS


def clean_ref(ref: str) -> str:
    ref = ref.strip()
    for sep in ("?", "#"):
        i = ref.find(sep)
        if i != -1:
            ref = ref[:i]
    return ref.strip()


def looks_templated(ref: str) -> bool:
    return any(tok in ref for tok in ("{{", "}}", "${", "<%", "%>")) or (" " in ref)


def git_tracked(root: str) -> Set[str]:
    out = subprocess.run(
        ["git", "-C", root, "ls-files", "-z"],
        check=True, capture_output=True, text=True,
    ).stdout
    return {norm(p) for p in out.split("\0") if p}


def discover_public_dirs(root: str, scan_rel: str) -> List[str]:
    """Return repo-relative VitePress public/ dirs (sibling of every .vitepress)."""
    pubs: List[str] = []
    scan_abs = os.path.join(root, scan_rel)
    for dirpath, dirnames, _ in os.walk(scan_abs):
        if ".vitepress" in dirnames:
            src_dir = os.path.relpath(dirpath, root)
            pubs.append(norm(os.path.join(src_dir, "public")))
    return pubs


def candidates(ref: str, file_rel: str, public_dirs: List[str]) -> List[str]:
    cands: List[str] = []
    if ref.startswith("/"):
        rel = ref.lstrip("/")
        cands.append(norm(rel))
        for pub in public_dirs:
            cands.append(norm(os.path.join(pub, rel)))
    else:
        cands.append(norm(os.path.join(os.path.dirname(file_rel), ref)))
    seen: List[str] = []
    for c in cands:
        if c not in seen:
            seen.append(c)
    return seen


def extract_refs(text: str) -> List[Tuple[int, str]]:
    """Yield (line_no, raw_ref) for every local image reference in the text."""
    refs: List[Tuple[int, str]] = []

    def line_of(pos: int) -> int:
        return text.count("\n", 0, pos) + 1

    for m in MD_IMAGE_RE.finditer(text):
        refs.append((line_of(m.start()), m.group(1)))
    for m in HTML_SRC_RE.finditer(text):
        refs.append((line_of(m.start()), m.group(1)))
    for lineno, line in enumerate(text.splitlines(), start=1):
        code = line.split("//", 1)[0]
        for m in ASSET_KEY_RE.finditer(code):
            val = m.group("val").strip()
            if has_image_ext(val):
                refs.append((lineno, val))
    return refs


def check_file(
    abs_path: str,
    file_rel: str,
    tracked: Set[str],
    public_dirs: List[str],
) -> Tuple[int, List[str]]:
    with open(abs_path, "r", encoding="utf-8", errors="replace") as fh:
        text = fh.read()

    checked = 0
    problems: List[str] = []
    seen: Set[Tuple[int, str]] = set()
    for lineno, raw in extract_refs(text):
        ref = clean_ref(raw)
        if not ref or is_remote(raw) or looks_templated(ref):
            continue
        key = (lineno, ref)
        if key in seen:
            continue
        seen.add(key)
        checked += 1
        cands = candidates(ref, file_rel, public_dirs)
        if not any(c in tracked for c in cands):
            tried = ", ".join(cands)
            problems.append(
                f"{file_rel}:{lineno}: image '{ref}' resolves to no committed "
                f"file (tried: {tried})"
            )
    return checked, problems


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=".", help="repo root (default: .)")
    ap.add_argument(
        "--scan", default="docs/site",
        help="subtree under root to scan (default: docs/site)",
    )
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    root = os.path.abspath(args.root)
    scan_abs = os.path.join(root, args.scan)
    if not os.path.isdir(scan_abs):
        print(f"ERROR: scan path does not exist: {args.scan} (under {root})",
              file=sys.stderr)
        return 2

    try:
        tracked = git_tracked(root)
    except subprocess.CalledProcessError as exc:
        print(f"ERROR: not a git repo / git ls-files failed: {exc}", file=sys.stderr)
        return 2

    public_dirs = discover_public_dirs(root, args.scan)

    total_refs = 0
    total_files = 0
    problems: List[str] = []
    for dirpath, dirnames, filenames in os.walk(scan_abs):
        dirnames[:] = [d for d in dirnames if d not in (".git", "node_modules")]
        for name in filenames:
            if os.path.splitext(name)[1].lower() not in SCANNED_EXTS:
                continue
            abs_path = os.path.join(dirpath, name)
            file_rel = norm(os.path.relpath(abs_path, root))
            checked, file_problems = check_file(
                abs_path, file_rel, tracked, public_dirs
            )
            total_files += 1
            total_refs += checked
            problems.extend(file_problems)

    if problems:
        print("BROKEN LOCAL IMAGE REFERENCES:")
        for p in problems:
            print(f"  - {p}")
        print(
            f"\nFAIL: {len(problems)} broken image reference(s) across "
            f"{total_files} file(s)."
        )
        return 1

    if not args.quiet:
        pub = ", ".join(public_dirs) if public_dirs else "(none found)"
        print(
            f"OK: {total_refs} local image reference(s) across {total_files} "
            f"file(s) under {args.scan} all resolve to committed files."
        )
        print(f"     VitePress public dir(s): {pub}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
