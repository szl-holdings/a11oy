from __future__ import annotations

"""Read-mostly FastAPI service and local operator console."""

import hmac
import os
from importlib.resources import files
from pathlib import Path
from typing import Any

from .canary import run_canary
from .errors import ValidationError
from .state_bus import StateBus


def _bounded_token(value: str | None, *, name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or len(value.encode("utf-8")) < 32 or len(value) > 4096:
        raise ValidationError(f"{name} must contain 32..4096 UTF-8 bytes")
    return value


def create_app(
    *,
    db_path: str,
    runtime_root: str,
    admin_token: str | None = None,
    read_token: str | None = None,
):
    try:
        from fastapi import FastAPI, Header, HTTPException, Request
        from fastapi.responses import HTMLResponse, Response
    except ImportError as exc:  # pragma: no cover - optional extra
        raise RuntimeError("FastAPI is not installed; install szl-council-kernel[api]") from exc

    app = FastAPI(
        title="A11oy Council Kernel",
        version="0.5.0rc1",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    bus = StateBus(db_path)
    runtime = Path(runtime_root)
    if runtime.exists() and (runtime.is_symlink() or not runtime.is_dir()):
        raise ValidationError("runtime_root must be a real directory")
    runtime.mkdir(parents=True, exist_ok=True)
    if runtime.is_symlink():
        raise ValidationError("runtime_root must not be a symbolic link")
    token = _bounded_token(
        admin_token or os.environ.get("ALLOY_COUNCIL_ADMIN_TOKEN"),
        name="admin token",
    )
    reader = _bounded_token(
        read_token or os.environ.get("ALLOY_COUNCIL_READ_TOKEN"),
        name="read token",
    )

    def require_admin(value: str | None) -> None:
        if not token:
            raise HTTPException(status_code=503, detail="admin mutation endpoint disabled")
        if value is None or not hmac.compare_digest(value, token):
            raise HTTPException(status_code=401, detail="invalid admin token")

    def require_read(value: str | None, authorization: str | None) -> None:
        if not reader:
            raise HTTPException(status_code=503, detail="sensitive read endpoint disabled")
        candidate = value
        if candidate is None and authorization and authorization.startswith("Bearer "):
            candidate = authorization[7:]
        if candidate is None or not hmac.compare_digest(candidate, reader):
            raise HTTPException(status_code=401, detail="invalid read token")

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; object-src 'none'; "
            "base-uri 'none'; frame-ancestors 'none'; form-action 'none'"
        )
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
        )
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        return response

    @app.get("/healthz")
    def healthz() -> dict[str, Any]:
        verification = bus.verify_chain()
        return {
            "status": "ok" if verification["status"] == "PASS" else "degraded",
            "release": "0.5.0rc1",
            "state_bus": verification["status"],
            "production_independence_verified": False,
        }

    @app.get("/api/v1/status")
    def status() -> dict[str, Any]:
        recent = bus.list_cases(limit=50)
        cases = [
            {
                "case_id": item["case_id"],
                "state": item["state"],
                "envelope_digest": item["envelope_digest"],
                "updated_at": item["updated_at"],
            }
            for item in recent
        ]
        ledger = bus.verify_chain()
        return {
            "schema": "a11oy.council-service-status/v2",
            "release": "0.5.0rc1",
            "cases": cases,
            "ledger": {
                "schema": ledger["schema"],
                "status": ledger["status"],
                "event_count": ledger["event_count"],
                "case_count": ledger["case_count"],
                "receipt_count": ledger["receipt_count"],
                "head_hash": ledger["head_hash"],
                "errors": ledger["errors"][:20],
            },
            "mutation_api_enabled": bool(token),
            "sensitive_read_api_enabled": bool(reader),
            "projection_mode": "read-only",
            "production_independence_verified": False,
        }

    @app.get("/api/v1/cases")
    def cases(
        limit: int = 100,
        x_alloy_read_token: str | None = Header(default=None),
        authorization: str | None = Header(default=None),
    ) -> list[dict[str, Any]]:
        require_read(x_alloy_read_token, authorization)
        return bus.list_cases(limit=limit)

    @app.get("/api/v1/cases/{case_id}")
    def case(
        case_id: str,
        x_alloy_read_token: str | None = Header(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_read(x_alloy_read_token, authorization)
        try:
            return bus.get_case(case_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="case not found") from exc

    @app.get("/api/v1/ledger/verify")
    def verify_ledger() -> dict[str, Any]:
        return bus.verify_chain()

    @app.get("/api/v1/evidence/export")
    def export_evidence(
        x_alloy_read_token: str | None = Header(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_read(x_alloy_read_token, authorization)
        return bus.export_evidence()

    @app.post("/api/v1/canary")
    def canary(x_alloy_admin_token: str | None = Header(default=None)) -> dict[str, Any]:
        require_admin(x_alloy_admin_token)
        return run_canary(runtime / "api-canary")

    def asset(name: str) -> str:
        return files("szl_council_kernel.web").joinpath(name).read_text(encoding="utf-8")

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return asset("index.html")

    @app.get("/app.js")
    def app_js() -> Response:
        return Response(asset("app.js"), media_type="application/javascript")

    @app.get("/app.css")
    def app_css() -> Response:
        return Response(asset("app.css"), media_type="text/css")

    return app
