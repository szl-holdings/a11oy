#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
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
        if token not in text:
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
