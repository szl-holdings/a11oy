"""
pin_results.py — runs each chakra kernel against a canonical envelope
and writes the verbatim (input, output) pair into result.json so the
shipped artifact reflects real runtime behavior.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

CANONICAL = {
    "root": {"signals": {"grounded": 0.9, "integrity": 0.9}},
    "sacral": {"signals": {"novelty": 0.5, "fluency": 0.8}},
    "solar": {"signals": {"intent": 0.8, "agency": 0.9, "friction": 0.1}},
    "heart": {"signals": {"care": 0.9, "harm": 0.1}},
    "throat": {"signals": {"clarity": 0.81, "truth": 0.64}},
    "third_eye": {"signals": {"pattern_strength": 0.7, "uncertainty": 0.2}},
    "crown": {"upstream": {"stability": 0.9, "flow": 0.68, "will": 0.62, "coherence": 0.8, "fidelity": 0.72, "insight": 0.56}},
}


def main() -> int:
    for name, envelope in CANONICAL.items():
        kernel = importlib.import_module(f"amaru.chakras.{name}.kernel")
        output = kernel.evaluate(envelope)
        path = ROOT / "src" / "amaru" / "chakras" / name / "result.json"
        path.write_text(json.dumps({
            "canonical_input": envelope,
            "canonical_output": output,
            "stubbed": False,
            "proof_id": f"amaru.{name}.v1",
        }, indent=2, sort_keys=True) + "\n")
        print(f"{name}: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
