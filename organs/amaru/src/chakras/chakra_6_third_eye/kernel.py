"""CH'ULLA-NAWI kernel — TINKUY toolcall primitive. ≤10 lines. MIT."""
import random


def tinkuy(intent: str, tools: list[dict], seed: int, invoke=None):
    random.seed(seed)
    ranked = sorted(tools, key=lambda t: sum(w in intent.lower() for w in t["name"].lower().split("_")), reverse=True)
    chosen = ranked[0]
    args = {k: f"<{k}>" for k in chosen.get("params", [])}
    result = (invoke or (lambda n, a: {"mock": True, "tool": n, "args": a}))(chosen["name"], args)
    return chosen["name"], args, result
