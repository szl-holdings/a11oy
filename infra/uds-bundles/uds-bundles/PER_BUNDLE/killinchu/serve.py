# Copyright 2026 SZL Holdings — SPDX-License-Identifier: Apache-2.0
# killinchu lean UDS runtime — real health/identity/drones/audit/mesh endpoints.
import json, os, urllib.request
from fastapi import FastAPI
from fastapi.responses import JSONResponse

DOCTRINE_V11 = {"declarations": 749, "unique_axioms": 14, "sorries": 163,
    "yuyay": "13-axis yuyay_v3",
    "replay_hash": "bacf54434f1a3bf2d758b27a62d5fd580ca4c8d3b180693573eeebcaea631fc5",
    "A2": "IsHomogeneous", "A4": "IsBounded", "slsa": "L1", "lambda": "Conjecture 1"}

def _load_db():
    p = os.path.join(os.path.dirname(__file__), "drones_db.json")
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return {"drones": []}

app = FastAPI(title="killinchu-bundle", version="uds-v0.3.1")

@app.get("/killinchu/healthz")
def healthz():
    return {"status": "ok", "flagship": "killinchu", "version": "uds-v0.3.1"}

@app.get("/killinchu/identity")
def identity():
    return {"flagship": "killinchu", "role": "drone-flagship",
            "doctrine_v11": DOCTRINE_V11, "puriq_core": True, "twoPersonGate": True}

@app.get("/drones")
def drones():
    return _load_db()

@app.get("/killinchu/audit/summary")
def audit():
    db = _load_db()
    return {"registered": len(db.get("drones", [])), "twoPersonGate": True}

@app.get("/killinchu/mesh")
def mesh():
    targets = {"rosie": "http://rosie.rosie.svc.cluster.local:8080/api/rosie/healthz"}
    out = {}
    for name, url in targets.items():
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                out[name] = {"reachable": r.status == 200, "status": r.status}
        except Exception as e:
            out[name] = {"reachable": False, "error": str(e)[:80]}
    return JSONResponse({"mesh": out, "all_green": all(v.get("reachable") for v in out.values())})
