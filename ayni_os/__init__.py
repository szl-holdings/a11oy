# VENDORED FROM szl-holdings/platform@c11291e09702c86f3f8995fffcae6167155c7240 — packages/ayni-os/ayni_os/__init__.py
# DO NOT EDIT HERE. Edit in the monorepo, then run scripts/sync_from_monorepo.sh sync.
"""AYNI-OS — time-reversible (event-sourced) reciprocity runtime.

HONEST SCOPE:
- "Time-reversal" here means EVENT-SOURCING REPLAY: we reconstruct past state by
  re-applying an append-only log of signed KIPU receipts up to a target timestamp.
  This is the standard event-sourcing / event-store pattern. It is NOT
  "quantum time-travel" and makes no physics claim.
- "Ayni" is a GAME-THEORY PRIMITIVE: direct reciprocity / reciprocal altruism
  (Axelrod & Hamilton, Science 211(4489), 1981; Trivers, QRB 46(1), 1971). No
  mysticism, no ritual, no religion.

Doctrine v11 LOCKED numbers preserved (749/14/163; 13-axis yuyay_v3; replay hash
bacf54434f1a3bf2d758b27a62d5fd580ca4c8d3b180693573eeebcaea631fc5). ADDITIVE only.
"""

__all__ = [
    "ledger",
    "checkpoint",
    "rewind",
    "reciprocity_monitor",
    "tinkuy",
    "replay_api",
]

# Doctrine v11 LOCKED constants — preserved verbatim, never recomputed here.
DOCTRINE_V11 = {
    "declarations": 749,
    "unique_axioms": 14,
    "sorries": 163,
    "yuyay_v3_axes": 13,
    "yuyay_v3_replay_hash":
        "bacf54434f1a3bf2d758b27a62d5fd580ca4c8d3b180693573eeebcaea631fc5",
}

# Additive constants for AYNI-OS (yuyay_v4 / T24).
AYNI = {
    "yuyay_axis": 14,                  # appended axis, separate v4 hash
    "alpha_balanced": 0.5,             # In == Out
    "alpha_min": 0.45,                 # below this => HUKLLA T24 fires
    "hukla_tripwire": "T24",
    "checkpoint_interval_seconds": 7 * 60,   # periodic KIPU snapshot every 7 minutes
    "tinkuy_r_threshold": 0.85,        # Kuramoto order parameter for flow state
}
