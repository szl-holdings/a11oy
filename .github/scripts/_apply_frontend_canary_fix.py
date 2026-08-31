#!/usr/bin/env python3
"""Apply the exact live-canary repair, validate it, then remove bootstrap files."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LANDING = ROOT / "a11oy_landing.html"
PATCH_SPEC = ROOT / "config" / "a11oy-frontdoor" / "PATCH_SPEC.json"
REPAIR = ROOT / "scripts" / "repair_a11oy_frontdoor.py"
CANARY_TEST = ROOT / "tests" / "test_hf_frontend_live_canary_v1.py"
SELF = ROOT / ".github" / "scripts" / "_apply_frontend_canary_fix.py"
WORKFLOW = ROOT / ".github" / "workflows" / "_bootstrap-frontend-canary-fix.yml"

MENU_PREVIOUS = "  .menu-toggle{display:none;align-items:center;justify-content:center;width:44px;height:44px;min-width:44px;min-height:44px;padding:0;margin-left:auto;border:1px solid var(--border);border-radius:10px;background:rgba(255,255,255,0.04);color:var(--ink);cursor:pointer;font-size:20px;line-height:1}"
MENU_FINAL = "  .menu-toggle{display:none;align-items:center;justify-content:center;width:48px;height:48px;min-width:48px;min-height:48px;padding:0;margin-left:auto;border:1px solid var(--border);border-radius:6px;background:rgba(255,255,255,0.04);color:var(--ink);cursor:pointer;font-size:20px;line-height:1}"
MOBILE_TOP_PREVIOUS = ".hero .wrap{padding-top:44px;padding-bottom:44px}"
MOBILE_TOP_FINAL = ".hero .wrap{padding-top:32px;padding-bottom:44px}"
TEST_NAME = "test_landing_mobile_controls_reserve_a_full_live_canary_hit_area"


class RepairError(RuntimeError):
    pass


def replace_once_or_accept(path: Path, previous: str, final: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    previous_count = text.count(previous)
    final_count = text.count(final)
    if final_count == 1 and previous_count == 0:
        return
    if previous_count != 1 or final_count != 0:
        raise RepairError(
            f"{label}: expected one previous anchor or one final anchor; "
            f"previous={previous_count} final={final_count}"
        )
    path.write_text(text.replace(previous, final, 1), encoding="utf-8")


def patch_landing() -> None:
    replace_once_or_accept(
        LANDING,
        MENU_PREVIOUS,
        MENU_FINAL,
        "landing mobile menu target",
    )
    replace_once_or_accept(
        LANDING,
        MOBILE_TOP_PREVIOUS,
        MOBILE_TOP_FINAL,
        "landing mobile hero position",
    )


def patch_spec() -> None:
    text = PATCH_SPEC.read_text(encoding="utf-8")
    if TEST_NAME in text:
        raise RepairError("unexpected test marker in patch specification")

    if MOBILE_TOP_FINAL not in text:
        count = text.count(MOBILE_TOP_PREVIOUS)
        if count != 1:
            raise RepairError(
                "patch specification mobile top anchor is absent or ambiguous: "
                f"count={count}"
            )
        text = text.replace(MOBILE_TOP_PREVIOUS, MOBILE_TOP_FINAL, 1)

    payload = json.loads(text)
    replacements = payload.get("replacements")
    if not isinstance(replacements, list):
        raise RepairError("patch specification has no replacements list")

    named = [item for item in replacements if item.get("name") == "mobile_menu_hit_area"]
    if not named:
        entry = {
            "name": "mobile_menu_hit_area",
            "old": MENU_PREVIOUS,
            "new": MENU_FINAL,
        }
        anchor = '  "replacements": [\n'
        if text.count(anchor) != 1:
            raise RepairError("patch specification insertion anchor is absent or ambiguous")
        compact = "    " + json.dumps(
            entry,
            ensure_ascii=False,
            separators=(",", ":"),
        ) + ",\n"
        text = text.replace(anchor, anchor + compact, 1)
    elif len(named) == 1:
        if named[0].get("old") != MENU_PREVIOUS or named[0].get("new") != MENU_FINAL:
            raise RepairError("existing mobile_menu_hit_area replacement is not canonical")
    else:
        raise RepairError("mobile_menu_hit_area replacement is duplicated")

    validated = json.loads(text)
    names = [item.get("name") for item in validated["replacements"]]
    if len(names) != len(set(names)):
        raise RepairError("patch specification replacement names are not unique")
    mobile = next(
        item for item in validated["replacements"]
        if item.get("name") == "mobile_layout_hardening"
    )
    if MOBILE_TOP_FINAL not in mobile.get("new", ""):
        raise RepairError("mobile_layout_hardening does not carry the final hero position")
    PATCH_SPEC.write_text(text, encoding="utf-8")


def patch_repair_script() -> None:
    text = REPAIR.read_text(encoding="utf-8")

    constants_anchor = (
        'SPEC_PATH = Path(__file__).resolve().parents[1] / "config" / '
        '"a11oy-frontdoor" / "PATCH_SPEC.json"\n'
    )
    if "MENU_TOGGLE_FINAL =" not in text:
        if text.count(constants_anchor) != 1:
            raise RepairError("repair-script constants anchor is absent or ambiguous")
        constants = (
            constants_anchor
            + f"\nMENU_TOGGLE_PREVIOUS = {json.dumps(MENU_PREVIOUS)}\n"
            + f"MENU_TOGGLE_FINAL = {json.dumps(MENU_FINAL)}\n"
        )
        text = text.replace(constants_anchor, constants, 1)

    block_start_token = "MOBILE_FINAL_BLOCK = '''"
    block_start = text.find(block_start_token)
    if block_start < 0:
        raise RepairError("MOBILE_FINAL_BLOCK is absent")
    block_end = text.find("'''", block_start + len(block_start_token))
    if block_end < 0:
        raise RepairError("MOBILE_FINAL_BLOCK terminator is absent")
    block = text[block_start:block_end]
    if MOBILE_TOP_FINAL not in block:
        if block.count(MOBILE_TOP_PREVIOUS) != 1:
            raise RepairError("MOBILE_FINAL_BLOCK previous hero position is absent or ambiguous")
        block = block.replace(MOBILE_TOP_PREVIOUS, MOBILE_TOP_FINAL, 1)
        text = text[:block_start] + block + text[block_end:]

    prior_definition = '''MOBILE_FINAL = (
    "  /* Mobile overrides intentionally follow all equal-specificity base rules. */\\n"
    + MOBILE_FINAL_BLOCK
)
'''
    previous_definition = '''MOBILE_PREVIOUS_BLOCK = MOBILE_FINAL_BLOCK.replace(
    "padding-top:32px", "padding-top:44px"
)
MOBILE_PREVIOUS = (
    "  /* Mobile overrides intentionally follow all equal-specificity base rules. */\\n"
    + MOBILE_PREVIOUS_BLOCK
)
'''
    if "MOBILE_PREVIOUS_BLOCK =" not in text:
        if text.count(prior_definition) != 1:
            raise RepairError("MOBILE_FINAL definition anchor is absent or ambiguous")
        text = text.replace(
            prior_definition,
            prior_definition + previous_definition,
            1,
        )

    reviewed_anchor = '''REVIEWED_SUCCESSORS = {
    "measured_legend": MEASURED_NVIDIA,
    "mobile_layout_hardening": MOBILE_FINAL,
}
'''
    reviewed_final = '''REVIEWED_SUCCESSORS = {
    "measured_legend": MEASURED_NVIDIA,
    "mobile_layout_hardening": MOBILE_FINAL,
    "mobile_menu_hit_area": MENU_TOGGLE_FINAL,
}
'''
    if reviewed_final not in text:
        if text.count(reviewed_anchor) != 1:
            raise RepairError("REVIEWED_SUCCESSORS anchor is absent or ambiguous")
        text = text.replace(reviewed_anchor, reviewed_final, 1)

    apply_anchor = '''        successor = REVIEWED_SUCCESSORS.get(name)
        successor_count = text.count(successor) if successor else 0
        if successor_count == 1:
'''
    apply_final = '''        successor = REVIEWED_SUCCESSORS.get(name)
        successor_count = text.count(successor) if successor else 0
        previous_successor = (
            MOBILE_PREVIOUS if name == "mobile_layout_hardening" else None
        )
        previous_successor_count = (
            text.count(previous_successor) if previous_successor else 0
        )
        if successor_count == 1:
'''
    if "previous_successor_count =" not in text:
        if text.count(apply_anchor) != 1:
            raise RepairError("apply_text successor anchor is absent or ambiguous")
        text = text.replace(apply_anchor, apply_final, 1)

    successor_guard_anchor = '''        if successor_count > 1:
            raise PatchError(f"{name}: reviewed successor is duplicated ({successor_count})")

        old_count = text.count(old)
'''
    successor_guard_final = '''        if successor_count > 1:
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
'''
    if "REVIEWED_PREVIOUS_SUCCESSOR" not in text:
        if text.count(successor_guard_anchor) != 1:
            raise RepairError("apply_text previous-successor guard anchor is absent or ambiguous")
        text = text.replace(successor_guard_anchor, successor_guard_final, 1)

    converge_anchor = '''    if MOBILE_FINAL not in text:
        late_intermediate = (
'''
    converge_final = '''    previous_mobile_count = text.count(MOBILE_PREVIOUS)
    if MOBILE_FINAL not in text and previous_mobile_count == 1:
        text = text.replace(MOBILE_PREVIOUS, MOBILE_FINAL, 1)
    elif MOBILE_FINAL not in text and previous_mobile_count > 1:
        raise PatchError(
            "mobile_layout_hardening: previous successor is duplicated"
        )

    if MOBILE_FINAL not in text:
        late_intermediate = (
'''
    if "previous_mobile_count =" not in text:
        if text.count(converge_anchor) != 1:
            raise RepairError("mobile convergence anchor is absent or ambiguous")
        text = text.replace(converge_anchor, converge_final, 1)

    banned_anchor = '''        MEASURED_INTERMEDIATE,
        MOBILE_INTERMEDIATE_BLOCK,
    ]
'''
    banned_final = '''        MEASURED_INTERMEDIATE,
        MOBILE_INTERMEDIATE_BLOCK,
        MOBILE_PREVIOUS,
        MENU_TOGGLE_PREVIOUS,
    ]
'''
    if "MENU_TOGGLE_PREVIOUS," not in text:
        if text.count(banned_anchor) != 1:
            raise RepairError("validate_truth banned anchor is absent or ambiguous")
        text = text.replace(banned_anchor, banned_final, 1)

    required_anchor = '''        MEASURED_NVIDIA,
        MOBILE_FINAL,
    ]
'''
    required_final = '''        MEASURED_NVIDIA,
        MOBILE_FINAL,
        MENU_TOGGLE_FINAL,
    ]
'''
    if "MENU_TOGGLE_FINAL," not in text:
        if text.count(required_anchor) != 1:
            raise RepairError("validate_truth required anchor is absent or ambiguous")
        text = text.replace(required_anchor, required_final, 1)

    REPAIR.write_text(text, encoding="utf-8")


def patch_regression_test() -> None:
    text = CANARY_TEST.read_text(encoding="utf-8")
    if TEST_NAME in text:
        return
    test = f'''


def {TEST_NAME}() -> None:
    source = LANDING.read_text(encoding="utf-8")
    menu = re.search(r"\\.menu-toggle\\{{[^}}]+\\}}", source)
    assert menu is not None
    contract = menu.group(0)
    for token in (
        "width:48px",
        "height:48px",
        "min-width:48px",
        "min-height:48px",
        "border-radius:6px",
    ):
        assert token in contract
    assert "width:44px" not in contract
    assert "height:44px" not in contract
    assert "{MOBILE_TOP_FINAL}" in source
'''
    CANARY_TEST.write_text(text.rstrip() + test + "\n", encoding="utf-8")


def run(*args: str) -> None:
    completed = subprocess.run(
        args,
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise RepairError(
            f"command failed ({completed.returncode}): {' '.join(args)}\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )
    if completed.stdout:
        print(completed.stdout, end="")


def validate() -> None:
    landing = LANDING.read_text(encoding="utf-8")
    if landing.count(MENU_FINAL) != 1 or MENU_PREVIOUS in landing:
        raise RepairError("landing menu target did not converge exactly")
    if landing.count(MOBILE_TOP_FINAL) != 1 or MOBILE_TOP_PREVIOUS in landing:
        raise RepairError("landing mobile hero position did not converge exactly")

    json.loads(PATCH_SPEC.read_text(encoding="utf-8"))
    run("python3", "-m", "py_compile", str(REPAIR), str(CANARY_TEST))
    run("python3", "scripts/repair_a11oy_frontdoor.py", "a11oy_landing.html", "--check")
    run("python3", "scripts/check_a11oy_frontdoor_truth.py", "a11oy_landing.html")


def remove_bootstrap() -> None:
    for path in (SELF, WORKFLOW):
        if not path.is_file():
            raise RepairError(f"bootstrap path missing before cleanup: {path}")
        path.unlink()


def main() -> int:
    patch_landing()
    patch_spec()
    patch_repair_script()
    patch_regression_test()
    validate()
    remove_bootstrap()
    print("frontend live-canary repair converged and bootstrap files removed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
