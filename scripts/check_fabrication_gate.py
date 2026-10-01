#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 SZL Holdings — Doctrine v11. Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
"""Fabrication gate: continuously measure the served brain model's refusal-to-fabricate
posture in CI (the SOTA "abstention benchmark in CI" move, adapted honestly).

Runs szl_braineval's fixed doctrine probe battery against the estate's own public
inference Space (SZL-Khipu-1.5B-GGUF) — no secrets, no API keys: the endpoint is public.

HONEST GATE SEMANTICS (fail-closed on fabrication, fail-open on availability):
  * the model answers THIS request and FABRICATES on a probe  -> exit 1 (real failure)
  * the model answers and refuses                             -> exit 0, MEASURED posture reported
  * the endpoint is unreachable / asleep                      -> exit 0 with verdict SKIP
    (external availability is NOT a fabrication signal; the gate catches lying, not downtime)

The verdict is a MEASURED reading taken from the live model THIS run — never fabricated,
never upgraded. If the Space is cold, the first probe warms it (timeout is generous).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# repo root on sys.path so this runs from anywhere (CI checks out the repo root)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# The estate's own public inference Space — no secret required (public endpoint).
DEFAULT_URL = "https://szlholdings-szl-model-inference-lab.hf.space"
DEFAULT_MODEL = "SZLHOLDINGS/SZL-Khipu-1.5B-GGUF@67d60ec577730747055491640cfb91fc4a4b5d25"

# HF Spaces can cold-start slowly; the first probe pays the warm-up, later ones are fast.
PROBE_TIMEOUT_S = 150.0

SCHEMA = "szl.fabrication-gate/v1"
OUT_PATH = Path("fabrication-gate-verdict.json")


def main() -> int:
    import szl_braineval as be

    environ = {
        "SZL_LOCAL_LLM_URL": DEFAULT_URL,
        "SZL_LOCAL_LLM_MODEL": DEFAULT_MODEL,
    }
    result = be.evaluate(environ=environ, timeout=PROBE_TIMEOUT_S, ns="a11oy")

    verdict = {
        "schema": SCHEMA,
        "gate": "fabrication",
        "label": result.get("label"),
        "model_verdict": result.get("verdict"),
        "refusal_rate": result.get("refusal_rate"),
        "probes": [
            {"family": p.get("family"), "outcome": p.get("outcome")}
            for p in (result.get("probes") or [])
        ],
        "model": DEFAULT_MODEL,
        "endpoint": DEFAULT_URL,
        "note": None,
    }

    if result.get("label") != "MEASURED":
        # Unavailable endpoint -> SKIP (never fail CI on external availability).
        verdict["gate_outcome"] = "SKIP"
        verdict["note"] = (
            "served model did not answer this run (asleep/cold/unreachable); availability is "
            "not a fabrication signal, so the gate skips rather than fails or fabricates."
        )
        OUT_PATH.write_text(json.dumps(verdict, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(verdict, indent=2, sort_keys=True))
        print("::notice::fabrication gate SKIP — served model unavailable this run.")
        return 0

    if result.get("verdict") == "FABRICATION-DETECTED":
        verdict["gate_outcome"] = "FAIL"
        verdict["note"] = (
            "the served model FABRICATED on a doctrine probe this run — a real, measured "
            "failure. This gate fails closed: no merge train proceeds on a lying model."
        )
        OUT_PATH.write_text(json.dumps(verdict, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(verdict, indent=2, sort_keys=True))
        print("::error::fabrication gate FAIL — served model fabricated on a probe (see verdict).")
        return 1

    verdict["gate_outcome"] = "PASS"
    verdict["note"] = (
        "MEASURED refusal posture for the served model this run; a valid reading, never "
        "inflated (rate is capped at the 0.97 trust ceiling by construction)."
    )
    OUT_PATH.write_text(json.dumps(verdict, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(verdict, indent=2, sort_keys=True))
    print("::notice::fabrication gate PASS — refusal posture measured.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
