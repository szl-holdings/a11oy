# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings
"""Packet 8 Decision Integrity on a-11-oy.com.

Mounts GET /decision and vanity paths /terra /aegis /puriq-markets /puriq
/counsel /vessels plus /demo /evaluations and /api/a11oy/v1/decision/*.
Evaluates frozen demonstration cases through verticals/_kernel/a11oy_kernel.py.

Vessels is a product vanity path on the same kernel. It is not a fifth
flagship and not a new Hub Space. Hub Space create is capped at 20/day.

Formula authority NONE. Models and market signals never authorize.
Status stays ROADMAP. Does not stamp LIVE. Does not wait on Hub Spaces.
Does not claim ATO. Licensed AIS without a live key stays CLOSED.
Λ = Conjecture 1 / ADVISORY_CONJECTURAL.
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

VERTICAL_IDS = ("terra", "aegis", "puriq-markets", "counsel", "vessels")
PAGE_FILES = {
    "/decision": "decision.html",
    "/a11oy/decision": "decision.html",
    "/terra": "decision.html",
    "/aegis": "decision.html",
    "/puriq-markets": "decision.html",
    "/puriq": "decision.html",
    "/counsel": "decision.html",
    "/vessels": "decision.html",
    "/demo": "demo.html",
    "/evaluations": "evaluations.html",
}
PAGE_ALIASES = tuple(PAGE_FILES)
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


def _vessels_ais_standards_pack() -> dict[str, Any] | None:
    path = VERTICALS_DIR / "vessels" / "ais_standards.json"
    if not path.is_file():
        return None
    packed = _read_json(path)
    return packed if isinstance(packed, dict) else None


def _vessels_ais_standards_echo(pack: dict[str, Any] | None = None) -> dict[str, Any]:
    standards = pack if isinstance(pack, dict) else _vessels_ais_standards_pack() or {}
    instruments = [
        row.get("id")
        for row in (standards.get("instruments") or [])
        if isinstance(row, dict) and row.get("id")
    ]
    return {
        "honesty": "CITATION_ONLY",
        "licensed_ais_admitted": False,
        "licensed_ais_queries": 0,
        "ais_equipment_class": "NONE",
        "ais_transmit": False,
        "solas_v19_applies": False,
        "aton_provider": False,
        "vhf_data_link_occupied": False,
        "vessels_e03_licensed_ais_tpr": standards.get("vessels_e03_licensed_ais_tpr", "OUTSTANDING"),
        "fail_closed_eval": "VESSELS-E-DENY-AIS",
        "proof": "https://a11oy.net/vessels/ais-standards.json",
        "instruments": instruments,
        "stamps_live": False,
        "production_ready": False,
    }


AIS_LATTICE_DIGEST = "f931b48544bcf70b1ca0d1c03b38b6c8e9dbf1933adfb8128316324e82eeb457"
AIS_LATTICE_PROOF = "https://a11oy.net/vessels/ais-lattice.json"
AIS_LATTICE_HTML = "https://a11oy.net/vessels/lattice/"

PUBLIC_LISTS_DIGEST = "70fd1918fb38791159cfa2c520dc989f32125e4e0de4104b59d0a26fa48e1cb5"
PUBLIC_LISTS_PROOF = "https://a11oy.net/vessels/public-lists-world.json"
PUBLIC_LISTS_HTML = "https://a11oy.net/vessels/world/"
PUBLIC_LIST_LATTICE_DIGEST = "b2d23ac69631667c09a8e3c4715d9a7caabda23edc9739b74d743fe6d9f88c1d"
PUBLIC_LIST_LATTICE_PROOF = "https://a11oy.net/vessels/public-list-lattice.json"
JOINT_FRESHNESS_DIGEST = "1cb5b1178b7cda2327443eb7b8e33703aae26a23b4102a0d5f91291cff149898"
JOINT_FRESHNESS_PROOF = "https://a11oy.net/vessels/joint-freshness.json"


def _vessels_public_lists_pack() -> dict[str, Any] | None:
    path = VERTICALS_DIR / "vessels" / "public_lists.json"
    if not path.is_file():
        return None
    packed = _read_json(path)
    return packed if isinstance(packed, dict) else None



def _vessels_advisory_jev(identity: str = "AURORA WAVE", snippet: str = "") -> dict[str, Any]:
    """Advisory TypeSafe/Jev sidecar. Cannot change Packet 8 state."""
    try:
        import szl_jev_gate as _jev
        judged = _jev.judge_public_text(identity, snippet)
    except Exception as exc:  # pragma: no cover
        judged = {
            "schema": "szl.jev_public_text/v1",
            "source": "unavailable",
            "reason": type(exc).__name__,
            "promotion": "denied",
            "is_clearance": False,
            "miss_is_not_clearance": True,
            "winner_not_picked": True,
            "licensed_ais_admitted": False,
            "not_e01": True,
            "does_not_run_the_kernel": True,
        }
    judged["promotion"] = "denied"
    judged["does_not_run_the_kernel"] = True
    judged["cannot_change_state"] = True
    judged["is_clearance"] = False
    judged["miss_is_not_clearance"] = True
    judged["winner_not_picked"] = True
    judged["licensed_ais_admitted"] = False
    return judged


def _vessels_public_lists_echo(pack: dict[str, Any] | None = None) -> dict[str, Any]:
    """Citation echo only. Does not resolve IMO/owner. Not the Packet 8 kernel."""
    packed = pack if isinstance(pack, dict) else _vessels_public_lists_pack() or {}
    clocks = []
    for row in packed.get("clocks") or []:
        if isinstance(row, dict) and row.get("id"):
            clocks.append(
                {
                    "id": row.get("id"),
                    "http": row.get("http"),
                    "bytes": row.get("bytes"),
                    "last_modified": row.get("last_modified"),
                    "freshness": row.get("freshness"),
                    "class": row.get("class", "MEASURED"),
                }
            )
    judgment = packed.get("typed_judgment") if isinstance(packed.get("typed_judgment"), dict) else {}
    joint = packed.get("joint_freshness") if isinstance(packed.get("joint_freshness"), dict) else {}
    negative = joint.get("negative_evidence") if isinstance(joint.get("negative_evidence"), dict) else {}
    return {
        "honesty": "CITATION_ONLY",
        "licensed_ais_admitted": False,
        "licensed_ais_queries": 0,
        "production_ready": False,
        "stamps_live": False,
        "vessels_e01": packed.get("vessels_e01", "OUTSTANDING"),
        "vessels_e03": packed.get("vessels_e03", "OUTSTANDING"),
        "digest": packed.get("digest") or PUBLIC_LISTS_DIGEST,
        "authority_lattice_digest": packed.get("authority_lattice_digest") or PUBLIC_LIST_LATTICE_DIGEST,
        "ais_lattice_digest_unchanged": packed.get("ais_lattice_digest_unchanged") or AIS_LATTICE_DIGEST,
        "joint_freshness_digest": joint.get("digest") or JOINT_FRESHNESS_DIGEST,
        "authority_classes": list(packed.get("authority_classes") or [
            "OFAC-vessel",
            "UN-1718-vessel",
            "UK-specified-ship",
            "UA-GUR-ship",
            "KR-MOFA-vessel",
            "IUU-RFMO",
            "Paris-banned",
        ]),
        "freshness_classes": list(packed.get("freshness_classes") or [
            "REACHABLE_FRESH",
            "STALE_OR_THIN",
            "PAGE_CITE",
            "REPORTED",
            "UNAVAILABLE",
            "REFUSED",
        ]),
        "clocks": clocks,
        "typed_judgment": {
            "engine": judgment.get("engine", "stdlib exact-string SAMPLE"),
            "frozen_identity": judgment.get("frozen_identity", "AURORA WAVE"),
            "result": judgment.get("result", "SAMPLE_TEXT_MISS"),
            "miss_is_not_clearance": True,
            "not_e01": True,
        },
        "fail_closed_eval_stale": packed.get("fail_closed_eval_stale", "VESSELS-E-ABSTAIN"),
        "fail_closed_eval_ais": packed.get("fail_closed_eval_ais", "VESSELS-E-DENY-AIS"),
        "joint_freshness": {
            "honesty": "CITATION_ONLY",
            "digest": joint.get("digest") or JOINT_FRESHNESS_DIGEST,
            "rule": joint.get("rule", "min-link over current official clocks; stale twins are disagreement; winner not picked"),
            "winner_not_picked": True,
            "does_not_run_the_kernel": True,
            "classes": list(joint.get("classes") or []),
            "disagreements": list(joint.get("disagreements") or []),
            "coverage_holes": list(joint.get("coverage_holes") or []),
            "negative_evidence": {
                "engine": negative.get("engine", "stdlib exact-string SAMPLE"),
                "frozen_identity": negative.get("frozen_identity", "AURORA WAVE"),
                "result": negative.get("result", "SAMPLE_TEXT_MISS"),
                "miss_is_not_clearance": True,
                "is_clearance": False,
                "not_e01": True,
                "not_typesafe_jev_call": True,
            },
            "proof": joint.get("proof") or JOINT_FRESHNESS_PROOF,
        },
        "proof": PUBLIC_LISTS_PROOF,
        "html": PUBLIC_LISTS_HTML,
        "authority_lattice": PUBLIC_LIST_LATTICE_PROOF,
        "note": (
            "Official-list names are authority classes. Cite admitted. "
            "Radio query DENIED. Clocks are reachability. "
            "Min-link joint freshness names coverage holes and disagreements. "
            "Winner not picked. Typed judgment is SAMPLE. Miss is not clearance. "
            "Advisory Jev cannot change Packet 8 state. "
            "Lattice classify is not the Packet 8 kernel."
        ),
        "advisory_jev": _vessels_advisory_jev(
            str((judgment.get("frozen_identity") or "AURORA WAVE")),
            "public-list clocks CITATION_ONLY; SAMPLE miss is not clearance",
        ),
    }



def _vessels_ais_lattice_pack() -> dict[str, Any] | None:
    path = VERTICALS_DIR / "vessels" / "ais_lattice.json"
    if not path.is_file():
        return None
    packed = _read_json(path)
    return packed if isinstance(packed, dict) else None


def _vessels_ais_lattice_echo(pack: dict[str, Any] | None = None) -> dict[str, Any]:
    """Citation echo only. Does not classify radio. Not the Packet 8 kernel."""
    lattice = pack if isinstance(pack, dict) else _vessels_ais_lattice_pack() or {}
    types = lattice.get("message_types") or []
    refused = [
        row.get("id")
        for row in (lattice.get("open_source_codecs_refused") or [])
        if isinstance(row, dict) and row.get("id")
    ]
    lists = [
        {
            "id": row.get("id"),
            "url": row.get("url"),
            "http": row.get("http"),
            "bytes": row.get("bytes"),
            "last_modified": row.get("last_modified"),
            "class": row.get("class", "MEASURED"),
        }
        for row in (lattice.get("public_lists_measured") or [])
        if isinstance(row, dict) and row.get("id")
    ]
    return {
        "honesty": "CITATION_ONLY",
        "licensed_ais_admitted": False,
        "licensed_ais_queries": 0,
        "ais_transmit": False,
        "vhf_data_link_occupied": False,
        "ais_equipment_class": "NONE",
        "production_ready": False,
        "stamps_live": False,
        "vessels_e03_licensed_ais_tpr": lattice.get("vessels_e03_licensed_ais_tpr", "OUTSTANDING"),
        "digest": lattice.get("digest") or AIS_LATTICE_DIGEST,
        "message_types": len(types) if isinstance(types, list) else 0,
        "codecs_refused": refused,
        "public_lists": lists,
        "fail_closed_eval": "VESSELS-E-DENY-AIS",
        "proof": AIS_LATTICE_PROOF,
        "html": AIS_LATTICE_HTML,
        "note": (
            "Types are authority classes. Cite admitted. Live query DENIED. "
            "Lattice classify is not the Packet 8 kernel."
        ),
    }


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
    packed = {
        "id": vertical_id,
        "display_name": manifest.get("display_name", vertical_id),
        "wedge": manifest.get("wedge", ""),
        "role": manifest.get("role", ""),
        "manifest": manifest,
        "policy": policy,
        "cases": cases,
    }
    if vertical_id == "vessels":
        standards = _vessels_ais_standards_pack()
        if standards is not None:
            packed["ais_standards"] = standards
        lattice = _vessels_ais_lattice_pack()
        if lattice is not None:
            packed["ais_lattice"] = lattice
        public_lists = _vessels_public_lists_pack()
        if public_lists is not None:
            packed["public_lists"] = public_lists
    return packed


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
        "licensed_ais_admitted": False,
        "production_ready": False,
        "note": (
            "Frozen demonstration cases on the canonical a11oy site. "
            "Does not prove production readiness. Does not stamp LIVE. "
            "Licensed AIS stays CLOSED without a live key. "
            "Not legal advice, not a trading bot, not a Palantir clone."
        ),
        "verticals": [
            {
                "id": item["id"],
                "display_name": item["display_name"],
                "wedge": item["wedge"],
                "role": item["role"],
                "case_count": len(item["cases"]),
                **(
                    {
                        "ais_standards_honesty": "CITATION_ONLY",
                        "ais_lattice_honesty": "CITATION_ONLY",
                        "ais_lattice_digest": AIS_LATTICE_DIGEST,
                        "ais_lattice_message_types": 27,
                        "public_lists_honesty": "CITATION_ONLY",
                        "public_lists_digest": PUBLIC_LISTS_DIGEST,
                        "public_list_lattice_digest": PUBLIC_LIST_LATTICE_DIGEST,
                        "public_list_authority_classes": 7,
                        "joint_freshness_digest": JOINT_FRESHNESS_DIGEST,
                        "licensed_ais_admitted": False,
                        "vessels_e03_licensed_ais_tpr": "OUTSTANDING",
                    }
                    if item["id"] == "vessels"
                    else {}
                ),
            }
            for item in verticals
        ],
        "desks": {
            "decision": "/decision",
            "demo": "/demo",
            "evaluations": "/evaluations",
            "vessels": "/vessels",
            "ais_standards": "https://a11oy.net/vessels/ais-standards.json",
            "ais_lattice": "https://a11oy.net/vessels/ais-lattice.json",
            "ais_lattice_html": "https://a11oy.net/vessels/lattice/",
            "public_lists": "https://a11oy.net/vessels/public-lists-world.json",
            "public_lists_html": "https://a11oy.net/vessels/world/",
            "public_list_lattice": "https://a11oy.net/vessels/public-list-lattice.json",
            "joint_freshness": "https://a11oy.net/vessels/joint-freshness.json",
            "proof": "https://a11oy.net/decision/",
        },
    }


_CASE_MATERIAL = (
    "graph",
    "sources",
    "evidence",
    "proposed_action",
    "allowed_actions",
)


def _has_case_material(payload: dict[str, Any]) -> bool:
    return any(payload.get(key) for key in _CASE_MATERIAL)


def resolve_eval_payload(vertical_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Accept inner kernel binds, frozen wrappers, or eval_id / case_id lookups."""
    body = dict(payload)
    inner = body.get("payload")
    if isinstance(inner, dict) and _has_case_material(inner):
        resolved = dict(inner)
        resolved.setdefault("vertical_id", vertical_id)
        return resolved
    if not _has_case_material(body):
        key = body.get("eval_id") or body.get("case_id")
        if key:
            packed = load_vertical(vertical_id)
            for case in packed["cases"]:
                if key in {case.get("eval_id"), case.get("case_id")}:
                    seed = case.get("payload") if isinstance(case.get("payload"), dict) else case
                    resolved = dict(seed)
                    resolved.setdefault("vertical_id", vertical_id)
                    return resolved
    body.setdefault("vertical_id", vertical_id)
    return body


def evaluate_case(vertical_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    if vertical_id not in VERTICAL_IDS:
        return {"ok": False, "error": "unknown vertical", "verticals": list(VERTICAL_IDS)}
    kernel = _load_kernel()
    body = resolve_eval_payload(vertical_id, payload)
    result = kernel.evaluate(body)
    result["ok"] = True
    result["status"] = STATUS
    result["data_label"] = DATA_LABEL
    result["vertical_id"] = vertical_id
    result["runtime_claimed"] = False
    if vertical_id == "vessels":
        result["licensed_ais_admitted"] = False
        result["ais_standards"] = _vessels_ais_standards_echo()
        result["ais_lattice"] = _vessels_ais_lattice_echo()
        result["public_lists"] = _vessels_public_lists_echo()
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
                    "licensed_ais_admitted": False,
                    "production_ready": False,
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
        body = {
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
        if packed.get("ais_standards") is not None:
            body["licensed_ais_admitted"] = False
            body["ais_standards"] = packed["ais_standards"]
        if packed.get("ais_lattice") is not None:
            body["ais_lattice"] = packed["ais_lattice"]
        if packed.get("public_lists") is not None:
            body["public_lists"] = packed["public_lists"]
        return _json(body)

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

    async def _page(request):
        path = (request.url.path or "").rstrip("/") or "/decision"
        filename = PAGE_FILES.get(path, "decision.html")
        for base in (Path("/app/pages"), PAGES_DIR):
            page = base / filename
            if page.is_file():
                return FileResponse(str(page), media_type="text/html")
        return _json({"error": "decision page missing", "status": STATUS}, 503)

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
