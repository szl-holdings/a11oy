#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 SZL Holdings - Doctrine v11. Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
"""Retired fabrication monitor: emit unavailable evidence and exit 2.

The legacy /v1/chat/completions inference contract is retired. This monitor
performs no inference and cannot mint public-prompt consent for an unattended
workflow. It never turns retirement into a successful availability SKIP.

A replacement evaluator must use the authenticated primary route
POST /api/a11oy/v1/atelier/cpu-lab/turn with declared="PUBLIC" and explicit
public_share_acknowledged=true, then qualify actual outcome, grounding and
receipt binding before claiming measured refusal posture. Merely switching
to the upstream /api/v3/governed-infer URL does not qualify that evaluation.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

DEFAULT_URL = "https://szlholdings-szl-model-inference-lab.hf.space"
DEFAULT_MODEL = "SZLHOLDINGS/SZL-Khipu-1.5B-GGUF@67d60ec577730747055491640cfb91fc4a4b5d25"
SCHEMA = "szl.fabrication-gate/v1"
OUT_PATH = Path("fabrication-gate-verdict.json")
PRIMARY_PATH = "/api/a11oy/v1/atelier/cpu-lab/turn"


def issue_eligible(verdict) -> bool:
    """A monitor failure alone is never evidence that a model fabricated."""
    return (
        isinstance(verdict, dict)
        and verdict.get("gate_outcome") == "FAIL"
        and verdict.get("label") == "MEASURED"
        and verdict.get("model_verdict") == "FABRICATION-DETECTED"
    )


def main() -> int:
    verdict = {
        "schema": SCHEMA,
        "gate": "fabrication",
        "gate_outcome": "RETIRED",
        "label": "UNAVAILABLE",
        "model_verdict": "UNAVAILABLE",
        "refusal_rate": None,
        "probes": [],
        "model": DEFAULT_MODEL,
        "endpoint": DEFAULT_URL,
        "retired_path": "/v1/chat/completions",
        "inference_performed": False,
        "evaluation_performed": False,
        "successor": {
            "method": "POST",
            "path": PRIMARY_PATH,
            "ui": "/command-centre#cpu-work",
            "operator_authentication_required": True,
            "public_share_acknowledged": True,
            "declared": "PUBLIC",
            "grounding_required": True,
            "automatic_forwarding": False,
        },
        "migration_requirement": (
            "Qualify a governed evaluator through authenticated " + PRIMARY_PATH
            + " with explicit public-prompt acknowledgement, outcome/grounding checks "
            "and request-bound receipt evidence. No current refusal posture is measured."
        ),
        "note": (
            "Legacy inference contract retired. Monitoring is UNAVAILABLE; "
            "no model call was made and retirement is not a fabrication finding."
        ),
    }
    OUT_PATH.write_text(json.dumps(verdict, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(verdict, indent=2, sort_keys=True))
    print("::error::fabrication monitoring RETIRED / UNAVAILABLE; governed evaluation migration required.")
    return 2


if __name__ == "__main__":
    sys.exit(main())
