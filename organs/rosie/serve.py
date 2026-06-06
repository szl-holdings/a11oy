"""serve.py — Khipu 3D demo server shim (Beat 3).

The canonical rosie runtime entrypoint is `app.py` (Gradio mounted on a root
FastAPI app, `app`). This module re-exports that ASGI app and ALSO guarantees
the Beat-3 surface is present even if you run rosie standalone:

  * GET  /api/rosie/v1/khipu/aggregate  — live fan-out to every organ ledger.
  * /khipu-3d/*                         — vanilla three.js + 3d-force-graph viz.

Run any of:

    uvicorn serve:app --host 0.0.0.0 --port 7860          # full rosie (Gradio + API)
    python serve.py                                       # same, convenience
    uvicorn serve:khipu_app --host 0.0.0.0 --port 7861    # API + /khipu-3d ONLY (no Gradio)

The `khipu_app` fallback is a minimal FastAPI app used when the heavy Gradio
import is unavailable; it still serves the real aggregate endpoint + static viz.

Signed-off-by: Yachay <yachay@szlholdings.ai>
Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
"""
from __future__ import annotations

import sys

# Primary: the full rosie app (Gradio + every API surface, incl. /khipu-3d).
app = None
try:
    from app import app as _full_app  # noqa: E402

    app = _full_app
    print("[serve] using full rosie app (app.py) — /khipu-3d + aggregate live", file=sys.stderr)
except Exception as _e:  # pragma: no cover - standalone/degraded path
    print(f"[serve] full app unavailable ({_e!r}); building minimal khipu_app", file=sys.stderr)

# Fallback / always-available minimal API app (no Gradio dependency).
khipu_app = None
try:
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware

    import szl_khipu_aggregate as _khipu3d

    khipu_app = FastAPI(title="rosie · Khipu 3D (Beat 3)", version="1.0.0")
    khipu_app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "OPTIONS"],
        allow_headers=["*"], allow_credentials=False,
    )
    _info = _khipu3d.register(khipu_app, ns="rosie")
    print(f"[serve] khipu_app ready: {_info}", file=sys.stderr)

    @khipu_app.get("/healthz")
    def _healthz():
        return {"ok": True, "doctrine": _khipu3d.DOCTRINE, "surface": ["/api/rosie/v1/khipu/aggregate", "/khipu-3d"]}

    if app is None:
        app = khipu_app
except Exception as _e:  # pragma: no cover
    print(f"[serve] minimal khipu_app build failed: {_e!r}", file=sys.stderr)
    raise

if __name__ == "__main__":
    import os

    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "7860")))
