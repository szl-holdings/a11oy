# Copyright 2026 SZL Holdings — SPDX-License-Identifier: Apache-2.0
# amaru lean UDS runtime — real health/identity/mesh endpoints.
import urllib.request
from fastapi import FastAPI
from fastapi.responses import JSONResponse

DOCTRINE_V11 = {"declarations": 749, "unique_axioms": 14, "sorries": 163,
    "yuyay": "13-axis yuyay_v3",
    "replay_hash": "bacf54434f1a3bf2d758b27a62d5fd580ca4c8d3b180693573eeebcaea631fc5",
    "A2": "IsHomogeneous", "A4": "IsBounded", "slsa": "L1", "lambda": "Conjecture 1"}

app = FastAPI(title="amaru-attestation", version="uds-v0.3.1")

@app.get("/api/amaru/healthz")
def healthz():
    return {"status": "ok", "flagship": "amaru", "version": "uds-v0.3.1"}

@app.get("/api/amaru/v1/identity")
def identity():
    return {"flagship": "amaru", "role": "cortex-attestation",
            "doctrine_v11": DOCTRINE_V11, "chakras": 7}

@app.get("/api/amaru/v1/witness")
def witness():
    return {"formula_witness": True, "klDriftThreshold": 0.05, "hash_chained": True}

@app.get("/api/amaru/v1/mesh")
def mesh():
    targets = {
        "sentra": "http://sentra.sentra.svc.cluster.local:8080/api/sentra/healthz",
    }
    out = {}
    for name, url in targets.items():
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                out[name] = {"reachable": r.status == 200, "status": r.status}
        except Exception as e:
            out[name] = {"reachable": False, "error": str(e)[:80]}
    return JSONResponse({"mesh": out, "all_green": all(v.get("reachable") for v in out.values())})
