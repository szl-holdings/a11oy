# Copyright 2026 SZL Holdings
# SPDX-License-Identifier: Apache-2.0
#
# a11oy lean UDS runtime — serves canonical health/identity/mesh-reachability
# endpoints so the a11oy->amaru->sentra->killinchu->rosie Istio smoke test is REAL.
# ADDITIVE: mirrors the live HF Space contract; does not replace it.
import os, json, urllib.request
from fastapi import FastAPI
from fastapi.responses import JSONResponse

# Doctrine v11 LOCKED — preserved verbatim.
DOCTRINE_V11 = {
    "declarations": 749,
    "unique_axioms": 14,
    "sorries": 163,
    "yuyay": "13-axis yuyay_v3",
    "replay_hash": "bacf54434f1a3bf2d758b27a62d5fd580ca4c8d3b180693573eeebcaea631fc5",
    "A2": "IsHomogeneous",
    "A4": "IsBounded",
    "slsa": "L1",
    "lambda": "Conjecture 1",
}
ANCHOR_GATES = ["LiuHuiPi", "MadhavaBound", "FalsePosition",
                "SummationInvariant", "AdversarialRobustness"]

app = FastAPI(title="a11oy-runtime", version="uds-v0.3.1")

@app.get("/api/a11oy/healthz")
def healthz():
    return {"status": "ok", "flagship": "a11oy", "version": "uds-v0.3.1"}

@app.get("/api/a11oy/v1/identity")
def identity():
    return {"flagship": "a11oy", "role": "orchestration-kernel",
            "doctrine_v11": DOCTRINE_V11, "anchor_gates": ANCHOR_GATES}

@app.get("/api/a11oy/v1/gates")
def gates():
    return {"gates": ANCHOR_GATES, "strictMode": True, "failClosed": True}

@app.get("/api/a11oy/v1/reason")
def reason():
    return {"router": "puriq-open-llm", "backends": ["llama", "qwen"], "ready": True}

@app.get("/api/a11oy/v1/mesh")
def mesh():
    """Reachability probe across the SZL mesh (real HTTP calls inside cluster)."""
    targets = {
        "amaru": "http://amaru.amaru.svc.cluster.local:8080/api/amaru/healthz",
        "sentra": "http://sentra.sentra.svc.cluster.local:8080/api/sentra/healthz",
        "killinchu": "http://killinchu.killinchu.svc.cluster.local:8080/killinchu/healthz",
        "rosie": "http://rosie.rosie.svc.cluster.local:8080/api/rosie/healthz",
    }
    out = {}
    for name, url in targets.items():
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                out[name] = {"reachable": r.status == 200, "status": r.status}
        except Exception as e:
            out[name] = {"reachable": False, "error": str(e)[:80]}
    green = all(v.get("reachable") for v in out.values())
    return JSONResponse({"mesh": out, "all_green": green})
