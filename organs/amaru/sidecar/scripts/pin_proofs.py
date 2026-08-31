"""
pin_proofs.py — recompute every chakra's proof.json sha256 over the
canonical kernel.py source bytes. Run after editing a kernel to keep
provenance honest.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

CHAKRA_ROOT = Path(__file__).resolve().parents[1] / "src" / "amaru" / "chakras"

KERNEL_SUMMARY = {
    "root": ("amaru.root.v1", "mean of (grounded + integrity) / 2, clamped to [0,1]"),
    "sacral": ("amaru.sacral.v1", "convex blend 0.6*fluency + 0.4*novelty, clamped to [0,1]"),
    "solar": ("amaru.solar.v1", "intent * agency - friction, clamped to [0,1]"),
    "heart": ("amaru.heart.v1", "care - harm clamped to [0,1]"),
    "throat": ("amaru.throat.v1", "geometric mean sqrt(clarity*truth), clamped to [0,1]"),
    "third_eye": ("amaru.third_eye.v1", "pattern_strength * (1 - uncertainty), clamped to [0,1]"),
    "crown": ("amaru.crown.v1", "arithmetic mean of upstream scalars, clamped to [0,1]"),
}


def main() -> int:
    for chakra, (proof_id, summary) in KERNEL_SUMMARY.items():
        kernel_path = CHAKRA_ROOT / chakra / "kernel.py"
        proof_path = CHAKRA_ROOT / chakra / "proof.json"
        if not kernel_path.exists():
            raise SystemExit(f"missing kernel: {kernel_path}")
        digest = hashlib.sha256(kernel_path.read_bytes()).hexdigest()
        proof = {
            "proof_id": proof_id,
            "sha256": digest,
            "kind": "kernel-source",
            "summary": summary,
            "notes": "sha256 computed over the canonical kernel.py source bytes; re-pin via services/amaru/scripts/pin_proofs.py after edits.",
        }
        proof_path.write_text(json.dumps(proof, indent=2) + "\n")
        print(f"{chakra}: {proof_id} -> {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
