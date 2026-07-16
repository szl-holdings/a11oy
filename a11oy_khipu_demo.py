# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings
"""
a11oy Khipu demo — GET /api/khipu/demo

Serves THREE recorded Khipu navigator traces for the console demo tab. These are
copyable, static, in-image outputs — NOT live inference. The a11oy Space CPU
cannot serve the model honestly, so nothing here calls the model at request time.

Honesty label (doctrine): the traces were RECORDED 2026-07-16 by an agent that
ran the *quantized* GGUF (Q4_K_M) on CPU via llama-cpp-python, reusing the public
harness's prompt assembly + scoring (szl-forge main khipu/eval_khipu.py). This is
a DIFFERENT ARTIFACT and DIFFERENT RUNTIME than the owner's signed eval receipt —
these are NOT the signed-receipt counts and are never presented as such.

The three traces are deliberately mixed:
  * navigation  — a schema-valid NAVIGATE plan grounded in the offered candidates
  * governance  — the schema/contract forces ABSTAIN on an unsupported/illegitimate
                  target (query asked for "the owner's account password")
  * abstain     — a REAL, labeled FAILURE: the model produced a NAVIGATE plan where
                  it should have abstained. Recorded honestly (matches the card's
                  documented weak-abstention result, 2/6).

Additive module per Space convention: register(app) adds the route and front-moves
it so the exact JSON path wins over the SPA history fallback and the /api proxy.
The trace data ships in-image as a11oy_khipu_demo_traces.json (COPY'd next to this
module); NO fetch to any external domain happens at request time.
"""

import json
import os

_ROUTE = "/api/khipu/demo"
_DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "a11oy_khipu_demo_traces.json")


def _load_data() -> dict:
    """Read the in-image recorded traces. Loud on failure — never a silent stub."""
    with open(_DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


async def _khipu_demo_handler():
    try:
        data = _load_data()
        return {
            "ok": True,
            "wall": "khipu-demo",
            "servedFrom": "a-11-oy.com (a11oy flagship Space) — recorded traces, in-image, NOT live inference",
            "traces": data["traces"],
            "provenance": data["provenance"],
        }
    except Exception as demo_error:  # loud + honest; never fabricate traces
        return {
            "ok": False,
            "wall": "khipu-demo",
            "traces": [],
            "provenance": {
                "label": "RECORDED 2026-07-16, AGENT-RUN, llama.cpp CPU, Q4_K_M quant — not live inference, not the signed-receipt artifact",
            },
            "error": f"{type(demo_error).__name__}: {demo_error}",
        }


def register(app) -> str:
    """Additive registration + front-move (exact route must beat SPA fallback)."""
    app.add_api_route(_ROUTE, _khipu_demo_handler, methods=["GET"], include_in_schema=False)
    for index, route in enumerate(app.router.routes):
        if getattr(route, "path", None) == _ROUTE:
            app.router.routes.insert(0, app.router.routes.pop(index))
            break
    return f"{_ROUTE} (recorded traces: navigation, governance, abstain-failure — in-image, not live)"
