#!/usr/bin/env python3
"""Run the reviewed repair and normalize exact generated source bytes."""
from __future__ import annotations

import runpy
from pathlib import Path


try:
    runpy.run_path(
        ".github/scripts/repair_runtime_postmerge_once.py",
        run_name="__main__",
    )
except SystemExit as exc:
    if exc.code not in (None, 0):
        raise

# The v1 one-shot generator uses raw templates containing two literal escape
# layers before each docstring quote. Prefer the exact two-layer token; retain a
# one-layer fallback only for a partially normalized retry. Each full target is
# path-scoped and must occur exactly once. No broad source rewrite is allowed.
replacements = {
    Path("szl_immune.py"): (
        (
            r'    \\"\\"\\"Return the key that actually verified the receipt, including rotation.\\"\\"\\"',
            r'    \"\"\"Return the key that actually verified the receipt, including rotation.\"\"\"',
        ),
        '    """Return the key that actually verified the receipt, including rotation."""',
    ),
    Path("szl_agentic_loop.py"): (
        (
            r'    \\"\\"\\"Atomically append one run-of-runs record without lineage forks.\\"\\"\\"',
            r'    \"\"\"Atomically append one run-of-runs record without lineage forks.\"\"\"',
        ),
        '    """Atomically append one run-of-runs record without lineage forks."""',
    ),
    Path("tests/test_post_merge_1986_review_repairs.py"): (
        (
            r'\\"\\"\\"Adversarial regressions for the Codex findings left after PR #1986.\\"\\"\\"',
            r'\"\"\"Adversarial regressions for the Codex findings left after PR #1986.\"\"\"',
        ),
        '"""Adversarial regressions for the Codex findings left after PR #1986."""',
    ),
}

for path, (candidates, replacement) in replacements.items():
    text = path.read_text(encoding="utf-8")
    matched = None
    for candidate in candidates:
        count = text.count(candidate)
        if count > 1:
            raise SystemExit(
                f"{path}: generated quoting target repeated {count} times"
            )
        if count == 1:
            matched = candidate
            break
    if matched is None:
        raise SystemExit(f"{path}: generated quoting target was not found")
    text = text.replace(matched, replacement, 1)
    if any(candidate in text for candidate in candidates):
        raise SystemExit(f"{path}: escaped quoting target survived normalization")
    if text.count(replacement) != 1:
        raise SystemExit(f"{path}: normalized docstring identity is not unique")
    path.write_text(text, encoding="utf-8")


def replace_once(text: str, old: str, new: str, *, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one target, found {count}")
    return text.replace(old, new, 1)


# The inherited IMMUNE suite exposed two additional runtime defects once the
# Codex fixes compiled: structured ledger state was not normalized to a count,
# and Channel B never used its documented read-only state fallback.
immune_path = Path("szl_immune.py")
immune_text = immune_path.read_text(encoding="utf-8")
immune_text = replace_once(
    immune_text,
    '''    ledger = body.get("receiptCount")
    if ledger is None:
        ledger = body.get("ledger")
''',
    '''    ledger = body.get("receiptCount")
    if ledger is None:
        ledger = body.get("ledger")
    if isinstance(ledger, dict):
        ledger = ledger.get("count")
    if isinstance(ledger, bool) or not isinstance(ledger, int) or ledger < 0:
        ledger = None
''',
    label="kernel ledger normalization",
)
immune_text = replace_once(
    immune_text,
    '''    status, data, err = probe(_KERNEL_LATTICE_URL + "/api/field")
    body = data if isinstance(data, dict) else {}
    reachable = status == 200 and isinstance(data, dict)
    raw_cells = body.get("cells") if reachable else None
    cells = raw_cells if isinstance(raw_cells, list) else None
''',
    '''    field_url = _KERNEL_LATTICE_URL + "/api/field"
    state_url = _KERNEL_SPACE_URL + "/api/immune/state"
    status, data, err = probe(field_url)
    body = data if isinstance(data, dict) else {}
    reachable = status == 200 and isinstance(data, dict)
    fallback_state = False
    if not reachable:
        state_status, state_data, state_err = probe(state_url)
        if state_status == 200 and isinstance(state_data, dict):
            fallback_state = True
            status, data, err = state_status, state_data, None
            reachable = True
            estate = state_data.get("estate")
            observed_cells = []
            if isinstance(estate, list):
                for row in estate:
                    if not isinstance(row, dict):
                        continue
                    observed_cells.append({
                        "id": row.get("id"),
                        "title": row.get("title"),
                        "role": row.get("role"),
                        "verb": "OBSERVED",
                    })
            ledger_state = state_data.get("ledger")
            body = {
                "lambda_status": "Conjecture 1 (NOT a theorem)",
                "actuation": "SIMULATED",
                "rule": "observe only — never strike people",
                "cells": observed_cells,
                "hunts": None,
                "ledger": ledger_state if isinstance(ledger_state, dict) else None,
                "doctrine": {
                    "source": "/api/immune/state",
                    "readiness": state_data.get("readiness"),
                    "mesh": state_data.get("mesh"),
                },
            }
        else:
            err = err or state_err
    raw_cells = body.get("cells") if reachable else None
    cells = raw_cells if isinstance(raw_cells, list) else None
''',
    label="field read-only state fallback",
)
immune_text = replace_once(
    immune_text,
    '''        "cell_count": len(cells) if cells is not None else None,
        "upstream_http": status,
''',
    '''        "cell_count": len(cells) if cells is not None else None,
        "ledger": body.get("ledger") if reachable else None,
        "upstream_http": status,
''',
    label="field ledger evidence",
)
immune_text = replace_once(
    immune_text,
    '''        "contract": "/api/field",
        "url": _KERNEL_LATTICE_URL + "/api/field",
''',
    '''        "contract": "/api/immune/state" if fallback_state else "/api/field",
        "url": state_url if fallback_state else field_url,
''',
    label="field fallback source contract",
)
immune_path.write_text(immune_text, encoding="utf-8")

workcell = Path("audit/POST_MERGE_1986_REVIEW_REPAIR_2026-09-05.md")
workcell.write_text(
    workcell.read_text(encoding="utf-8").rstrip() + "\n",
    encoding="utf-8",
)
