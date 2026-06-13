# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings
# ORCID: 0009-0001-0110-4173
# Doctrine v11
"""Unified server for Hugging Face Spaces — serves both the Amaru API and the built frontend.

Round 2 additions (amaru_full_operational):
- /console/ — operator console SPA (7-chakra dashboard, DSSE inspector, tripwires, bus, receipts)
- Rosie widget embedded in console
"""

import logging
import os
import sys

sys.path.insert(0, "/app")

from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from starlette.middleware.cors import CORSMiddleware

from amaru.app import app as amaru_app

logger = logging.getLogger("amaru.serve")

STATIC_DIR = Path(os.environ.get("AMARU_STATIC_DIR", "/app/static"))
CONSOLE_DIR = Path(os.environ.get("AMARU_CONSOLE_DIR", "/app/console"))

# Critical static assets the Space must serve. If any of these is missing the
# page renders a broken "(loading)" placeholder or a generic 404 — the exact
# trap CTO-2 flagged on the amaru hero image. We make that failure loud at boot
# instead of letting it surface in front of an audience. Set
# AMARU_SKIP_ASSET_PREFLIGHT=1 to bypass (local frontend-less API runs only).
CRITICAL_ASSETS = (
    STATIC_DIR / "index.html",
    STATIC_DIR / "assets" / "amaru_hero.png",
)


def assert_assets_present() -> None:
    """Refuse to boot the full-stack server if a critical static asset is absent.

    Rationale: a Space that boots green while its hero asset 404s is a
    fake-green surface. Failing closed here turns a silent in-room blemish into
    a deploy-time error the operator sees before Warhacker, not during it.
    """
    if os.environ.get("AMARU_SKIP_ASSET_PREFLIGHT") == "1":
        logger.warning("asset preflight skipped (AMARU_SKIP_ASSET_PREFLIGHT=1)")
        return
    if not STATIC_DIR.exists():
        # No built frontend in this image: API-alone mode is a valid deployment,
        # so we do not hard-fail — we serve the API and log the absence.
        logger.warning("no static dir at %s — serving the API alone", STATIC_DIR)
        return
    missing = [str(p) for p in CRITICAL_ASSETS if not p.is_file()]
    if missing:
        raise RuntimeError(
            "amaru static preflight failed — critical asset(s) missing: "
            + ", ".join(missing)
            + ". Refusing to boot a Space that would serve a broken page. "
            "Rebuild the frontend (npm run build) so dist/ includes these, "
            "or set AMARU_SKIP_ASSET_PREFLIGHT=1 for an API-alone run."
        )
    logger.info("asset preflight ok — %d critical asset(s) present", len(CRITICAL_ASSETS))


app = FastAPI(title="Amaru — Full Stack")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/api/amaru", amaru_app)

# Run the preflight at import time so an unhealthy image fails fast under any
# launcher (uvicorn factory import, gunicorn, or __main__).
assert_assets_present()


@app.get("/healthz")
async def healthz():
    """Liveness + asset-presence probe.

    Always returns HTTP 200 (the endpoint itself is alive) but reports
    status="degraded" with the offending paths when a critical static asset is
    missing, or status="ok" when every asset is present (or the image is a
    declared API-alone build). A monitor that trusts the HF runtime stage by
    itself cannot see a 404ing hero; reading this body's status field can.
    """
    api_alone = not STATIC_DIR.exists()
    missing = (
        []
        if api_alone
        else [str(p) for p in CRITICAL_ASSETS if not p.is_file()]
    )
    status = "ok" if not missing else "degraded"
    console_present = (CONSOLE_DIR / "console.html").is_file()
    return {
        "status": status,
        "api_alone": api_alone,
        "missing_assets": missing,
        "static_dir": str(STATIC_DIR),
        "console_present": console_present,
        "console_route": "/console/",
    }


# ── /console/ route — operator SPA ────────────────────────────────────────────
# The console SPA is a self-contained HTML file that uses /api/amaru/* endpoints
# for all live data. No build step required — served directly from CONSOLE_DIR.

@app.get("/console")
@app.get("/console/")
async def console_root():
    """Operator console — 7-chakra dashboard, DSSE inspector, tripwires, bus, receipts."""
    console_file = CONSOLE_DIR / "console.html"
    if console_file.is_file():
        return FileResponse(console_file, media_type="text/html")
    # Fallback: redirect to the main SPA
    return HTMLResponse(
        '<meta http-equiv="refresh" content="0;url=/" />'
        '<p>Console not found. <a href="/">Return home</a>.</p>',
        status_code=200,
    )


# ── Static SPA + assets ───────────────────────────────────────────────────────
if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(STATIC_DIR / "assets")), name="assets")

    @app.get("/{path:path}")
    async def serve_spa(path: str):
        # Never intercept /console (handled above) or /api
        if path.startswith("console") or path.startswith("api"):
            return HTMLResponse("Not found", status_code=404)
        file_path = STATIC_DIR / path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(STATIC_DIR / "index.html")


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "7860"))
    uvicorn.run("serve:app", host="0.0.0.0", port=port, log_level="info")
