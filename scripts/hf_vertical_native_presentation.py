# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Stephen P. Lutar Jr. / SZL Holdings
"""Presentation-only projection of the four established vertical front doors.

The canonical token prefix and Orbit icon are verified against their existing
source records. No runtime scripts, source labels, forms, or publication targets
are rewritten. This module runs in the existing generator, not in the Space.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys

ROOT = Path(__file__).resolve().parents[1]
VERSION = "szl.vertical-native-presentation/v1"
SLUGS = frozenset({"counsel", "terra", "finance", "sentra"})
TOKEN_END = "/* --- 5 · BASE / RESET"
ART_REVISION = "27d12e77fc0f9f1a0e5fae8b34adf2380d51d070"


def _read(relative: str, limit: int = 200_000) -> bytes:
    # All callers below supply literal source-owned paths, never runtime input.
    fd = os.open(ROOT, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        parts = relative.split("/")
        for part in parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            previous, fd = fd, child
            os.close(previous)
        leaf = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd)
        try:
            info = os.fstat(leaf)
            if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
                raise ValueError("native presentation source must be bounded regular bytes")
            chunks, size = [], 0
            while True:
                chunk = os.read(leaf, min(65536, limit + 1 - size))
                if not chunk:
                    break
                chunks.append(chunk)
                size += len(chunk)
                if size > limit:
                    raise ValueError("native presentation source exceeds bound")
            data = b"".join(chunks)
            # Emit the exact logical source path only after a bounded regular
            # file has been read successfully. The convergence audit uses this
            # event instead of mistaking secure openat directory components for
            # independent content inputs.
            sys.audit("szl.vertical_native.read", relative)
            return data
        finally:
            os.close(leaf)
    finally:
        os.close(fd)


def assets() -> tuple[str, str]:
    sheet = _read("console/assets/szl/szl-design-system.css")
    source = json.loads(_read("console/assets/szl/SOURCE.json"))
    icon = _read("console/assets/szl/orbit-v2/szl-icon-32.svg")
    art = json.loads(_read("console/assets/szl/orbit-v2/UPSTREAM.json"))
    if hashlib.sha256(sheet).hexdigest() != source["sha256"]["szl-design-system.css"]:
        raise ValueError("canonical design source checksum mismatch")
    if hashlib.sha256(icon).hexdigest() != art["sha256"] or art["source_commit"] != ART_REVISION:
        raise ValueError("canonical Orbit source checksum mismatch")
    text = sheet.decode("utf-8")
    if text.count(TOKEN_END) != 1:
        raise ValueError("canonical token boundary unavailable")
    # Preserve the exact canonical prefix; omit the unrelated global components.
    tokens = text.split(TOKEN_END, 1)[0]
    return tokens, "data:image/svg+xml;base64," + base64.b64encode(icon).decode("ascii")


def _once(page: str, old: str, new: str) -> str:
    if page.count(old) != 1:
        raise ValueError("vertical presentation insertion boundary changed")
    return page.replace(old, new, 1)


def present(page: str, slug: str, *, forge: bool = False) -> str:
    if slug not in SLUGS:
        return page
    if 'data-szl-native-vertical=' in page:
        raise ValueError("native presentation may only be applied once")
    original_scripts = re.findall(r"<script\b[^>]*>.*?</script>", page, re.S | re.I)
    tokens, icon = assets()
    css = _read("scripts/hf_vertical_native.css").decode("utf-8")
    polarity = "light" if slug == "counsel" else "dark"
    page = _once(page, '<html lang="en"', '<html lang="en" data-szl-native-vertical="v1" '
                 f'data-surface="{polarity}" data-native-domain="{slug}"')
    page = _once(page, "</head>", f'<style id="szl-native-tokens">{tokens}</style>'
                 f'<style id="szl-native-vertical">{css}</style></head>')
    page = _once(page, "<body>", '<body><a class="native-skip" href="#native-main">Skip to workspace</a>')
    main = "<main>" if forge else '<main class="shell">'
    page = _once(page, main, main[:-1] + ' id="native-main" tabindex="-1">')
    identity = (f'<div class="native-identity"><img src="{icon}" width="40" height="40" '
                'alt="SZL Holdings"><span>SZL HOLDINGS<span class="native-family">A11oy · '
                + ("CHAPAQ" if slug == "sentra" else slug.title()) + '</span></span></div>')
    if forge:
        page = _once(page, '<div class="kicker">', identity + '<div class="kicker">')
    else:
        start = '<header class="top"><div class="brand">'
        page = _once(page, start, '<header class="top">' + identity + '<div class="brand">')
    if forge:
        page = _once(page, 'id="livepill"', 'id="livepill" role="status" aria-live="polite" aria-atomic="true"')
        page = _once(page, 'id="demodata"', 'id="demodata" tabindex="0" aria-label="Runtime observation JSON"')
        page = _once(page, '<div class="panel"><h2>Runtime observation</h2>', '<div class="panel" id="native-observation"><h2>Runtime observation</h2>')
        page = _once(page, '<div class="panel"><h2>Estate wiring</h2>', '<div class="panel" id="native-wiring"><h2>Estate wiring</h2>')
        nav = '<nav class="native-nav" aria-label="Workspace sections"><a href="#native-observation">Runtime observation</a><a href="#native-wiring">Source wiring</a></nav>'
    else:
        page = _once(page, '<div id="st"', '<div id="st" role="status" aria-live="polite" aria-atomic="true"')
        page = _once(page, '<pre id="out"', '<pre id="out" tabindex="0" aria-label="Governed evidence JSON"')
        page = _once(page, '<section class="panel" style="margin-top:14px">', '<section class="panel" id="native-evidence" aria-label="Governed evidence" style="margin-top:14px">')
        links = [("#native-evidence", "Evidence status")]
        if slug == "finance":
            links = [("#fin-signed", "Signed prices"), ("#fin-research", "Research audit"),
                     ("#fin-desk", "Source workbench"), ("#fin-analytics", "Advisory analytics"), *links]
        elif slug == "sentra":
            links.insert(0, ("#sentra-verifier-handoff", "Open CHAPAQ verifier"))
        nav = '<nav class="native-nav" aria-label="Workspace sections">' + ''.join(
            f'<a href="{target}">{label}</a>' for target, label in links) + '</nav>'
    notice = '<noscript><p class="native-noscript">JavaScript is disabled. No runtime observation has been made in this page. Source links remain available; interactive tools require JavaScript.</p></noscript>'
    # The index comes before the hero and never triggers a provider request.
    if forge:
        page = _once(page, '<div class="kicker">', nav + notice + '<div class="kicker">')
    else:
        page = _once(page, '</header>', '</header>' + nav + notice)
    credit = ('<div class="native-credit">Orbit v2 artwork © Stephen P. Lutar Jr. / SZL Holdings · '
              '<a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a> · '
              f'<a href="https://github.com/szl-holdings/szl-brand/blob/{ART_REVISION}/NOTICE">Trademark notice</a>'
              '<span>Presentation does not change source, evidence, or authorization state.</span></div>')
    if forge:
        credit = credit.replace('</div>', '<span>Terra retains the sealed Forge 0.2.2 base; this page is a presentation derived from it. The build receipt distinguishes both artifact hashes.</span></div>')
    page = _once(page, "</main>", credit + "</main>")
    if original_scripts != re.findall(r"<script\b[^>]*>.*?</script>", page, re.S | re.I):
        raise ValueError("native presentation changed an operational script")
    return page


def derive_forge(page: str, forge: dict) -> tuple[str, dict]:
    """Retain the verified original chain and explicitly describe derived bytes."""
    derived = present(page, "terra", forge=True)
    return derived, {**forge, "presentation": {
        "schema": VERSION,
        "source_path": "scripts/hf_vertical_native_presentation.py",
        "base_artifact_sha256": hashlib.sha256(page.encode()).hexdigest(),
        "derived_landing_sha256": hashlib.sha256(derived.encode()).hexdigest(),
        "scope": "presentation only; original Forge chain remains the base artifact",
    }}
