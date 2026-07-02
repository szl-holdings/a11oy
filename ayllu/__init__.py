"""ayllu — the AlloyScape tribe, ingested and reborn as a11oy's own agent community.

This package is a11oy-native. It learns the tribe's *design* (a roster of specialised
agent-personas sharing one guarded tool loop, an always-on daemon, an autonomy gate,
and a collaboration lounge) and rebuilds it in a11oy's idiom: the active-flux model
router, the bounded-autonomy AgentLoop, and DSSE receipts.

It deliberately does NOT adopt the tribe's "fully agentic, no sandbox" mandate. Every
persona here runs under a11oy's fail-closed Λ-gate. See INGEST.md for the full mapping
and boundary.

Public surface:
    from ayllu.personas import ROSTER, get_persona, load_soul
    from ayllu.loop import select_tier, run_turn
    from ayllu.autonomy import gate
    from ayllu.lounge import Lounge
    from ayllu.daemon import Daemon
"""
from __future__ import annotations

__version__ = "0.1.0"
NAMESPACE_DEFAULT = "a11oy"

__all__ = ["__version__", "NAMESPACE_DEFAULT"]
