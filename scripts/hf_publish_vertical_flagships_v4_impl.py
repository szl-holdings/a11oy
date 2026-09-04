#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Policy overlay for the immutable Domain Experience v4 renderer.

The generated renderer stays byte-identical in the adjacent base module. This
module applies the reviewed Sentra receipt-verifier semantics and the truthful
generated-runtime contract while preserving Terra forge 0.2.2, the current
Lyte source pin, every non-Sentra vertical, and the canonical single-writer
publisher contract.

Importing this module performs no network or provider mutation. Direct
execution is refused; only the canonical estate publisher may admit writes.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import importlib.util
import json
import os
import time
from pathlib import Path
from types import ModuleType
from typing import Any

from huggingface_hub import HfApi

BASE_IMPLEMENTATION_PATH = Path(__file__).with_name(
    "_hf_publish_vertical_flagships_v4_impl_base.py"
)
SENTRA_OVERLAY_VERSION = "receipt-verifier/v1"


def _load_base() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "szl_hf_vertical_flagships_v4_base", BASE_IMPLEMENTATION_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load immutable flagship base: {BASE_IMPLEMENTATION_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_BASE = _load_base()
if getattr(_BASE, "TERRA_FORGE_MARKER", None) != 'data-szl-vertical-forge="0.2.2"':
    raise RuntimeError("immutable flagship base is not Terra forge 0.2.2")
if getattr(_BASE, "TERRA_FORGE_GENERATOR", None) != "szl-vertical-forge/0.2.2":
    raise RuntimeError("immutable flagship base has an unexpected Terra generator")

_sentra = {
    "slug": "sentra",
    "title": "Sentra",
    "vertical": "ASSURANCE COMMAND",
    "short": "Public receipt verification and assurance evidence",
    "source": (
        "https://github.com/szl-holdings/a11oy/blob/main/"
        "scripts/hf_publish_vertical_flagships_v4_impl.py"
    ),
    "upstream": (
        "https://szlholdings-a11oy.hf.space/api/a11oy/v1/verify/receipt"
    ),
    "workflow": ("RECEIPT", "SIGNATURE", "DIGEST", "CHAIN", "VERDICT"),
    "lens": "receipt",
    "labels": ("Verifier contract", "Integrity checks", "Evidence verdict"),
}

_REQUIRED_EVIDENCE_PATHS: dict[str, tuple[str, ...]] = {
    "terra": ("hpd_litigations", "dob_violations", "rates"),
    "sentra": ("state", "evidence", "try"),
    "counsel": ("federal_register", "court_filings"),
    "finance": ("equities_official", "equities", "crypto", "fx", "fintech_cve"),
    "vessels": ("$",),
    "lyte": (
        "observed",
        "observed_at",
        "melt.metrics.dag_depth",
        "melt.events.signed_spans",
    ),
}

_rows = tuple(getattr(_BASE, "FLAGSHIPS", ()))
if sum(1 for row in _rows if row.get("slug") == "sentra") != 1:
    raise RuntimeError("immutable flagship base must contain exactly one Sentra row")
_BASE.FLAGSHIPS = tuple(
    _sentra if row.get("slug") == "sentra" else row for row in _rows
)

_BASE.DOMAIN_CSS = dict(getattr(_BASE, "DOMAIN_CSS", {}))
_BASE.DOMAIN_CSS["sentra"] = r''':root{--bg:#030506;--panel:rgba(7,12,15,.92);--muted:#8ca1a8;--accent:#54f0d1;--accent2:#ff5d73}.domain{margin-top:48px;display:grid;grid-template-columns:minmax(0,1fr) minmax(300px,.8fr);gap:14px}.verification{min-height:410px;position:relative;overflow:hidden;background:radial-gradient(circle at 30% 30%,rgba(84,240,209,.08),transparent 35%),linear-gradient(rgba(84,240,209,.045) 1px,transparent 1px),linear-gradient(90deg,rgba(84,240,209,.045) 1px,transparent 1px);background-size:auto,28px 28px,28px 28px}.node{position:absolute;inline-size:74px;block-size:74px;border:1px solid var(--accent);border-radius:50%;display:grid;place-items:center;background:#061014;font:800 9px ui-monospace,monospace;text-align:center}.n1{left:8%;top:18%}.n2{left:42%;top:10%}.n3{right:8%;top:38%;border-color:var(--accent2)}.n4{left:34%;bottom:9%}.path{position:absolute;block-size:1px;background:linear-gradient(90deg,var(--accent),var(--accent2));transform-origin:left center}.x1{left:16%;top:27%;inline-size:31%;transform:rotate(-8deg)}.x2{left:49%;top:20%;inline-size:37%;transform:rotate(25deg)}.x3{left:42%;top:65%;inline-size:42%;transform:rotate(-22deg)}.queue{display:grid;gap:8px}.incident{padding:12px;border:1px solid var(--line);display:grid;grid-template-columns:64px 1fr;gap:10px}.sev{font:900 10px ui-monospace,monospace;color:var(--accent2)}@media(max-width:850px){.domain{grid-template-columns:1fr}}'''

_BASE.DOMAIN_HTML = dict(getattr(_BASE, "DOMAIN_HTML", {}))
_BASE.DOMAIN_HTML["sentra"] = '''<div class="domain"><section class="panel verification" aria-label="Illustrative receipt verification graph" data-evidence-state="SAMPLE"><span class="illus">Illustrative — schematic, not live data</span><span class="path x1"></span><span class="path x2"></span><span class="path x3"></span><div class="node n1">RECEIPT</div><div class="node n2">SIGNATURE</div><div class="node n3">DIGEST</div><div class="node n4">CHAIN</div></section><aside class="panel queue" data-evidence-state="SAMPLE"><span class="illus">Illustrative — schematic, not live data</span><div class="mono">VERIFICATION EVIDENCE QUEUE</div><div class="incident"><span class="sev">CONTRACT</span><span>The live upstream describes the public verifier and its supported checks; it does not claim a receipt verdict.</span></div><div class="incident"><span class="sev">VERDICT</span><span>PASS requires an actual caller-supplied receipt and successful signature, payload-digest, and hash-chain checks.</span></div><div class="incident"><span class="sev">SCOPE</span><span>This read-only surface performs no admission or approval. Sentra is the sole Assurance Command; Aegis is decommissioned history and IMMUNE is an engine under Sentra, with runtime migration UNVERIFIED.</span></div></aside></div>'''

_TRUTHFUL_APP = r'''import datetime as dt,hashlib,json,time,urllib.request
from pathlib import Path
import httpx
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
CFG=json.loads(Path("config.json").read_text(encoding="utf-8"))
INDEX=Path("index.html").read_text(encoding="utf-8")
PANELS=Path("panels.html").read_text(encoding="utf-8")
app=FastAPI(title=CFG["title"]+" - SZL Holdings")

PUBLIC_EVIDENCE_STATES=("LIVE","CACHED","DEGRADED","UNAVAILABLE")
_LIVE_MARKERS={"LIVE","OBSERVED","MEASURED","READY","OK","AVAILABLE","CONNECTED","CURRENT","HEALTHY","UP"}
_CACHED_MARKERS={"CACHED","CACHE","STALE","LAST_GOOD"}
_DEGRADED_MARKERS={"DEGRADED","PARTIAL","MIXED","WARNING"}
_UNAVAILABLE_MARKERS={"UNAVAILABLE","UNKNOWN","INVALID","FAILED","FAILURE","ERROR","EMPTY","OFFLINE","BLOCKED","NOT_AVAILABLE","NOT_OBSERVED","INCOMPLETE","DOWN"}
_STATE_KEYS=("status","state","observation_state","data_state","evidence_state","availability")
_META_KEYS={"schema","note","honesty","doctrine","source","source_url","url","leader","data_kind","vertical","pitch"}

def sha256_text(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()

def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00","Z")

def _marker_state(value):
    if not isinstance(value,str):
        return None
    marker=value.strip().upper().replace("-","_").replace(" ","_")
    if marker in _LIVE_MARKERS: return "LIVE"
    if marker in _CACHED_MARKERS: return "CACHED"
    if marker in _DEGRADED_MARKERS: return "DEGRADED"
    if marker in _UNAVAILABLE_MARKERS: return "UNAVAILABLE"
    return None

def _merge_states(states):
    values=[state for state in states if state in PUBLIC_EVIDENCE_STATES]
    if not values or all(state=="UNAVAILABLE" for state in values): return "UNAVAILABLE"
    if "UNAVAILABLE" in values or "DEGRADED" in values: return "DEGRADED"
    if "CACHED" in values: return "CACHED"
    return "LIVE"

def classify_evidence(value):
    """Classify response content without trusting a green parent label."""
    if value is None: return "UNAVAILABLE"
    if isinstance(value,bool): return "LIVE" if value else "UNAVAILABLE"
    if isinstance(value,(int,float)): return "LIVE"
    if isinstance(value,str): return _marker_state(value) or ("LIVE" if value.strip() else "UNAVAILABLE")
    if isinstance(value,list):
        if not value: return "DEGRADED"
        return _merge_states([classify_evidence(item) for item in value])
    if not isinstance(value,dict) or not value: return "UNAVAILABLE"
    states=[]
    substantive=False
    for key in _STATE_KEYS:
        if key in value: states.append(_marker_state(value.get(key)) or "UNAVAILABLE")
    for key in ("observed","live","available","ready","ok"):
        if key in value and isinstance(value.get(key),bool):
            states.append("LIVE" if value[key] else "UNAVAILABLE")
    freshness=value.get("freshness")
    if isinstance(freshness,dict):
        states.append(_marker_state(freshness.get("status")) or "UNAVAILABLE")
        if freshness.get("status") not in (None,"unavailable","UNAVAILABLE") and freshness.get("fetched_at") is None:
            states.append("UNAVAILABLE")
    if value.get("error") not in (None,"",False) and "CACHED" not in states:
        states.append("UNAVAILABLE")
    for key,child in value.items():
        if key in _META_KEYS or key in _STATE_KEYS or key in {"freshness","error","observed","live","available","ready","ok"}: continue
        if key in {"value","data","result","results","items","records","metrics","events","observed_at","fetched_at"}:
            states.append(classify_evidence(child))
            substantive=substantive or child not in (None,"",[],{})
        elif isinstance(child,(dict,list)):
            states.append(classify_evidence(child))
            substantive=substantive or bool(child)
        elif child not in (None,""): substantive=True
    if states and not substantive: states.append("UNAVAILABLE")
    if not states: return "LIVE" if substantive else "UNAVAILABLE"
    return _merge_states(states)

def _resolve_path(payload,path):
    if path=="$": return True,payload
    current=payload
    for part in path.split("."):
        if not isinstance(current,dict) or part not in current: return False,None
        current=current[part]
    return True,current

def classify_required_evidence(payload,paths):
    observations=[]
    for path in list(paths or ["$"]):
        present,value=_resolve_path(payload,path)
        observations.append({"path":path,"present":present,"state":classify_evidence(value) if present else "UNAVAILABLE"})
    return {"status":_merge_states([item["state"] for item in observations]),"required":observations}

def local_integrity():
    checks={"landing_sha256":sha256_text(INDEX)==CFG["landing_sha256"],"panels_sha256":sha256_text(PANELS)==CFG["panels_sha256"]}
    ready=all(checks.values())
    return {"schema":"szl.vertical-shell-readiness/v1","ready":ready,"state":"MEASURED" if ready else "INVALID","scope":"LOCAL_RUNTIME_ARTIFACTS_ONLY","checks":checks,"routes":{"landing":"/","panels":"/panels","liveness":"/livez","readiness":"/readyz","live_evidence":"/api/live","receipt":"/build-receipt.json"}}

def probe():
    started=time.time(); observed_at=utc_now()
    try:
        response=httpx.get(CFG["upstream"],timeout=15,headers={"User-Agent":"SZLHOLDINGS-Flagship/4.0","Accept":"application/json"})
        elapsed=round((time.time()-started)*1000,1)
        if not response.is_success:
            return {"schema":"szl.vertical-evidence-observation/v2","status":"UNAVAILABLE","http_status":response.status_code,"latency_ms":elapsed,"observed_at":observed_at,"source":CFG["upstream"],"evidence":{"status":"UNAVAILABLE","required":[]},"data":None}
        if "json" not in response.headers.get("content-type","").lower():
            return {"schema":"szl.vertical-evidence-observation/v2","status":"UNAVAILABLE","http_status":response.status_code,"latency_ms":elapsed,"observed_at":observed_at,"source":CFG["upstream"],"error":"NON_JSON_UPSTREAM","evidence":{"status":"UNAVAILABLE","required":[]},"data":None}
        body=response.json(); evidence=classify_required_evidence(body,CFG.get("required_evidence_paths"))
        return {"schema":"szl.vertical-evidence-observation/v2","status":evidence["status"],"http_status":response.status_code,"latency_ms":elapsed,"observed_at":observed_at,"source":CFG["upstream"],"evidence":evidence,"data":body}
    except Exception as exc:
        return {"schema":"szl.vertical-evidence-observation/v2","status":"UNAVAILABLE","latency_ms":round((time.time()-started)*1000,1),"observed_at":observed_at,"error":type(exc).__name__,"source":CFG["upstream"],"evidence":{"status":"UNAVAILABLE","required":[]},"data":None}

def probe_summary(observation): return {key:value for key,value in observation.items() if key!="data"}

def hf_revision():
    try:
        req=urllib.request.Request("https://huggingface.co/api/spaces/"+CFG["hf_repository"],headers={"Accept":"application/json","User-Agent":"SZLHOLDINGS-BuildInfo/1.0"})
        with urllib.request.urlopen(req,timeout=10) as response: payload=json.loads(response.read().decode("utf-8"))
        value=str(payload.get("sha") or "").lower()
        return value if len(value)==40 and all(ch in "0123456789abcdef" for ch in value) else "UNAVAILABLE"
    except Exception: return "UNAVAILABLE"

def process_liveness(): return {"schema":"szl.vertical-process-liveness/v1","ok":True,"status":"LIVE","scope":"PROCESS_ONLY","dependencies_checked":False,"product":CFG["title"],"domain":CFG["slug"]}

@app.get("/healthz")
def healthz(): return process_liveness()

@app.get("/livez")
def livez(): return process_liveness()

@app.get("/readyz")
def readyz():
    integrity=local_integrity(); dependency=probe()
    ready=integrity["ready"] and dependency["status"] in ("LIVE","CACHED")
    payload={"schema":"szl.vertical-shell-readiness/v1","ready":ready,"state":"MEASURED" if ready else "NOT_READY","local_integrity":integrity,"required_dependency":probe_summary(dependency),"accepted_dependency_states":["LIVE","CACHED"]}
    return JSONResponse(payload,status_code=200 if ready else 503)

@app.get("/api/live")
def live(): return JSONResponse(probe())

@app.get("/api/capabilities")
def capabilities(): return {"schema":"szl.vertical-capabilities/v1","product":CFG["slug"],"access":"READ_ONLY","declared_workflow":CFG.get("workflow",[]),"evidence_route":"/api/live","write_endpoints":[]}

@app.get("/api/data-sources")
def data_sources():
    observation=probe()
    return {"schema":"szl.vertical-data-sources/v1","source":CFG["upstream"],"required_evidence_paths":CFG.get("required_evidence_paths",["$"]),"observation":probe_summary(observation)}

@app.get("/api/doctrine")
def doctrine(): return {"schema":"szl.public-doctrine/v1","honest_evidence_states":["LIVE","CACHED","DEGRADED","UNAVAILABLE","SAMPLE"],"non_runtime_evidence_labels":["MEASURED","REPORTED","MODELED"],"locked_formula_ids":["F1","F4","F7","F11","F12","F18","F19","F22"],"lambda_status":"CONJECTURE_1","read_routes_have_side_effects":False,"sample_policy":"Illustrative interface graphics are SAMPLE and are not upstream observations."}

@app.get("/api/demo")
def demo(): return {"schema":"szl.vertical-demo-disclosure/v1","state":"SAMPLE","observed":False,"visual_surface":"ILLUSTRATIVE_SCHEMATIC","live_evidence_route":"/api/live","note":"The rendered domain graphic is a sample interface. Only /api/live reports bounded upstream observations."}

@app.get("/api/provenance/verify")
def provenance_verify():
    integrity=local_integrity(); revision=str(CFG["source_revision"]).lower()
    revision_format_valid=len(revision)==40 and all(ch in "0123456789abcdef" for ch in revision)
    workflow_id_valid=isinstance(CFG["workflow_run_id"],int) and CFG["workflow_run_id"]>0
    verified=integrity["ready"] and revision_format_valid and workflow_id_valid
    payload={"schema":"szl.vertical-provenance-verification/v1","state":"VERIFIED_LOCAL_ARTIFACTS" if verified else "INVALID_LOCAL_ARTIFACTS","verification_scope":"LOCAL_RUNTIME_ARTIFACTS_AND_CONFIG_FORMAT_ONLY","source_revision_format_valid":revision_format_valid,"workflow_run_id_valid":workflow_id_valid,"integrity":integrity,"signature_verification":"UNAVAILABLE","external_attestation_verified":False,"receipt_minted":False,"side_effects":False}
    return JSONResponse(payload,status_code=200 if verified else 503)

@app.get("/api/source")
def source(): return {"product_source":CFG["product_source"],"deployment_source":CFG["source_repository"],"source_revision":CFG["source_revision"],"workflow_run_id":CFG["workflow_run_id"]}

@app.get("/api/build-info")
def build_info(): return JSONResponse({"schema":"szl.build-info/v1","source_repository":CFG["source_repository"],"source_revision":CFG["source_revision"],"workflow_run_id":CFG["workflow_run_id"],"hf_repository":CFG["hf_repository"],"hf_revision":hf_revision(),"artifact_set_sha256":CFG["artifact_set_sha256"],"public_experience":CFG["public_experience"],"product_source":CFG["product_source"],"forge":CFG.get("forge"),"routes":{"landing":"/","panels":"/panels","liveness":"/livez","readiness":"/readyz","live_evidence":"/api/live","capabilities":"/api/capabilities","data_sources":"/api/data-sources","doctrine":"/api/doctrine","demo":"/api/demo","provenance_verify":"/api/provenance/verify","receipt":"/build-receipt.json"}})

@app.get("/build-receipt.json")
def build_receipt():
    integrity=local_integrity()
    return JSONResponse({"schema":"szl.vertical-shell-deployment/v1","state":"VERIFIED_RUNTIME_ARTIFACTS" if integrity["ready"] else "INVALID","verification_scope":"LOCAL_RUNTIME_ARTIFACTS_ONLY","source_repository":CFG["source_repository"],"source_revision":CFG["source_revision"],"workflow_run_id":CFG["workflow_run_id"],"hf_repository":CFG["hf_repository"],"hf_revision":hf_revision(),"artifact_set_sha256":CFG["artifact_set_sha256"],"landing_sha256":CFG["landing_sha256"],"panels_sha256":CFG["panels_sha256"],"forge":CFG.get("forge"),"integrity":integrity},status_code=200 if integrity["ready"] else 503)

@app.get("/.well-known/szl-source.json")
def source_document(): return build_info()

@app.get("/",response_class=HTMLResponse)
def root(): return INDEX

@app.get("/panels",response_class=HTMLResponse)
def panels(): return PANELS
'''

for _name in dir(_BASE):
    if not _name.startswith("_"):
        globals()[_name] = getattr(_BASE, _name)

APP = _TRUTHFUL_APP
CANONICAL_ENTRYPOINT_ADMITTED = False


def _sync_contract() -> None:
    _BASE.FLAGSHIPS = tuple(FLAGSHIPS)
    _BASE.DOMAIN_CSS = dict(DOMAIN_CSS)
    _BASE.DOMAIN_HTML = dict(DOMAIN_HTML)
    _BASE.APP = APP
    _BASE.TERRA_FORGE_BUNDLE = TERRA_FORGE_BUNDLE
    _BASE.TERRA_FORGE_MARKER = TERRA_FORGE_MARKER
    _BASE.TERRA_FORGE_GENERATOR = TERRA_FORGE_GENERATOR
    _BASE.TERRA_FORGE_SOURCE_REPOSITORY = TERRA_FORGE_SOURCE_REPOSITORY


def load_terra_forge_bundle() -> tuple[str, dict[str, Any]]:
    _sync_contract()
    return _BASE.load_terra_forge_bundle()


def html(item: dict[str, Any]) -> str:
    _sync_contract()
    return _BASE.html(item)


def readme(item: dict[str, Any]) -> str:
    _sync_contract()
    return _BASE.readme(item)


def _publish_main() -> int:
    _sync_contract()
    token, token_source = token_from_env()
    api = HfApi(token=token)
    source_revision = os.getenv("GITHUB_SHA", "").strip().lower()
    workflow_run_id = os.getenv("GITHUB_RUN_ID", "").strip()
    if len(source_revision) != 40 or not all(ch in "0123456789abcdef" for ch in source_revision):
        raise RuntimeError("publisher requires an exact 40-hex GITHUB_SHA")
    if not workflow_run_id.isdigit() or int(workflow_run_id) <= 0:
        raise RuntimeError("publisher requires a positive GITHUB_RUN_ID")
    terra_page, terra_forge = load_terra_forge_bundle()
    rows: list[dict[str, Any]] = []
    for item in FLAGSHIPS:
        slug = item["slug"]
        required_evidence = _REQUIRED_EVIDENCE_PATHS.get(slug)
        if required_evidence is None:
            raise RuntimeError(f"missing required evidence contract for {slug}")
        rid = f"{ORG}/{slug}"
        panels = html(item)
        page = terra_page if slug == "terra" else panels
        forge = terra_forge if slug == "terra" else None
        root_marker = TERRA_FORGE_MARKER if slug == "terra" else PUBLIC_EXPERIENCE_MARKER
        card = readme(item)
        forge_payload = json.dumps(forge, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        landing_sha256 = hashlib.sha256(page.encode("utf-8")).hexdigest()
        panels_sha256 = hashlib.sha256(panels.encode("utf-8")).hexdigest()
        artifacts = artifact_digest(APP, DOCKER, REQ, page, panels, card, forge_payload)
        config = json.dumps({
            "slug": slug, "title": item["title"], "vertical": item["vertical"],
            "product_source": item["source"], "source_repository": DEPLOYMENT_SOURCE_REPOSITORY,
            "source_revision": source_revision, "workflow_run_id": int(workflow_run_id),
            "hf_repository": rid, "artifact_set_sha256": artifacts,
            "landing_sha256": landing_sha256, "panels_sha256": panels_sha256,
            "forge": forge, "upstream": item["upstream"],
            "workflow": list(item["workflow"]),
            "required_evidence_paths": list(required_evidence),
            "public_experience": PUBLIC_EXPERIENCE_VERSION,
        }, indent=2, sort_keys=True) + "\n"
        row: dict[str, Any] = {"id": rid, "slug": slug, "source": item["source"], "source_revision": source_revision, "workflow_run_id": int(workflow_run_id), "artifact_set_sha256": artifacts, "landing_sha256": landing_sha256, "panels_sha256": panels_sha256, "forge": forge, "root_marker": root_marker, "actions": []}
        try:
            row["actions"].append(ensure_space_repository(api, rid))
            for path, payload in (("app.py", APP), ("Dockerfile", DOCKER), ("requirements.txt", REQ), ("config.json", config), ("index.html", page), ("panels.html", panels), ("README.md", card)):
                upload_text(api, rid, path, payload)
            row["actions"].append("publish_source")
            api.restart_space(rid)
            row["actions"].append("restart")
        except Exception as exc:
            row["error"] = f"{type(exc).__name__}: {exc}"
        rows.append(row)
    deadline = time.time() + 900
    pending = {row["id"].split("/", 1)[1] for row in rows if "error" not in row}
    while pending and time.time() < deadline:
        for slug in tuple(pending):
            row = next(value for value in rows if value["id"].endswith("/" + slug))
            observe_flagship(row)
            if observation_passes(row, source_revision=source_revision, workflow_run_id=workflow_run_id):
                pending.remove(slug)
        if pending: time.sleep(15)
    complete = True
    for row in rows:
        observe_flagship(row)
        ok = "error" not in row and observation_passes(row, source_revision=source_revision, workflow_run_id=workflow_run_id)
        row["operational"] = ok
        complete = complete and ok
    receipt = {
        "schema": "szl.hf-vertical-flagships/v4",
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
        "source_repository": DEPLOYMENT_SOURCE_REPOSITORY,
        "source_revision": source_revision,
        "workflow_run_id": int(workflow_run_id),
        "token_source_name": token_source,
        "token_value_recorded": False,
        "public_experience": PUBLIC_EXPERIENCE_VERSION,
        "verticals_total": len(rows),
        "verticals_operational": sum(1 for row in rows if row.get("operational") is True),
        "complete": complete,
        "rows": rows,
    }
    Path("hf-vertical-flagships-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if complete else 1


def main() -> int:
    if not CANONICAL_ENTRYPOINT_ADMITTED:
        raise RuntimeError("direct execution is disabled; use hf_publish_vertical_flagships_v4.py")
    return _publish_main()


__all__ = tuple(sorted(name for name in globals() if not name.startswith("_") and name not in {"Any", "ModuleType", "Path", "dt", "hashlib", "importlib", "json", "os", "time"}))


if __name__ == "__main__":
    raise SystemExit(main())
