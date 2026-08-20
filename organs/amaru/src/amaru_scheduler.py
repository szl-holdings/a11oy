"""AMARU — kundalini scheduler. Fires 7 chakras in serpentine order.

Doctrine: ≤10 SLOC. Ascending phase = propose (1→7). Descending phase = commit (7→1).
Serpent shape: single thread, head-to-tail, no branching mid-tick.
"""

ASCEND = ["KALLPA", "YACHAY", "RIMAY", "YUYAY", "RUWAY", "NAWI", "HATUN"]

def amaru(chakras: dict, state: dict, world: dict, yawar: list) -> tuple:
    """Run one full serpentine tick. Returns (new_state, new_yawar, trace)."""
    trace = []
    for name in ASCEND:                          # 1 — kundalini rises
        fn = chakras[name]
        result = fn(state, world, yawar)
        trace.append((name, result))             # 2 — receipt per chakra
        state = result.get("state", state)       # 3 — state evolves
        yawar = result.get("yawar", yawar)       # 4 — bus accumulates
    return state, yawar, trace                   # 5 — single return
