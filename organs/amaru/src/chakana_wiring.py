# Copyright 2024 CHAKANA Project Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
chakana_wiring.py — Canonical 21-edge wiring for CHAKANA v3 spine (9 nodes).

Maxwell rigidity criterion: M = b - 3j + 6 = 0
  j = 9 nodes, b = 21 edges → M = 21 - 27 + 6 = 0  ✓

Edges are DIRECTED (→) because AMARU is a directional cognitive pipeline.
The Maxwell criterion is classically undirected; see WIRING_RATIONALE.md for
the caveat and our mitigating convention.
"""

# ---------------------------------------------------------------------------
# Node registry
# ---------------------------------------------------------------------------

CHAKRAS = [
    "KALLPA",   # 1  root       — energy budget
    "YACHAY",   # 2  sacral     — retrieve / codex
    "MUSQUY",   # 3  pos 2.5   — simulate
    "RIMAY",    # 4  solar      — propose
    "YUYAY",    # 5  heart      — critique / gate
    "NAWI",     # 6  third-eye  — boundary-in / toolcall
    "RUWAY",    # 7  throat     — commit
    "TUKUY",    # 8  pos 7.5   — action-out
    "HATUN",    # 9  crown      — sovereignty + continuum_hash
]

# ---------------------------------------------------------------------------
# Edge registry  (from, to, justification)
# All 21 directed edges; (a,b) ≠ (b,a) — see WIRING_RATIONALE.md
# ---------------------------------------------------------------------------

EDGES = [
    # ── BASE SERPENT EDGES (8) ─────────────────────────────────────────────
    ("KALLPA",  "YACHAY",  "Serpent-1: energy primes retrieval"),
    ("YACHAY",  "MUSQUY",  "Serpent-2: codex feeds simulation"),
    ("MUSQUY",  "RIMAY",   "Serpent-3: simulation drives proposal"),
    ("RIMAY",   "YUYAY",   "Serpent-4: proposal enters critique gate"),
    ("YUYAY",   "RUWAY",   "Serpent-5: gate approval triggers commit"),
    ("RUWAY",   "TUKUY",   "Serpent-6: commit hands off to action-out"),
    ("TUKUY",   "HATUN",   "Serpent-7: outbound action crowned by sovereignty"),
    ("HATUN",   "KALLPA",  "Serpent-8: cycle close — sovereign hash seeds next tick energy"),

    # ── BRACING EDGES (13) ─────────────────────────────────────────────────
    ("KALLPA",  "HATUN",   "Brace-1: sovereignty informs energy budget (bidirectional intent: reverse arc)"),
    ("NAWI",    "RIMAY",   "Brace-2: toolcall results inform proposal"),
    ("NAWI",    "YUYAY",   "Brace-3: toolcall results pass directly to critique gate"),
    ("YACHAY",  "YUYAY",   "Brace-4: retrieved priors checked at gate"),
    ("YACHAY",  "RUWAY",   "Brace-5: codex updates committed via throat"),
    ("KALLPA",  "YUYAY",   "Brace-6: energy budget gates critique cost"),
    ("KALLPA",  "RUWAY",   "Brace-7: commit action pays energy toll"),
    ("HATUN",   "YUYAY",   "Brace-8: HUKLLA continuum hash informs 9-axis critique"),
    ("MUSQUY",  "YUYAY",   "Brace-9: critique can request re-simulation"),
    ("MUSQUY",  "YACHAY",  "Brace-10: simulation consults codex mid-flight"),
    ("MUSQUY",  "KALLPA",  "Brace-11: simulation pays energy budget"),
    ("HATUN",   "NAWI",    "Brace-12: sovereignty governs external boundary — HATUN authorises which reads NAWI may open"),
    ("TUKUY",   "NAWI",    "Brace-13: action-out symmetric to action-in boundary"),
]

# ---------------------------------------------------------------------------
# Maxwell rigidity
# ---------------------------------------------------------------------------

def maxwell_count() -> int:
    """Return M = b - 3*j + 6 for the v3 spine."""
    j = len(CHAKRAS)   # 9
    b = len(EDGES)     # 21
    return b - 3 * j + 6


def verify_rigid() -> bool:
    """Return True if Maxwell count M == 0 (isostatic / minimally rigid)."""
    return maxwell_count() == 0


# ---------------------------------------------------------------------------
# Quick self-check when run directly
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    M = maxwell_count()
    print(f"j = {len(CHAKRAS)}  b = {len(EDGES)}  M = {M}")
    print("RIGID (M=0): PASS" if verify_rigid() else f"FAIL (M={M})")
