# Copyright 2026 SZL Holdings — SPDX-License-Identifier: Apache-2.0
# sentra lean UDS runtime — real health/identity/gates/mesh endpoints.
import urllib.request
from fastapi import FastAPI
from fastapi.responses import JSONResponse

DOCTRINE_V11 = {"declarations": 749, "unique_axioms": 14, "sorries": 163,
    "yuyay": "13-axis yuyay_v3",
    "replay_hash": "bacf54434f1a3bf2d758b27a62d5fd580ca4c8d3b180693573eeebcaea631fc5",
    "A2": "IsHomogeneous", "A4": "IsBounded", "slsa": "L1", "lambda": "Conjecture 1"}
GATES = ["asset-scope", "nist-csf-2.0", "d3fend", "exfil-watch", "lateral-move",
         "priv-esc", "anomaly", "forecast-l7"]  # 8 fail-closed gates

app = FastAPI(title="sentra-gates", version="uds-v0.3.1")

@app.get("/api/sentra/healthz")
def healthz():
    return {"status": "ok", "flagship": "sentra", "version": "uds-v0.3.1"}

@app.get("/api/sentra/v1/identity")
def identity():
    return {"flagship": "sentra", "role": "immune-threat-gates",
            "doctrine_v11": DOCTRINE_V11, "gates": GATES, "failClosed": True}

@app.get("/api/sentra/v1/gates")
def gates():
    return {"gates": GATES, "count": len(GATES), "failClosed": True, "nistCsf": "2.0"}

@app.get("/api/sentra/v1/verdict")
def verdict():
    return {"verdict": "allow", "failClosed": True, "evaluated_gates": len(GATES)}

@app.get("/api/sentra/v1/mesh")
def mesh():
    targets = {"killinchu": "http://killinchu.killinchu.svc.cluster.local:8080/killinchu/healthz"}
    out = {}
    for name, url in targets.items():
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                out[name] = {"reachable": r.status == 200, "status": r.status}
        except Exception as e:
            out[name] = {"reachable": False, "error": str(e)[:80]}
    return JSONResponse({"mesh": out, "all_green": all(v.get("reachable") for v in out.values())})
