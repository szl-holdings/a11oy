#!/usr/bin/env python3
"""Bind the reviewed responsive layer to the existing Holographic Experience.

The operation is deliberately narrow and idempotent: prepend one local CSS
import to the existing product-wide holographic stylesheet and advance the
machine-readable state record. It does not rewrite any product page, route,
API, evidence, receipt, model, or deployment configuration.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOST = ROOT / "console" / "assets" / "szl-hologram-v2.css"
ASSET = ROOT / "console" / "assets" / "szl-responsive-v3.css"
STATE = ROOT / "docs" / "responsive-experience-v3.json"
MARKER = "szl-responsive-v3"
IMPORT = '@import url("./szl-responsive-v3.css"); /* szl-responsive-v3 */'


def verify() -> None:
    if not HOST.is_file():
        raise RuntimeError(f"missing host stylesheet: {HOST.relative_to(ROOT)}")
    if not ASSET.is_file():
        raise RuntimeError(f"missing responsive stylesheet: {ASSET.relative_to(ROOT)}")
    text = HOST.read_text(encoding="utf-8")
    if text.count(MARKER) != 1:
        raise RuntimeError(f"expected exactly one {MARKER} binding, found {text.count(MARKER)}")
    first_rule = next((line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith("/*") and not line.lstrip().startswith("*")), "")
    if first_rule != IMPORT:
        raise RuntimeError("responsive import must precede all CSS rules")
    state = json.loads(STATE.read_text(encoding="utf-8"))
    if state.get("state") != "BOUND":
        raise RuntimeError("responsive state is not BOUND")


def apply() -> bool:
    if not HOST.is_file() or not ASSET.is_file():
        raise RuntimeError("responsive binding inputs are incomplete")
    text = HOST.read_text(encoding="utf-8")
    lines = [line for line in text.splitlines() if MARKER not in line]
    normalized = IMPORT + "\n" + "\n".join(lines).lstrip("\n")
    if not normalized.endswith("\n"):
        normalized += "\n"
    changed = normalized != text
    if changed:
        HOST.write_text(normalized, encoding="utf-8", newline="\n")

    state = json.loads(STATE.read_text(encoding="utf-8"))
    state["state"] = "BOUND"
    state["binding"]["verified"] = True
    state["binding"]["import"] = IMPORT
    STATE.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    verify()
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        verify()
        print("responsive-experience-v3: BOUND")
        return 0
    changed = apply()
    print(f"responsive-experience-v3: {'UPDATED' if changed else 'ALREADY_BOUND'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
