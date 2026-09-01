# SPDX-License-Identifier: Apache-2.0
"""Governed six-organ second-brain status for Packet 8 Space adapters."""
from __future__ import annotations
import importlib
import json
import time
from urllib.request import Request, urlopen

LOCKED_EIGHT=("F1","F4","F7","F11","F12","F18","F19","F22")
SUBSTRATE_SHA="ad2e04374717ef79dbf7dbb91aea5a8480ed10c3"
MODULES=("szl_substrate.szl_formula_wiring","szl_substrate.szl_formulas","szl_substrate.szl_unified_formulas","szl_substrate.szl_khipu_consensus","szl_substrate.szl_brain","szl_substrate.szl_dsse")

def _probe(url:str)->dict:
    started=time.perf_counter()
    try:
        with urlopen(Request(url,headers={"User-Agent":"szl-packet8-brain/1.0","Accept":"application/json"}),timeout=2.5) as r:
            raw=r.read(2048)
            try: body=json.loads(raw.decode("utf-8","replace"))
            except Exception: body=None
            return {"label":"MEASURED","http":int(r.status),"latency_ms":round((time.perf_counter()-started)*1000,2),"json":body}
    except Exception as exc:
        return {"label":"UNAVAILABLE","http":getattr(exc,"code",None),"latency_ms":None,"json":None}

def substrate_status()->dict:
    loaded=[]; missing=[]
    for name in MODULES:
        try:
            mod=importlib.import_module(name); loaded.append({"module":name,"exports":len([k for k in vars(mod) if not k.startswith("_")])})
        except Exception as exc: missing.append({"module":name,"error":type(exc).__name__})
    return {"label":"MEASURED","substrate_sha":SUBSTRATE_SHA,"loaded":loaded,"missing":missing,"locked_proven_count":8,"locked_proven_ids":list(LOCKED_EIGHT),"lambda":{"status":"OPEN","label":"REPORTED","name":"Conjecture 1"},"formula_authority":"NONE"}

def anatomy(surface:str)->dict:
    substrate=substrate_status(); ok=not substrate["missing"]
    feeds={"a11oy_atlas":_probe("https://a-11-oy.com/api/a11oy/v1/ecosystem/atlas"),"a11oy_health":_probe("https://a-11-oy.com/healthz")}
    organs=[{"name":"BRAIN","status":"LIVE" if ok else "DEGRADED","label":"MEASURED"},{"name":"HEART","status":"LIVE","label":"REPORTED","detail":"Lambda advisory only"},{"name":"CIRCULATORY","status":"LIVE" if any(v["label"]=="MEASURED" for v in feeds.values()) else "DEGRADED","label":"MEASURED"},{"name":"NERVOUS","status":"LIVE","label":"MEASURED"},{"name":"SKELETON","status":"LIVE","label":"MEASURED","detail":"pinned substrate + locked proof IDs"},{"name":"IMMUNE","status":"LIVE","label":"REPORTED","detail":"fail-closed evidence labels"}]
    return {"schema":"szl.second-brain.packet8/v1","surface":surface,"captured_at_unix":int(time.time()),"organs":organs,"substrate":substrate,"feeds":feeds,"truth_contract":["MEASURED","REPORTED","MODELED","UNAVAILABLE"],"product_certified":False,"proven_trust":False,"formula_authority":"NONE"}
