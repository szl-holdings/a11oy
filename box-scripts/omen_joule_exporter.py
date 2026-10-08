#!/usr/bin/env python3
"""
omen-joule-exporter — REAL NVML power/joule meter for the OMEN GPU.

Serves the exact JSON the a11oy energy-operator expects from its joule meter
(_JOULE_METER_URL), so OMEN's compute is metered as MEASURED (not SAMPLE):

  {
    "engines": [
      {"engine": "omen", "joules": <cumulative_J>,
       "gpus": [{"index": 0, "name": "...", "power_w": <W>, "joules": <J>,
                 "live": true}]}
    ],
    "totals": {"joules": <cumulative_J>}
  }

HONESTY (doctrine — never fabricate a joule):
  * power_w is read from the REAL GPU via `nvidia-smi --query-gpu=power.draw`.
  * joules is the time-integral of that real power (W x seconds), accumulated by
    a background sampler at a fixed cadence. No GPU reading => the GPU is marked
    "live": false, power_w/joules omitted (null) for that sample, and the
    operator will correctly keep that node's energy as SAMPLE, never MEASURED.
    This is integrated GPU board power, not an NVML total-energy counter delta,
    and cannot establish energy attributable to an individual inference or job.
  * The engine name defaults to "omen" to match A11OY_OMEN_GPU_LABEL. Override
    with OMEN_ENGINE_NAME if you change that label.

RUN (after separately provisioning request keys): python box-scripts/omen_joule_exporter.py
The default bind is 127.0.0.1:9471. Every telemetry read, including loopback and
reverse-proxy traffic, needs the per-client HMAC protocol in szl_meter_access.py.
An allowed source IP is an additional restriction, never client authentication.
Missing/invalid authentication configuration prevents startup, before GPU reads.
Install szl_meter_access.py beside a standalone copy of this exporter, or use the
canonical repository layout. No tunnel, key provisioning, or service activation is
performed here. See box-scripts/METER_REQUEST_AUTH.md for the installation contract.

MULTI-NODE AGGREGATION (real fix, not a bandaid):
  Set PEER_EXPORTERS to a comma-separated list of OTHER nodes' exporter URLs
  (e.g. the laptop's tailnet exporter). This node then serves its OWN NVML engine
  PLUS every reachable peer's engines merged into one `engines[]` list, so a single
  scrape of THIS exporter (the one behind meter.a-11-oy.com) returns every GPU in the
  mesh. Honest by design: an unreachable peer simply does not appear (never faked);
  a peer engine whose name duplicates a local engine is dropped (local wins).
    PEER_EXPORTERS must have exact-origin client keys in SZL_METER_HMAC_TARGETS;
    non-loopback peer URLs require HTTPS. Redirects never carry a meter capability.

Pure stdlib — no pip installs. Requires nvidia-smi on PATH (ships with the driver).
"""
import ipaddress
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

try:
    from szl_meter_access import MeterAuthConfigurationError, MeterRequestVerifier, open_meter_get
except ModuleNotFoundError as error:
    if error.name != "szl_meter_access":
        raise
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from szl_meter_access import MeterAuthConfigurationError, MeterRequestVerifier, open_meter_get

PORT = int(os.environ.get("OMEN_EXPORTER_PORT", "9471"))
BIND = os.environ.get("OMEN_EXPORTER_BIND", "127.0.0.1")
ENGINE_NAME = os.environ.get("OMEN_ENGINE_NAME", "omen")
SAMPLE_EVERY_S = float(os.environ.get("OMEN_SAMPLE_EVERY_S", "2.0"))
# Comma-separated peer exporter URLs to merge (empty = single-node behaviour, unchanged).
PEER_EXPORTERS = [u.strip() for u in os.environ.get("PEER_EXPORTERS", "").split(",") if u.strip()]
PEER_TIMEOUT_S = float(os.environ.get("PEER_TIMEOUT_S", "3.0"))
# The local tunnel uses loopback; an intended tower peer may scrape over Tailscale.
_ALLOWED_CLIENT_NETWORKS = tuple(ipaddress.ip_network(value) for value in (
    "127.0.0.0/8", "::1/128", "100.64.0.0/10", "fd7a:115c:a1e0::/48"
))

# Per-inference model energy reading written by ollama_energy_probe.py. Merged into the
# meter payload as a top-level models[] entry so the a11oy energy surface can show the
# GLM node's MEASURED joules/token. Purely additive — engines/totals are unchanged.
OLLAMA_ENERGY_JSON = os.environ.get(
    "OLLAMA_ENERGY_JSON",
    os.path.join(os.path.expanduser("~"), ".a11oy_ollama_energy.json"),
)
# A reading older than this (seconds) is stale => emitted as UNAVAILABLE, null number.
OLLAMA_ENERGY_MAX_AGE_S = float(os.environ.get("OLLAMA_ENERGY_MAX_AGE_S", "300"))

# Cumulative joules per GPU index, integrated from real power samples.
_state_lock = threading.Lock()
_cum_joules = {}          # gpu_index -> cumulative joules (float)
_last_sample = {}         # gpu_index -> {"power_w": float|None, "name": str, "live": bool, "ts": float}


def _read_gpu_power():
    """Return list of (index, name, power_w_or_None) from nvidia-smi. [] on failure."""
    try:
        out = subprocess.run(
            ["nvidia-smi",
             "--query-gpu=index,name,power.draw",
             "--format=csv,noheader,nounits"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=8, check=False,
        )
        if out.returncode != 0 or not out.stdout:
            return []
        rows = []
        for line in out.stdout.decode("utf-8", "replace").splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 3:
                continue
            try:
                idx = int(parts[0])
            except ValueError:
                continue
            name = parts[1]
            try:
                power_w = float(parts[2])
            except ValueError:
                power_w = None  # power unreadable => honest null, not zero
            rows.append((idx, name, power_w))
        return rows
    except (OSError, subprocess.SubprocessError):
        return []


def _sampler():
    """Background loop: integrate real power into cumulative joules."""
    prev_ts = time.time()
    while True:
        time.sleep(SAMPLE_EVERY_S)
        now = time.time()
        dt = now - prev_ts
        prev_ts = now
        rows = _read_gpu_power()
        with _state_lock:
            for idx, name, power_w in rows:
                if power_w is not None and dt > 0:
                    _cum_joules[idx] = _cum_joules.get(idx, 0.0) + power_w * dt
                _last_sample[idx] = {
                    "power_w": power_w,
                    "name": name,
                    "live": power_w is not None,
                    "ts": now,
                }


def _local_engine():
    """This node's own NVML engine dict (+ its cumulative joules total)."""
    with _state_lock:
        gpus = []
        total = 0.0
        for idx in sorted(_last_sample.keys()):
            s = _last_sample[idx]
            j = _cum_joules.get(idx, 0.0)
            total += j
            gpus.append({
                "index": idx,
                "name": s.get("name"),
                "power_w": s.get("power_w"),
                "joules": round(j, 3),
                "live": bool(s.get("live")),
            })
    return {"engine": ENGINE_NAME, "joules": round(total, 3), "gpus": gpus}, total


def _fetch_peer_engines():
    """Fetch each PEER_EXPORTER's engines[]. Unreachable peers are skipped (honest —
    never fabricated). Returns (engines_list, joules_sum) for all reachable peers."""
    engines, jsum = [], 0.0
    for url in PEER_EXPORTERS:
        try:
            with open_meter_get(url, timeout=PEER_TIMEOUT_S,
                                headers={"User-Agent": "omen-joule-exporter/peer"}) as r:
                body = r.read(65537)
                if len(body) > 65536:
                    continue
                data = json.loads(body.decode("utf-8", "replace"))
            for e in (data.get("engines") or []):
                if not isinstance(e, dict) or not e.get("engine"):
                    continue
                engines.append(e)
                if isinstance(e.get("joules"), (int, float)):
                    jsum += float(e["joules"])
        except Exception:
            # Peer down/unreachable => omit it. Never fake a joule. (Doctrine v11)
            continue
    return engines, jsum


def _read_models():
    """Read the ollama_energy_probe.py reading (OLLAMA_ENERGY_JSON) and return a
    top-level models[] list for the meter payload. Honest by construction:
      * file missing / unreadable / unparseable  => [] (no model surfaced, never faked)
      * reading older than OLLAMA_ENERGY_MAX_AGE_S => model surfaced with label
        UNAVAILABLE and joules_per_token=null (stale=true), never a stale number
      * fresh reading whose own label is UNAVAILABLE (NVML couldn't read on the box)
        => surfaced verbatim as UNAVAILABLE with null number
      * fresh MEASURED / MEASURED_SHARED_BOUNDED => number surfaced with its verbatim
        label and source (labels are NEVER upgraded here).
    """
    path = OLLAMA_ENERGY_JSON
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return []  # no probe reading on this box => surface no model (honest)
    try:
        with open(path, "r", encoding="utf-8") as f:
            r = json.load(f)
    except (OSError, ValueError):
        return []  # unreadable/corrupt => never fabricate

    name = r.get("model")
    if not name:
        return []
    age = time.time() - mtime
    stale = age > OLLAMA_ENERGY_MAX_AGE_S
    label = r.get("label") or "UNAVAILABLE"
    if stale or label == "UNAVAILABLE":
        # Stale or the probe itself couldn't measure => no number, honest UNAVAILABLE.
        return [{
            "name": name,
            "joules_per_token": None,
            "energy_joules": None,
            "label": "UNAVAILABLE",
            "source": r.get("source"),
            "ts": r.get("ts"),
            "stale": bool(stale),
        }]
    return [{
        "name": name,
        "joules_per_token": r.get("joules_per_token"),
        "energy_joules": r.get("energy_joules"),
        "energy_joules_idle_subtracted": r.get("energy_joules_idle_subtracted"),
        "output_tokens": r.get("output_tokens"),
        "avg_watts": r.get("avg_watts"),
        "idle_watts": r.get("idle_watts"),
        "duration_s": r.get("duration_s"),
        "measurement_method": r.get("measurement_method"),
        "exclusive": r.get("exclusive"),
        "gpu_index": r.get("gpu_index"),
        "gpu_name": r.get("gpu_name"),
        "label": label,           # verbatim — never upgraded
        "source": r.get("source"),
        "ts": r.get("ts"),
        "stale": False,
    }]


def _meter_json():
    local, local_total = _local_engine()
    engines = [local]
    total = local_total
    seen = {str(local["engine"]).lower()}
    if PEER_EXPORTERS:
        peer_engines, _ = _fetch_peer_engines()
        for e in peer_engines:
            name = str(e.get("engine")).lower()
            if name in seen:
                continue  # local wins on name collision; never double-count
            seen.add(name)
            engines.append(e)
            if isinstance(e.get("joules"), (int, float)):
                total += float(e["joules"])
    payload = {
        "engines": engines,
        "totals": {"joules": round(total, 3)},
        "exporter": "omen-joule-exporter (real NVML via nvidia-smi)"
                    + (" + %d peer(s)" % len(PEER_EXPORTERS) if PEER_EXPORTERS else ""),
        "ts": time.time(),
    }
    # Additive: per-inference model energy from ollama_energy_probe.py, if present.
    # Absent => key omitted entirely (engines/totals stay byte-compatible).
    models = _read_models()
    if models:
        payload["models"] = models
    return payload


def _client_allowed(remote):
    try:
        address = ipaddress.ip_address(remote)
    except ValueError:
        return False
    return any(address in network for network in _ALLOWED_CLIENT_NETWORKS)


class Handler(BaseHTTPRequestHandler):
    server_version = "omen-joule-exporter/1.1"

    def setup(self):
        super().setup()
        self.connection.settimeout(3.0)

    def _deny(self):
        self.close_connection = True
        self.send_response(403)
        self.send_header("Content-Length", "0")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()

    def do_GET(self):
        verifier = getattr(self.server, "meter_verifier", None)
        # No forwarded headers or reverse-proxy source IP can authorize a read.
        singleton = ("Host", "Content-Length", "Content-Type", "Content-Encoding",
                     "Transfer-Encoding", "Connection", "Expect", "Origin")
        if (not _client_allowed(self.client_address[0]) or verifier is None
                or any(len(self.headers.get_all(name, [])) > 1 for name in singleton)
                or len(self.headers.get_all("Host", [])) != 1
                or self.headers.get("Transfer-Encoding") is not None
                or self.headers.get("Expect") is not None
                or self.headers.get("Content-Length") not in (None, "0")
                or len(self.headers) > 32
                or sum(len(k) + len(v) for k, v in self.headers.items()) > 8192
                or not verifier.accepts("GET", self.path, self.headers)):
            self._deny()
            return
        payload = json.dumps(_meter_json(), allow_nan=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(payload)
        except BrokenPipeError:
            pass

    def log_message(self, *a):  # quiet
        pass


def main():
    # Configuration validation precedes every listener, sampler and GPU read.
    try:
        verifier = MeterRequestVerifier.from_environment()
        if not _client_allowed(BIND):
            raise MeterAuthConfigurationError("invalid exporter bind address")
    except MeterAuthConfigurationError:
        print("omen-joule-exporter BLOCKED: request authentication or bind configuration invalid")
        return 1
    threading.Thread(target=_sampler, daemon=True).start()
    # Warm one immediate sample so the first scrape isn't empty.
    rows = _read_gpu_power()
    with _state_lock:
        for idx, name, power_w in rows:
            _last_sample[idx] = {"power_w": power_w, "name": name,
                                 "live": power_w is not None, "ts": time.time()}
    httpd = ThreadingHTTPServer((BIND, PORT), Handler)
    httpd.meter_verifier = verifier
    print("omen-joule-exporter serving authenticated reads on %s:%d" % (BIND, PORT))
    httpd.serve_forever()


if __name__ == "__main__":
    raise SystemExit(main())
