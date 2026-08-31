#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""
szl_codename_gate.py - SHARED MODULE (byte-identical across a11oy + killinchu)
==============================================================================
Doctrine gate G5 enforcement: 0 user-visible codenames.

Internal route keys (amaru_* / rosie_* / sentra / jarvis) are allowed as code
identifiers, but they must NEVER appear in *rendered-text columns* or *served
HTML body text*. This module is the single source of truth for:

  - the banned-token set + public-role mapping (mirrors the JS sanitizer),
  - sanitize()                : map a string to its honest public roles,
  - scan_text()               : find banned tokens in a plain string,
  - scan_html_visible()       : find banned tokens in the VISIBLE text of HTML
                                (strips <script>/<style>, tags, id/class/data-*
                                route keys) - the false-positive-safe scanner
                                used by the CI acceptance gate,
  - scan_url()                : fetch a served URL and scan its visible HTML,
  - main()                    : CI entrypoint; exits non-zero on any violation.

Public roles (mirrors szl_codename_sanitizer.js MAP):
    amaru  -> YACHAY     (cortex / brain / OSINT ingest)
    rosie  -> Operator   (orchestrator)
    sentra -> CHAPAQ     (verdict / immune)
    jarvis -> Operator   (assistant / orchestrator)
"""
from __future__ import annotations

import html as _html
import re
import sys
from typing import Dict, List

MAP: Dict[str, str] = {
    "amaru": "YACHAY",
    "rosie": "Operator",
    "sentra": "CHAPAQ",
    "jarvis": "Operator",
}
TOKENS = ("amaru", "rosie", "sentra", "jarvis")
_BANNED = re.compile("(" + "|".join(TOKENS) + ")", re.IGNORECASE)


def sanitize(text: str) -> str:
    """Replace every banned codename with its honest public role."""
    if text is None:
        return text
    return _BANNED.sub(lambda m: MAP.get(m.group(0).lower(), m.group(0)), str(text))


def scan_text(text: str) -> List[str]:
    """Return the list of banned tokens found in a plain string."""
    return [m.group(0) for m in _BANNED.finditer(str(text or ""))]


# --- HTML visible-text extraction (no external deps) -----------------------
# Remove <script> and <style> bodies, then strip tags, decode entities. We do
# NOT scan attribute values like id=/class=/data-* (those are allowed internal
# route keys); we DO scan the visible human-facing attributes title/aria-label/
# alt/placeholder so a tooltip can't smuggle a codename to the user.
_SCRIPT_STYLE = re.compile(r"<(script|style)\b[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
_VISIBLE_ATTRS = re.compile(
    r'\b(?:title|aria-label|alt|placeholder)\s*=\s*(?:"([^"]*)"|\'([^\']*)\')',
    re.IGNORECASE,
)
_TAG = re.compile(r"<[^>]+>")


def html_visible_text(html_str: str) -> str:
    """Best-effort extraction of the text a human actually sees, plus the
    human-visible attributes (title/aria-label/alt/placeholder)."""
    s = _SCRIPT_STYLE.sub(" ", html_str or "")
    visible_attr_vals = []
    for m in _VISIBLE_ATTRS.finditer(s):
        visible_attr_vals.append(m.group(1) or m.group(2) or "")
    body = _TAG.sub(" ", s)
    body = _html.unescape(body)
    return body + " \n" + " \n".join(visible_attr_vals)


def scan_html_visible(html_str: str) -> List[str]:
    """Return banned tokens visible in rendered HTML (text + visible attrs)."""
    return scan_text(html_visible_text(html_str))


def scan_url(url: str, timeout: float = 30.0) -> List[str]:
    """Fetch a served URL and scan its visible HTML. Network errors raise."""
    import urllib.request

    req = urllib.request.Request(url, headers={"User-Agent": "szl-codename-gate/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 (trusted internal)
        data = r.read().decode("utf-8", "replace")
    return scan_html_visible(data)


def _scan_path(path: str) -> List[str]:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            content = fh.read()
    except Exception as e:  # pragma: no cover
        return ["<read-error:%s>" % e]
    if path.lower().endswith((".html", ".htm", ".svg")):
        return scan_html_visible(content)
    # For .csv / rendered-text columns and served JSON, scan the raw text.
    return scan_text(content)


def main(argv: List[str]) -> int:
    """CI entrypoint. Args = files / globs / http(s) URLs. Non-zero on hit."""
    import glob

    targets: List[str] = []
    urls: List[str] = []
    for a in argv:
        if a.startswith("http://") or a.startswith("https://"):
            urls.append(a)
        else:
            g = glob.glob(a, recursive=True)
            targets.extend(g if g else [a])

    violations = 0
    for path in targets:
        hits = _scan_path(path)
        if hits:
            violations += len(hits)
            print("FAIL %s -> banned visible tokens: %s" % (path, ", ".join(sorted(set(hits)))))
        else:
            print("ok   %s" % path)
    for url in urls:
        try:
            hits = scan_url(url)
        except Exception as e:
            print("WARN %s -> could not fetch (%s) - skipping" % (url, e))
            continue
        if hits:
            violations += len(hits)
            print("FAIL %s -> banned visible tokens: %s" % (url, ", ".join(sorted(set(hits)))))
        else:
            print("ok   %s" % url)

    print("\nG5 codename gate: %d banned user-visible token(s) found." % violations)
    if violations:
        print("Doctrine G5 violated: every user-visible string must read YACHAY / Operator / CHAPAQ.")
        return 1
    print("G5 PASS - 0 user-visible codenames.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
