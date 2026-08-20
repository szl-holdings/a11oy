#!/usr/bin/env python3
"""Audit explicitly optional serve.py integrations without importing them.

The prior startup log called missing source files "dead stubs" and printed full
tracebacks. That conflated an intentionally guarded integration point with a
broken present module. This audit has three evidence inputs only:

* the module name is referenced by ``serve.py``;
* a same-checkout source file/package exists;
* the explicit-copy Dockerfile includes that source.

It never invents an implementation and never treats absence as live. Use
``--strict`` to fail only when source exists but the explicit-copy image omits it.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


OPTIONAL_MODULES = (
    "szl_formula_ops",
    "szl_thesis_about",
    "a11oy_v4_predict",
    "a11oy_v4_thesis_primitives",
    "szl_kernels_organ",
    "a11oy_ontology",
    "a11oy_derivation",
    "a11oy_explorer",
)


def audit(root: Path) -> dict:
    serve = (root / "serve.py").read_text(encoding="utf-8")
    docker = (root / "Dockerfile").read_text(encoding="utf-8")
    rows = []
    for module in OPTIONAL_MODULES:
        filename = f"{module}.py"
        referenced = module in serve
        source_present = (root / filename).is_file() or (root / module / "__init__.py").is_file()
        image_copy_present = filename in docker or f"COPY {module}/" in docker
        if not referenced:
            status = "AUDIT_CONFIG_DRIFT"
        elif not source_present:
            status = "OPTIONAL-ABSENT"
        elif not image_copy_present:
            status = "SOURCE_PRESENT_IMAGE_COPY_MISSING"
        else:
            status = "WIRED_SOURCE_AND_IMAGE_COPY"
        rows.append({
            "module": module,
            "serve_reference": referenced,
            "source_present": source_present,
            "explicit_image_copy": image_copy_present,
            "status": status,
        })
    blocking = [r for r in rows if r["status"] in {
        "AUDIT_CONFIG_DRIFT", "SOURCE_PRESENT_IMAGE_COPY_MISSING"}]
    return {
        "schema": "szl.runtime.optional-import-audit/v1",
        "root": str(root.resolve()),
        "audited": len(rows),
        "blocking": len(blocking),
        "modules": rows,
        "honesty": (
            "OPTIONAL-ABSENT means no implementation exists in this checkout; "
            "no route or capability is claimed."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    report = audit(args.root)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if args.strict and report["blocking"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
