#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

SPEC_PATH = Path(__file__).resolve().parents[1] / "config" / "a11oy-frontdoor" / "PATCH_SPEC.json"

MENU_TOGGLE_PREVIOUS = "  .menu-toggle{display:none;align-items:center;justify-content:center;width:44px;height:44px;min-width:44px;min-height:44px;padding:0;margin-left:auto;border:1px solid var(--border);border-radius:10px;background:rgba(255,255,255,0.04);color:var(--ink);cursor:pointer;font-size:20px;line-height:1}"
MENU_TOGGLE_FINAL = "  .menu-toggle{display:none;align-items:center;justify-content:center;width:48px;height:48px;min-width:48px;min-height:48px;padding:0;margin-left:auto;border:1px solid var(--border);border-radius:6px;background:rgba(255,255,255,0.04);color:var(--ink);cursor:pointer;font-size:20px;line-height:1}"

MEASURED_INTERMEDIATE = '<div class="leg measured"><div class="lt">MEASURED</div><p>Read live from a running endpoint this session — receipt count, separately reported signer state, advisory Λ posture, and chain depth. Shown with a live chip; a dead probe degrades to an honest offline chip.</p></div>'
MEASURED_FINAL = '<div class="leg measured"><div class="lt">MEASURED</div><p>Read live from a running endpoint this session — receipt count, advisory Λ posture, and chain depth. Shown with a live chip; a dead probe degrades to an honest offline chip. Signer state is disclosed separately only where an actual signer-status read is present.</p></div>'
MEASURED_NVIDIA = '<div class="leg measured"><div class="lt">MEASURED</div><p>Read live from a running endpoint this session — receipt count, advisory Λ posture, and chain depth. Shown with a live chip; a dead probe degrades to an honest offline chip. Signer state is disclosed separately only where an actual signer-status read is present. Never used for GPU joules without a live exporter delta.</p></div>'
MOBILE_INTERMEDIATE_BLOCK = '''  @media(max-width:560px){
    .wrap{padding-inline:16px}
    section.band{padding:64px 0}
    .hero{min-height:auto}
    .hero .wrap{padding-top:44px;padding-bottom:44px}
    .cta-row{display:grid;grid-template-columns:1fr;width:100%}
    .cta-row .btn{width:100%;white-space:normal;text-align:center}
    .card,.tier,.vcard,.cstat,.estate-cell{min-width:0}
  }
'''
MOBILE_FINAL_BLOCK = '''  @media(max-width:560px){
    .wrap{padding-inline:16px}
    section.band{padding-block:64px}
    .hero{min-height:auto}
    .hero .wrap{padding-top:32px;padding-bottom:44px}
    .cta-row{display:grid;grid-template-columns:1fr;width:100%}
    .cta-row .btn{width:100%;white-space:normal;text-align:center}
    .card,.tier,.vcard,.cstat,.estate-cell{min-width:0}
  }
'''
MOBILE_FINAL = (
    "  /* Mobile overrides intentionally follow all equal-specificity base rules. */\n"
    + MOBILE_FINAL_BLOCK
)
MOBILE_PREVIOUS_BLOCK = MOBILE_FINAL_BLOCK.replace(
    "padding-top:32px", "padding-top:44px"
)
MOBILE_PREVIOUS = (
    "  /* Mobile overrides intentionally follow all equal-specificity base rules. */\n"
    + MOBILE_PREVIOUS_BLOCK
)

REVIEWED_SUCCESSORS = {
    "measured_legend": MEASURED_NVIDIA,
    "mobile_layout_hardening": MOBILE_FINAL,
    "mobile_menu_hit_area": MENU_TOGGLE_FINAL,
}


class PatchError(RuntimeError):
    pass


def load_spec() -> dict:
    return json.loads(SPEC_PATH.read_text(encoding="utf-8"))


def _converge_reviewed_successors(text: str) -> str:
    if MEASURED_NVIDIA not in text:
        if text.count(MEASURED_FINAL) == 1:
            text = text.replace(MEASURED_FINAL, MEASURED_NVIDIA, 1)
        elif text.count(MEASURED_INTERMEDIATE) == 1:
            text = text.replace(MEASURED_INTERMEDIATE, MEASURED_NVIDIA, 1)
        else:
            raise PatchError("measured_legend: reviewed successor anchor is absent or ambiguous")

    previous_mobile_count = text.count(MOBILE_PREVIOUS)
    if MOBILE_FINAL not in text and previous_mobile_count == 1:
        text = text.replace(MOBILE_PREVIOUS, MOBILE_FINAL, 1)
    elif MOBILE_FINAL not in text and previous_mobile_count > 1:
        raise PatchError(
            "mobile_layout_hardening: previous successor is duplicated"
        )

    if MOBILE_FINAL not in text:
        late_intermediate = (
            "  /* Mobile overrides intentionally follow all equal-specificity base rules. */\n"
            + MOBILE_INTERMEDIATE_BLOCK
        )
        if late_intermediate in text:
            if text.count(late_intermediate) != 1:
                raise PatchError("mobile_layout_hardening: intermediate successor is duplicated")
            text = text.replace(late_intermediate, MOBILE_FINAL, 1)
        elif text.count(MOBILE_INTERMEDIATE_BLOCK) == 1:
            text = text.replace(MOBILE_INTERMEDIATE_BLOCK, "", 1)
            if text.count("</style>") != 1:
                raise PatchError("mobile_layout_hardening: expected exactly one </style> insertion anchor")
            text = text.replace("</style>", MOBILE_FINAL + "</style>", 1)
        else:
            raise PatchError("mobile_layout_hardening: reviewed successor anchor is absent or ambiguous")

    return text


def apply_text(text: str, spec: dict) -> tuple[str, list[dict]]:
    results: list[dict] = []
    for item in spec["replacements"]:
        old, new, name = item["old"], item["new"], item["name"]
        successor = REVIEWED_SUCCESSORS.get(name)
        successor_count = text.count(successor) if successor else 0
        previous_successor = (
            MOBILE_PREVIOUS if name == "mobile_layout_hardening" else None
        )
        previous_successor_count = (
            text.count(previous_successor) if previous_successor else 0
        )
        if successor_count == 1:
            results.append({"name": name, "state": "REVIEWED_SUCCESSOR"})
            continue
        if successor_count > 1:
            raise PatchError(f"{name}: reviewed successor is duplicated ({successor_count})")
        if previous_successor_count == 1:
            results.append(
                {"name": name, "state": "REVIEWED_PREVIOUS_SUCCESSOR"}
            )
            continue
        if previous_successor_count > 1:
            raise PatchError(
                f"{name}: previous reviewed successor is duplicated "
                f"({previous_successor_count})"
            )

        old_count = text.count(old)
        new_count = text.count(new)
        if new_count == 1:
            results.append({"name": name, "state": "ALREADY_APPLIED"})
        elif old_count == 1:
            text = text.replace(old, new, 1)
            results.append({"name": name, "state": "APPLIED"})
        else:
            raise PatchError(
                f"{name}: expected one old anchor, one new anchor, or one reviewed successor; "
                f"old={old_count} new={new_count} successor={successor_count}"
            )

    text = _converge_reviewed_successors(text)
    return text, results


def validate_truth(text: str) -> list[str]:
    errors: list[str] = []
    banned = [
        "Every answer arrives with a signed receipt",
        "every governed decision is sealed into a signed, hash-chained receipt",
        "signed receipts travel the vessels",
        ">Signed receipts</div>",
        "const pass = v >= 0.90",
        "pass?'≥ floor':'below floor'",
        "snapshot observed 2026-07-16",
        '<div class="estate-cell"><b>15</b><span>Models</span></div>',
        '<div class="estate-cell"><b>24</b><span>Datasets</span></div>',
        '<div class="estate-cell"><b>26</b><span>Spaces</span></div>',
        '<div class="estate-cell"><b>22</b><span>Collections</span></div>',
        MEASURED_INTERMEDIATE,
        MOBILE_INTERMEDIATE_BLOCK,
        MOBILE_PREVIOUS,
        MENU_TOGGLE_PREVIOUS,
    ]
    for token in banned:
        if token in text:
            errors.append("banned token remains: " + token)

    required = [
        "proves its receipt state",
        "signer state",
        "verification passes",
        'grayChip(relation + " · CONJECTURE")',
        "Receipt records · signer state separate",
        "min-height:44px",
        "overflow-wrap:anywhere",
        "Hub collections are a catalog, not a zoo",
        MEASURED_NVIDIA,
        MOBILE_FINAL,
    ]
    for token in required:
        if token not in text:
            errors.append("required token missing: " + token)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    spec = load_spec()
    original = args.path.read_text(encoding="utf-8")
    if args.check:
        baseline_errors = validate_truth(original)
        if not baseline_errors:
            print(
                json.dumps(
                    {
                        "status": "PASS",
                        "target": str(args.path),
                        "notes": "frontdoor truth contract already current",
                    },
                    indent=2,
                )
            )
            return 0
    try:
        patched, results = apply_text(original, spec)
    except PatchError as exc:
        print(json.dumps({"status": "BLOCKED_DRIFT", "error": str(exc)}, indent=2))
        return 2

    errors = validate_truth(patched)
    if errors:
        print(json.dumps({"status": "FAIL", "errors": errors, "results": results}, indent=2))
        return 1

    changed = patched != original
    pending = [item["name"] for item in results if item["state"] == "APPLIED"]
    if args.check and (pending or changed):
        print(
            json.dumps(
                {
                    "status": "FAIL_UNAPPLIED",
                    "target": str(args.path),
                    "pending_replacements": pending,
                    "review_successor_change_required": changed,
                    "results": results,
                },
                indent=2,
            )
        )
        return 1

    if not args.check:
        out = args.output or args.path
        out.write_text(patched, encoding="utf-8")

    print(
        json.dumps(
            {
                "status": "PASS",
                "target": str(args.path),
                "output": str(args.output or args.path),
                "results": results,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
