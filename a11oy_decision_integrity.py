# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings
"""Packet 8 Decision Integrity on a-11-oy.com.

Mounts GET /decision and vanity paths /terra /aegis /puriq-markets /puriq
/counsel plus /api/a11oy/v1/decision/*. Evaluates frozen demonstration
cases through verticals/_kernel/a11oy_kernel.py.

Hub Space create is capped at 20/day. These desks are the same kernel on
a-11-oy.com, not four Spaces.

Formula authority NONE. Models and market signals never authorize.
Status stays ROADMAP. Does not stamp LIVE. Does not wait on Hub Spaces.
Does not claim ATO. Λ = Conjecture 1 / ADVISORY_CONJECTURAL.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
VERTICALS_DIR = ROOT / "verticals"
KERNEL_PATH = VERTICALS_DIR / "_kernel" / "a11oy_kernel.py"
PAGES_DIR = ROOT / "pages"

VERTICAL_IDS = ("terra", "aegis", "puriq-markets", "counsel")
PAGE_ALIASES = (
    "/decision",
    "/a11oy/decision",
    "/terra",
    "/aegis",
    "/puriq-markets",
    "/puriq",
    "/counsel",
)
STATUS = "ROADMAP"
DATA_LABEL = "SAMPLE"

_KERNEL = None


def _load_kernel():
    global _KERNEL
    if _KERNEL is not None:
        return _KERNEL
    if not KERNEL_PATH.is_file():
        raise FileNotFoundError(f"kernel missing: {KERNEL_PATH}")
    spec = importlib.util.spec_from_file_location("a11oy_packet8_kernel", KERNEL_PATH)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load Decision Integrity Kernel")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _KERNEL = module
    return module


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_vertical(vertical_id: str) -> dict[str, Any]:
    folder = VERTICALS_DIR / vertical_id
    manifest = _read_json(folder / "vertical_manifest.json")
    policy = _read_json(folder / "policy_bundle.json")
    evals_dir = folder / "evals"
    cases = []
    if evals_dir.is_dir():
        for path in sorted(evals_dir.glob("*.json")):
            item = _read_json(path)
            item.setdefault("eval_id", path.stem)
            cases.append(item)
    return {
        "id": vertical_id,
        "display_name": manifest.get("display_name", vertical_id),
        "wedge": manifest.get("wedge", ""),
        "role": manifest.get("role", ""),
        "manifest": manifest,
        "policy": policy,
        "cases": cases,
    }


def catalog() -> dict[str, Any]:
    kernel = _load_kernel()
    verticals = [load_vertical(vid) for vid in VERTICAL_IDS if (VERTICALS_DIR / vid / "vertical_manifest.json").is_file()]
    return {
        "schema": "szl.decision-integrity-surface/v8",
        "surface": "decision",
        "path": "/decision",
        "status": STATUS,
        "data_label": DATA_LABEL,
        "formula_authority": "NONE",
        "lambda": "Conjecture 1 / ADVISORY_CONJECTURAL",
        "locked_proven": ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"],
        "kernel_version": getattr(kernel, "VERSION", "UNKNOWN"),
        "kernel_schema": getattr(kernel, "SCHEMA", "UNKNOWN"),
        "runtime_claimed": False,
        "hub_spaces_required": False,
        "note": (
            "Frozen demonstration cases on the canonical a11oy site. "
            "Does not prove production readiness. Does not stamp LIVE. "
            "Not legal advice, not a trading bot, not a Palantir clone."
        ),
        "verticals": [
            {
                "id": item["id"],
                "display_name": item["display_name"],
                "wedge": item["wedge"],
                "role": item["role"],
                "case_count": len(item["cases"]),
            }
            for item in verticals
        ],
    }


def evaluate_case(vertical_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    if vertical_id not in VERTICAL_IDS:
        return {"ok": False, "error": "unknown vertical", "verticals": list(VERTICAL_IDS)}
    kernel = _load_kernel()
    body = dict(payload)
    body.setdefault("vertical_id", vertical_id)
    result = kernel.evaluate(body)
    result["ok"] = True
    result["status"] = STATUS
    result["data_label"] = DATA_LABEL
    result["vertical_id"] = vertical_id
    result["runtime_claimed"] = False
    return result


def register(app, ns: str = "a11oy") -> dict[str, Any]:
    try:
        from starlette.responses import FileResponse, JSONResponse
        from starlette.routing import Route
    except Exception as exc:  # pragma: no cover
        return {"registered": [], "status": f"starlette-absent: {exc!r}"}

    def _json(payload: dict[str, Any], status_code: int = 200) -> JSONResponse:
        return JSONResponse(payload, status_code=status_code)

    async def _index(_request):
        try:
            return _json(catalog())
        except Exception as exc:  # noqa: BLE001
            return _json({"ok": False, "error": str(exc), "status": STATUS}, 503)

    async def _healthz(_request):
        try:
            kernel = _load_kernel()
            present = [
                vid
                for vid in VERTICAL_IDS
                if (VERTICALS_DIR / vid / "vertical_manifest.json").is_file()
            ]
            return _json(
                {
                    "ok": True,
                    "status": STATUS,
                    "data_label": DATA_LABEL,
                    "kernel_version": getattr(kernel, "VERSION", "UNKNOWN"),
                    "verticals": present,
                    "runtime_claimed": False,
                }
            )
        except Exception as exc:  # noqa: BLE001
            return _json({"ok": False, "error": str(exc), "status": STATUS}, 503)

    async def _vertical(request):
        vertical_id = request.path_params["vertical"]
        if vertical_id not in VERTICAL_IDS:
            return _json({"error": "unknown vertical", "verticals": list(VERTICAL_IDS)}, 404)
        try:
            packed = load_vertical(vertical_id)
        except FileNotFoundError as exc:
            return _json({"error": str(exc), "status": STATUS}, 503)
        return _json(
            {
                "id": packed["id"],
                "display_name": packed["display_name"],
                "wedge": packed["wedge"],
                "role": packed["role"],
                "status": STATUS,
                "data_label": DATA_LABEL,
                "formula_authority": "NONE",
                "manifest": packed["manifest"],
                "policy": packed["policy"],
                "cases": packed["cases"],
            }
        )

    async def _evaluate(request):
        vertical_id = request.path_params["vertical"]
        try:
            payload = await request.json()
        except Exception:
            return _json({"error": "expected JSON body"}, 400)
        if not isinstance(payload, dict):
            return _json({"error": "expected JSON object"}, 400)
        if vertical_id not in VERTICAL_IDS:
            return _json({"error": "unknown vertical", "verticals": list(VERTICAL_IDS)}, 404)
        try:
            return _json(evaluate_case(vertical_id, payload))
        except Exception as exc:  # noqa: BLE001
            return _json({"ok": False, "error": str(exc), "status": STATUS}, 400)

    async def _scan(request):
        try:
            payload = await request.json()
        except Exception:
            return _json({"error": "expected JSON body"}, 400)
        kernel = _load_kernel()
        text = ""
        if isinstance(payload, dict):
            text = str(payload.get("text") or "")
        return _json(kernel.scan_memo(text))

    async def _replay(request):
        try:
            payload = await request.json()
        except Exception:
            return _json({"error": "expected JSON body"}, 400)
        kernel = _load_kernel()
        receipt = payload if isinstance(payload, dict) else {}
        return _json(kernel.replay_receipt(receipt))

    async def _page(_request):
        for base in (Path("/app/pages"), PAGES_DIR):
            page = base / "decision.html"
            if page.is_file():
                return FileResponse(str(page), media_type="text/html")
        return _json({"error": "decision page missing", "status": STATUS}, 503)

    # insert(0) last-wins. Literal healthz must be inserted after {vertical}.
    paths = [
        (f"/api/{ns}/v1/decision", _index, ["GET"]),
        (f"/api/{ns}/v1/decision/{{vertical}}", _vertical, ["GET"]),
        (f"/api/{ns}/v1/decision/{{vertical}}/evaluate", _evaluate, ["POST"]),
        (f"/api/{ns}/v1/decision/{{vertical}}/scan", _scan, ["POST"]),
        (f"/api/{ns}/v1/decision/{{vertical}}/replay", _replay, ["POST"]),
        (f"/api/{ns}/v1/decision/healthz", _healthz, ["GET"]),
        ("/v1/decision", _index, ["GET"]),
        ("/v1/decision/healthz", _healthz, ["GET"]),
    ]
    for alias in PAGE_ALIASES:
        paths.append((alias, _page, ["GET", "HEAD"]))
    registered = []
    for path, fn, methods in paths:
        app.router.routes.insert(0, Route(path, fn, methods=methods))
        registered.append(path)
    return {
        "registered": registered,
        "status": "ok",
        "module": "a11oy_decision_integrity",
        "surface_status": STATUS,
    }
