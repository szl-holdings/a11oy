#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

EARLY_MOBILE = '''  @media(max-width:560px){
    .wrap{padding-inline:16px}
    section.band{padding:64px 0}
    .hero{min-height:auto}
    .hero .wrap{padding-top:44px;padding-bottom:44px}
    .cta-row{display:grid;grid-template-columns:1fr;width:100%}
    .cta-row .btn{width:100%;white-space:normal;text-align:center}
    .card,.tier,.vcard,.cstat,.estate-cell{min-width:0}
  }
'''

LATE_MOBILE = '''  /* Mobile overrides intentionally follow all equal-specificity base rules. */
  @media(max-width:560px){
    .wrap{padding-inline:16px}
    section.band{padding:64px 0}
    .hero{min-height:auto}
    .hero .wrap{padding-top:44px;padding-bottom:44px}
    .cta-row{display:grid;grid-template-columns:1fr;width:100%}
    .cta-row .btn{width:100%;white-space:normal;text-align:center}
    .card,.tier,.vcard,.cstat,.estate-cell{min-width:0}
  }
'''

MEASURED_OLD = '<div class="leg measured"><div class="lt">MEASURED</div><p>Read live from a running endpoint this session — receipt count, separately reported signer state, advisory Λ posture, and chain depth. Shown with a live chip; a dead probe degrades to an honest offline chip.</p></div>'
MEASURED_NEW = '<div class="leg measured"><div class="lt">MEASURED</div><p>Read live from a running endpoint this session — receipt count, advisory Λ posture, and chain depth. Shown with a live chip; a dead probe degrades to an honest offline chip. Signer state is disclosed separately only where an actual signer-status read is present.</p></div>'


def apply(text: str) -> tuple[str, list[str]]:
    changes: list[str] = []

    if LATE_MOBILE not in text:
        if text.count(EARLY_MOBILE) != 1:
            raise RuntimeError(
                f"expected one early mobile block before migration; found {text.count(EARLY_MOBILE)}"
            )
        text = text.replace(EARLY_MOBILE, "", 1)
        if text.count("</style>") != 1:
            raise RuntimeError(f"expected one </style> anchor; found {text.count('</style>')}")
        text = text.replace("</style>", LATE_MOBILE + "</style>", 1)
        changes.append("mobile-cascade-order")
    elif EARLY_MOBILE in text:
        raise RuntimeError("both early and late mobile override blocks are present")

    if MEASURED_NEW not in text:
        if text.count(MEASURED_OLD) != 1:
            raise RuntimeError(
                f"expected one measured legend anchor; found {text.count(MEASURED_OLD)}"
            )
        text = text.replace(MEASURED_OLD, MEASURED_NEW, 1)
        changes.append("measured-signer-wording")

    validate(text)
    return text, changes


def validate(text: str) -> None:
    if EARLY_MOBILE in text:
        raise RuntimeError("mobile overrides remain before base rules")
    if text.count(LATE_MOBILE) != 1:
        raise RuntimeError("late mobile override block must exist exactly once")
    if MEASURED_OLD in text or text.count(MEASURED_NEW) != 1:
        raise RuntimeError("measured signer-state wording is not truthful")

    mobile_index = text.index(LATE_MOBILE)
    for token in (
        ".hero{position:relative;min-height:92vh",
        ".hero .wrap{position:relative;z-index:2;padding-top:54px",
        ".cta-row{display:flex;gap:12px",
        "section.band{padding:88px 0;position:relative}",
    ):
        base_index = text.find(token)
        if base_index < 0:
            raise RuntimeError(f"missing base CSS anchor: {token}")
        if mobile_index <= base_index:
            raise RuntimeError(f"mobile override must follow base rule: {token}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    original = args.path.read_text(encoding="utf-8")
    patched, changes = apply(original)
    if args.check and changes:
        print("FAIL_UNAPPLIED: " + ", ".join(changes))
        return 1
    if not args.check:
        args.path.write_text(patched, encoding="utf-8")
    print("PASS: " + (", ".join(changes) if changes else "already applied"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
