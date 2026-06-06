"""
chakana_wiring — fixed topology of the 7-chakra Andean cross.

The chakana (Andean cross) is a four-step staircase whose vertices we map
onto the 7 chakras. Read top→bottom the topology is an ouroboros: crown
feeds back into root, closing the cycle.

The wiring is intentionally static — there is no graph DB here, no runtime
mutation. If a kernel needs a different shape it ships as a new wiring file.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import CHAKRA_ORDER


@dataclass(frozen=True)
class Edge:
    src: str
    dst: str
    role: str  # e.g. "ascend" (root→crown direction) or "ouroboros" (crown→root)


# Sequential ascent root → sacral → solar → heart → throat → third_eye → crown.
ASCENT_EDGES: tuple[Edge, ...] = tuple(
    Edge(src=CHAKRA_ORDER[i], dst=CHAKRA_ORDER[i + 1], role="ascend")
    for i in range(len(CHAKRA_ORDER) - 1)
)

# Ouroboros closure: crown loops back to root.
OUROBOROS_EDGE: Edge = Edge(src="crown", dst="root", role="ouroboros")

ALL_EDGES: tuple[Edge, ...] = ASCENT_EDGES + (OUROBOROS_EDGE,)


def downstream_of(name: str) -> list[Edge]:
    return [e for e in ALL_EDGES if e.src == name]


def upstream_of(name: str) -> list[Edge]:
    return [e for e in ALL_EDGES if e.dst == name]


def wiring_snapshot() -> dict:
    return {
        "chakras": list(CHAKRA_ORDER),
        "edges": [{"src": e.src, "dst": e.dst, "role": e.role} for e in ALL_EDGES],
        "shape": "andean-cross-ouroboros",
    }
