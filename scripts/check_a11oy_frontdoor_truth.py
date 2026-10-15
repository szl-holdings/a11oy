#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path


def _function_body(text: str, signature: str) -> str | None:
    start = text.find(signature)
    if start < 0:
        return None
    open_brace = text.find("{", start + len(signature))
    if open_brace < 0:
        return None
    depth = 0
    quote: str | None = None
    escaped = False
    for index in range(open_brace, len(text)):
        char = text[index]
        if quote is not None:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in ("'", '"', "`"):
            quote = char
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[open_brace + 1 : index]
    return None


class _Links(HTMLParser):
    def __init__(self, text: str):
        super().__init__()
        self.links: list[dict[str, str | None]] = []
        self.feed(text)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "link":
            self.links.append(dict(attrs))


def _owned_css(path: Path, text: str, errors: list[dict]) -> str:
    """Only the reviewed local projection is eligible; never fetch an arbitrary href."""
    links = _Links(text).links
    owners = [row for row in links if row.get("id") == "szl-homepage-shell"]
    expected = "/assets/a11oy-homepage.css?v=dab2353006c8"
    if len(owners) != 1 or owners[0].get("href") != expected or owners[0].get("rel") != "stylesheet":
        errors.append({"check": "visual-owner", "detail": "one exact local stylesheet binding required"})
        return ""
    canonical = [i for i, row in enumerate(links) if row.get("href") == "/assets/szl/szl-design-system.css" and row.get("rel") == "stylesheet"]
    if len(canonical) != 1 or canonical[0] >= links.index(owners[0]):
        errors.append({"check": "visual-owner", "detail": "canonical design system must precede owned sheet"})
    css_path = path.parent / "console/assets/a11oy-homepage.css"
    inside_checkout = css_path.resolve().is_relative_to(path.parent.resolve())
    if not inside_checkout or css_path.is_symlink() or not css_path.is_file() or css_path.stat().st_size > 100_000:
        errors.append({"check": "visual-owner", "detail": "owned stylesheet unavailable or outside size contract"})
        return ""
    css = css_path.read_text(encoding="utf-8")
    required = (
        'html[data-szl-shell-owner="homepage"]',
        "var(--text)", "var(--text-sub)", "var(--font-display)",
        "var(--action-bg)", "var(--action-hover-bg)", "var(--action-press-bg)",
        "overflow:visible !important", "@media(prefers-reduced-motion:reduce)",
        "@media(forced-colors:active)",
        ".cta-row .btn{width:100%;min-height:52px;border-radius:6px;white-space:normal;text-align:center}",
    )
    for token in required:
        if token not in css:
            errors.append({"check": "owned-style-contract", "detail": token})
    mobile = css.find("@media(max-width:480px)")
    for token in (".hero-grid {", ".cta-row {", ".band,.honesty"):
        base = css.find(token)
        if base < 0 or mobile < base:
            errors.append({"check": "mobile-cascade-order", "detail": f"mobile reflow must follow {token}"})
    if re.search(r"#[0-9a-fA-F]{3,8}\b|@font-face|https?://", re.sub(r"/\*.*?\*/", "", css, flags=re.S)):
        # A literal proof URL in print-only content is permitted, but imported
        # styles, downloaded fonts and palette forks are never admitted here.
        stripped = css.replace('content:"The full source record is available at https://a-11-oy.com/#full-record"', "")
        if re.search(r"#[0-9a-fA-F]{3,8}\b|@font-face|https?://", re.sub(r"/\*.*?\*/", "", stripped, flags=re.S)):
            errors.append({"check": "owned-style-contract", "detail": "palette fork, font download or remote style reference"})
    return css


def check(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    errors: list[dict] = []
    banned = {
        "unconditional signed-answer claim": "Every answer arrives with a signed receipt",
        "unconditional signed-decision claim": "every governed decision is sealed into a signed, hash-chained receipt",
        "signed pulse overclaim": "signed receipts travel the vessels",
        "stale July inventory": "snapshot observed 2026-07-16",
        "green advisory branch": "const pass = v >= 0.90",
        "unconditional product slogan": "AI that signs its work",
        "unconditional signed metric": "signed-receipt count",
        "unconditional signed plural": "signed receipts",
        "unconditional signed decision": "signed receipt per decision",
        "unconditional finance signing": "signed after the fact",
        "unconditional receipt signing doctrine": "Receipts are signed on",
        "unconditional DSSE state": "DSSE receipts, ECDSA-P256 signed",
        "unmeasured signer state in measured legend": "receipt count, separately reported signer state, advisory Λ posture",
    }
    for name, token in banned.items():
        if token in text:
            errors.append({"check": name, "token": token})

    estate = re.search(
        r'<section\b[^>]*\bid="ecosystem"[^>]*>(.*?)</section>',
        text,
        re.S | re.I,
    )
    if not estate:
        errors.append({"check": "ecosystem-section", "detail": "missing"})
    else:
        block = estate.group(1)
        if re.search(r'<b>\d+</b><span>(Models|Datasets|Spaces|Collections)', block):
            errors.append({"check": "hardcoded-estate-counts", "detail": "numeric totals remain"})

    block = _function_body(text, "function lamChip(elId, v)")
    if block is None:
        errors.append({"check": "lambda-chip", "detail": "function missing or unbalanced"})
    else:
        if "var(--ok)" in block or "pass" in block or "liveChip" in block:
            errors.append({"check": "lambda-chip", "detail": "advisory chip can render pass/live/green"})
        if "CONJECTURE" not in block or "grayChip" not in block:
            errors.append({"check": "lambda-chip", "detail": "advisory/conjecture gray rendering missing"})

    canonical_owner = 'id="szl-homepage-shell"' in text or (
        'data-surface="light"' in text and 'data-szl-shell-owner="homepage"' in text
    )
    css = _owned_css(path, text, errors) if canonical_owner else ""
    if not canonical_owner:
        # Historical repair fixtures still retain their original admission path.
        mobile_marker = "/* Mobile overrides intentionally follow all equal-specificity base rules. */"
        mobile_index = text.find(mobile_marker)
        if mobile_index < 0:
            errors.append({"check": "mobile-cascade-order", "detail": "late mobile override marker missing"})
        else:
            for token in (
                ".hero{position:relative;min-height:92vh",
                ".hero .wrap{position:relative;z-index:2;padding-top:54px",
                ".cta-row{display:flex;gap:12px",
                "section.band{padding:88px 0;position:relative}",
            ):
                base_index = text.find(token)
                if base_index < 0:
                    errors.append({"check": "mobile-cascade-order", "detail": f"base rule missing: {token}"})
                elif mobile_index <= base_index:
                    errors.append({"check": "mobile-cascade-order", "detail": f"mobile override precedes base rule: {token}"})

    required = [
        "min-height:44px",
        "overflow-wrap:anywhere",
        "Receipt records · signer state separate",
        "Signer state is disclosed separately only where an actual signer-status read is present.",
    ]
    for token in required:
        if token not in text + css:
            errors.append({"check": "required-contract", "detail": token})

    return {
        "schema": "a11oy.frontdoor-truth-mobile-check/v1",
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
    }


def main() -> int:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "a11oy_landing.html")
    report = check(path)
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
