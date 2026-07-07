#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings
"""Local verification of the ENERGY MEASURED channel wiring.

Run with fastapi==0.137.2 / starlette==1.3.1. Proves:
  1. /api/a11oy/v1/harvest/posture returns HTTP 200.
  2. With NO meter env set, posture honestly reports joules_label="sample"
     (STRUCTURAL-ONLY), joules_measured False, joules_evidence {}, a clear reason,
     and NO fabricated joule.
  3. The MEASURED code path: measured_channel() parses a real omen snapshot
     (w27 live snapshot if present, else the documented synthetic shape) via an
     injected live reader and WOULD produce joules_label="measured" with evidence
     + provenance. Also asserts monotonic-reset -> STRUCTURAL-ONLY.

Sandbox cannot reach the real meter, so path (3) proves the parser + gate that
WOULD light MEASURED on a live meter delta — never fabricating a joule.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI
from fastapi.testclient import TestClient

import a11oy_harvest_endpoints as ep
import szl_energy_measured as em

FAIL = []


def check(cond, msg):
    print(("  PASS " if cond else "  FAIL ") + msg)
    if not cond:
        FAIL.append(msg)


print("=" * 74)
print("ENERGY MEASURED channel — local TestClient verification")
print("fastapi", __import__("fastapi").__version__, "starlette", __import__("starlette").__version__)
print("=" * 74)

# Ensure no meter env leaks in from the environment for the honest-fallback test.
for k in ("A11OY_JOULE_METER_URLS", "A11OY_JOULE_METER_URL"):
    os.environ.pop(k, None)

# Stub current_harvest_posture so the posture body is deterministic + network-free
# (the free feeds are not the subject of this test; the joules channel is). This keeps
# the run hermetic while exercising the REAL handle_posture() joules wiring.
class _P:
    posture = "idle"; rank = 1; wasted_energy_available = False; soak_hard = False
    measured_any = False; drivers = []; readings = []
    timestamp_utc = "2026-07-07T00:00:00+00:00"
    citation = "test"; doctrine = "test-doctrine"

ep.current_harvest_posture = lambda: _P()

# ---- Build a minimal app and register the harvest endpoints (register() pattern) ----
app = FastAPI()
status = ep.register(app, ns="a11oy")
print("\n[register] ->", status)
client = TestClient(app)

# ---- (1)+(2) posture returns 200 + honest STRUCTURAL-ONLY with no meter env ----
print("\n[1/2] GET /api/a11oy/v1/harvest/posture (no meter env => STRUCTURAL-ONLY):")
resp = client.get("/api/a11oy/v1/harvest/posture")
check(resp.status_code == 200, "posture returns HTTP 200 (got %s)" % resp.status_code)
body = resp.json()
check(body.get("joules_label") == "sample",
      "joules_label == 'sample' off-meter (got %r)" % body.get("joules_label"))
check(body.get("joules_measured") is False,
      "joules_measured is False off-meter (got %r)" % body.get("joules_measured"))
check(body.get("joules_evidence") == {},
      "joules_evidence is {} off-meter (no fabricated joule)")
check(bool(body.get("joules_reason")),
      "carries a machine-readable joules_reason: %r" % str(body.get("joules_reason"))[:80])
prov = body.get("joules_provenance") or {}
check("method" in prov, "carries joules_provenance with a method field")
print("      reason:", str(body.get("joules_reason"))[:90])

# ---- (3) MEASURED code path via measured_channel() parser (injected live reader) ----
print("\n[3] MEASURED code path — measured_channel() parses a real omen snapshot:")

W27 = "/home/user/workspace/w27/meter_live_snapshot.json"
if os.path.exists(W27):
    with open(W27) as f:
        SNAP = json.load(f)
    print("      using w27 live snapshot:", W27)
else:
    SNAP = {
        "engines": [{"engine": "omen", "joules": 6937.669,
                     "gpus": [{"index": 0, "name": "NVIDIA GeForce RTX 4060 Ti",
                               "power_w": 6.17, "joules": 6937.669, "live": True}]}],
        "totals": {"joules": 6937.669},
        "exporter": "omen-joule-exporter (real NVML via nvidia-smi)",
        "ts": 1783435960.4713373,
    }
    print("      using synthetic omen snapshot (documented shape)")

# Inject a live reader whose cumulative counter climbs a hair between the two reads
# (real omen ~6-20 W) so monotonic-reset detection passes and MEASURED lights.
_seq = {"n": 0}
_base = float(SNAP["engines"][0]["joules"])


def _live_reader(url, timeout):
    d = json.loads(json.dumps(SNAP))
    val = round(_base + 0.031 * _seq["n"], 3)
    d["engines"][0]["joules"] = val
    d["engines"][0]["gpus"][0]["joules"] = val
    d.setdefault("totals", {})["joules"] = val
    d["engines"][0]["gpus"][0]["live"] = True
    _seq["n"] += 1
    return d


_orig = em._read_meter_raw
em._read_meter_raw = _live_reader
try:
    ch = em.measured_channel(meter_urls=["https://meter.a-11-oy.com/"])
finally:
    em._read_meter_raw = _orig

check(ch.get("measured") is True, "measured_channel -> measured True on live omen read")
check(ch.get("joules_label") == "measured",
      "joules_label == 'measured' on live read (got %r)" % ch.get("joules_label"))
ev = ch.get("joules_evidence") or {}
check(ev.get("joules_measured_total") is not None,
      "evidence carries a REAL joules_measured_total (%s)" % ev.get("joules_measured_total"))
check(ch.get("provenance", {}).get("engine") == "omen",
      "provenance.engine == 'omen' (got %r)" % ch.get("provenance", {}).get("engine"))
check(ch.get("provenance", {}).get("meter_url") == "https://meter.a-11-oy.com/",
      "provenance.meter_url is the live meter")
check(ch.get("joules_after") is not None and ch.get("joules_before") is not None
      and ch["joules_after"] >= ch["joules_before"],
      "monotonic: joules_after >= joules_before (%.3f >= %.3f)"
      % (ch.get("joules_after") or 0, ch.get("joules_before") or 0))
print("      MEASURED: engine=%s power_w=%s joules=%s meter_ts=%s"
      % (ch["provenance"]["engine"], ch.get("power_w"),
         ch.get("joules_after"), ch["provenance"].get("meter_ts")))

# ---- (3b) monotonic reset (after < before) => honest STRUCTURAL-ONLY ----
print("\n[3b] monotonic-reset detection (after < before => STRUCTURAL-ONLY):")
_rseq = {"n": 0}


def _reset_reader(url, timeout):
    d = json.loads(json.dumps(SNAP))
    val = _base if _rseq["n"] == 0 else 12.5   # counter goes backwards (reboot)
    d["engines"][0]["joules"] = val
    d["engines"][0]["gpus"][0]["joules"] = val
    d.setdefault("totals", {})["joules"] = val
    d["engines"][0]["gpus"][0]["live"] = True
    _rseq["n"] += 1
    return d


em._read_meter_raw = _reset_reader
try:
    chr_ = em.measured_channel(meter_urls=["https://meter.a-11-oy.com/"])
finally:
    em._read_meter_raw = _orig
check(chr_.get("measured") is False, "reset -> measured False")
check("meter_reset_detected" in (chr_.get("reason") or ""),
      "reset flagged meter_reset_detected (no delta logged)")
check(chr_.get("joules_evidence") == {}, "reset carries NO fabricated evidence")

# ---- (3c) posture endpoint WOULD light MEASURED when the channel is measured ----
print("\n[3c] /harvest/posture WOULD emit MEASURED when the channel reads live:")
_orig_channel = ep._energy_measured_channel
em._read_meter_raw = _live_reader
_seq["n"] = 0
ep._energy_measured_channel = lambda now=None, meter_urls=None, timeout=None: em.measured_channel(
    meter_urls=["https://meter.a-11-oy.com/"])
try:
    resp2 = client.get("/api/a11oy/v1/harvest/posture")
finally:
    ep._energy_measured_channel = _orig_channel
    em._read_meter_raw = _orig
check(resp2.status_code == 200, "posture still 200 on measured path")
b2 = resp2.json()
check(b2.get("joules_label") == "measured",
      "posture joules_label == 'measured' on live channel (got %r)" % b2.get("joules_label"))
check(b2.get("joules_measured") is True, "posture joules_measured True on live channel")
check((b2.get("joules_evidence") or {}).get("joules_measured_total") is not None,
      "posture carries real joules_evidence.joules_measured_total")
check((b2.get("joules_provenance") or {}).get("engine") == "omen",
      "posture joules_provenance.engine == 'omen'")
print("      posture MEASURED: label=%s J=%s engine=%s"
      % (b2.get("joules_label"),
         (b2.get("joules_evidence") or {}).get("joules_measured_total"),
         (b2.get("joules_provenance") or {}).get("engine")))

print("\n" + "=" * 74)
if FAIL:
    print("RESULT: FAIL (%d checks failed)" % len(FAIL))
    for m in FAIL:
        print("  - " + m)
    sys.exit(1)
print("RESULT: ALL CHECKS PASSED")
sys.exit(0)
