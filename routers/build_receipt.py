"""routers/build_receipt.py — read-only GET /api/build + release promotion gate (#3770).

Route group (all GET, read-only; no signer, credential, store, or effector):
    GET /api/build                 (+ /api/a11oy/v1/build)
    GET /api/a11oy/v1/release/gate

The build receipt binds source identity (git commit) to runtime build
evidence (served frontend hash, API contract hash, model identity,
deployment identity). Every value is read from the one release manifest
(CI-generated, never hardcoded) or from runtime env; absent values surface as
the honest label UNKNOWN and the promotion gate BLOCKS. The gate never
upgrades an unreachable probe and never invents a build id.

The X-SZL-Release-Id response header is always present: the resolved release
id, or the honest label UNKNOWN when it cannot be resolved.

Wired at the serve.py pre-catch-all seam from routers/frontier_reads.py
(same guarded-additive pattern as series_a/frontier_now/atelier/hf_tooling):

    try:
        from routers import build_receipt as _build_receipt
        build_receipt = _build_receipt.register(app)
    except Exception:
        build_receipt = {"ok": False, "state": "UNAVAILABLE", ...}

One additive read surface must never take down A11oy. Not auto-merge; needs
review and the owner's yes. No deploy.

Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""

from __future__ import annotations

from typing import Any

from fastapi.responses import JSONResponse


def register(app) -> dict[str, Any]:
    import szl_release_manifest as srm

    @app.get("/api/build")
    @app.get("/api/a11oy/v1/build")
    async def a11oy_build_receipt() -> JSONResponse:
        try:
            payload = srm.build_payload()
            release_id = str(payload.get("release_id") or srm.UNKNOWN)
            return JSONResponse(payload, headers={"X-SZL-Release-Id": release_id})
        except Exception as exc:  # fail closed, never fabricate a build id
            return JSONResponse(
                {
                    "kind": srm.BUILD_KIND,
                    "status": "UNAVAILABLE",
                    "reason": type(exc).__name__,
                    "promotion_gate": {
                        "kind": srm.GATE_KIND,
                        "decision": "BLOCKED",
                        "fail_closed": True,
                        "issue": "#3770",
                    },
                },
                status_code=503,
                headers={"X-SZL-Release-Id": srm.UNKNOWN},
            )

    @app.get("/api/a11oy/v1/release/gate")
    async def a11oy_release_promotion_gate() -> JSONResponse:
        try:
            manifest = srm.load_manifest()
            runtime = srm.runtime_evidence()
            gate = srm.promotion_gate(manifest, runtime)
            return JSONResponse(gate)
        except Exception as exc:  # fail closed, never fabricate a pass
            return JSONResponse(
                {
                    "kind": srm.GATE_KIND,
                    "decision": "BLOCKED",
                    "fail_closed": True,
                    "state": "UNAVAILABLE",
                    "reason": type(exc).__name__,
                    "issue": "#3770",
                },
                status_code=503,
            )

    return {
        "ok": True,
        "group": "build-receipt",
        "issue": "#3770",
        "routes": [
            "/api/build",
            "/api/a11oy/v1/build",
            "/api/a11oy/v1/release/gate",
        ],
        "honesty": "read-only; UNKNOWN never passes the gate; no fabricated values",
    }
