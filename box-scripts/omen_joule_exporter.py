#!/usr/bin/env python3
"""
omen-joule-exporter — observed GPU power and optional NVML energy-counter meter.

Serves observed GPU power, a MODELED sampled-power integral, and MEASURED joules
only when two fresh monotone NVML total-energy counter readings are available:

  {
    "engines": [
      {"engine": "omen", "joules": <measured_J_or_null>, "estimated_joules": <modeled_J>,
       "gpus": [{"index": 0, "name": "...", "power_w": <observed_W>,
                  "joules": <measured_J_or_null>, "joules_method": "NVML_COUNTER_DELTA",
                  "estimated_joules": <modeled_J>,
                  "sample_ts": <actual_sample_epoch_s>, "live": true}]}
    ],
    "totals": {"joules": <measured_J_or_null>, "estimated_joules": <modeled_J>}
  }

HONESTY (doctrine — never fabricate a joule):
  * power_w and GPU UUID are read from `nvidia-smi`; a measured counter delta
    requires the same UUID from NVML on both polls.
  * joules is accumulated only from real NVML total-energy counter deltas (mJ),
    when available. An unsupported API, failed poll, detected counter decrease,
    missing GPU, or stale sample emits null measured joules; zero deltas stay zero.
    NVML does not attest driver continuity: a reset hidden by an overtaking new
    counter between polls cannot be ruled out from this API alone.
  * estimated_joules is sampled power x time, always labeled MODELED. Missing or
    stale GPU samples emit null power/joules/estimate; cumulative history is kept
    internally, with gaps excluded.
  * The engine name defaults to "omen" to match A11OY_OMEN_GPU_LABEL. Override
    with OMEN_ENGINE_NAME if you change that label.

RUN (on OMEN):  python omen_joule_exporter.py     # serves on 0.0.0.0:9471
Then tunnel port 9471 and point A11OY_JOULE_METER_URL at the tunnel /.
Only loopback and Tailscale-range peers may read this listener. This source-IP
filter does not authenticate Tailscale peers or public tunnel clients; a public
tunnel needs its own access policy.

MULTI-NODE AGGREGATION (real fix, not a bandaid):
  Set PEER_EXPORTERS to a comma-separated list of OTHER nodes' exporter URLs
  (e.g. the laptop's tailnet exporter). This node then serves its OWN NVML engine
  PLUS every reachable peer's engines merged into one `engines[]` list, so a single
  scrape of THIS exporter (the one behind meter.a-11-oy.com) returns every GPU in the
  mesh. Honest by design: an unreachable peer simply does not appear (never faked);
  a peer engine whose name duplicates a local engine is dropped (local wins).
    export PEER_EXPORTERS=http://100.x.y.z:9471/     # laptop 'betterwithage' over tailnet

Requires nvidia-smi on PATH for observed power. Optional nvidia-ml-py (`pynvml`)
and hardware total-energy-counter support are required for MEASURED joules.
"""
import ipaddress
import json
import math
import os
import subprocess
import threading
import time
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("OMEN_EXPORTER_PORT", "9471"))
ENGINE_NAME = os.environ.get("OMEN_ENGINE_NAME", "omen")
SAMPLE_EVERY_S = float(os.environ.get("OMEN_SAMPLE_EVERY_S", "2.0"))
# Two normal intervals plus the nvidia-smi 8s deadline; cap configured cadences
# so a stopped sampler cannot keep a reading live indefinitely.
MAX_SAMPLE_AGE_S = min(30.0, max(10.0, 2 * SAMPLE_EVERY_S + 8.0))
# Comma-separated peer exporter URLs to merge (empty = single-node behaviour, unchanged).
PEER_EXPORTERS = [u.strip() for u in os.environ.get("PEER_EXPORTERS", "").split(",") if u.strip()]
PEER_TIMEOUT_S = float(os.environ.get("PEER_TIMEOUT_S", "3.0"))
# The local tunnel uses loopback; an intended tower peer may scrape over Tailscale.
_ALLOWED_CLIENT_NETWORKS = tuple(ipaddress.ip_network(value) for value in (
    "127.0.0.0/8", "::1/128", "100.64.0.0/10", "fd7a:115c:a1e0::/48"
))


# External per-inference model-energy file. Its producer/harness is not source-bound
# in this repository, so models[] is normalized to UNKNOWN/null below.
OLLAMA_ENERGY_JSON = os.environ.get(
    "OLLAMA_ENERGY_JSON",
    os.path.join(os.path.expanduser("~"), ".a11oy_ollama_energy.json"),
)
# A reading older than this (seconds) is stale => emitted as UNAVAILABLE, null number.
OLLAMA_ENERGY_MAX_AGE_S = float(os.environ.get("OLLAMA_ENERGY_MAX_AGE_S", "300"))

# Cumulative joules per GPU index, integrated from real power samples.
_state_lock = threading.Lock()
_cum_joules = {}          # gpu_index -> MODELED sampled-power integral
_cum_counter_joules = {}  # gpu_index -> observed NVML counter deltas only
_last_sample = {}         # gpu_index -> last actual poll, counter and validity


def _finite_nonnegative(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) and number >= 0 else None


def _fresh_observation(sample_ts, now):
    observed = _finite_nonnegative(sample_ts)
    return observed is not None and 0 <= now - observed <= MAX_SAMPLE_AGE_S


def _read_gpu_power():
    """Return (index, uuid, name, power_w) rows from nvidia-smi. [] on failure."""
    try:
        out = subprocess.run(
            ["nvidia-smi",
             "--query-gpu=index,uuid,name,power.draw",
             "--format=csv,noheader,nounits"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=8, check=False,
        )
        if out.returncode != 0 or not out.stdout:
            return []
        rows = []
        for line in out.stdout.decode("utf-8", "replace").splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 4:
                continue
            try:
                idx = int(parts[0])
            except ValueError:
                continue
            gpu_uuid = parts[1]
            name = parts[2]
            try:
                power_w = _finite_nonnegative(float(parts[3]))
            except ValueError:
                power_w = None  # power unreadable => honest null, not zero
            rows.append((idx, gpu_uuid, name, power_w))
        return rows
    except (OSError, subprocess.SubprocessError):
        return []


def _read_gpu_energy_counters():
    """GPU-index -> {uuid, mj} from NVML; {} if the API is unavailable."""
    try:
        import pynvml
    except ImportError:
        return {}
    try:
        pynvml.nvmlInit()
    except Exception:
        return {}
    counters = {}
    try:
        for idx in range(pynvml.nvmlDeviceGetCount()):
            try:
                handle = pynvml.nvmlDeviceGetHandleByIndex(idx)
                value = _finite_nonnegative(pynvml.nvmlDeviceGetTotalEnergyConsumption(handle))
                uuid = pynvml.nvmlDeviceGetUUID(handle)
                if isinstance(uuid, bytes):
                    uuid = uuid.decode("ascii", "replace")
                if value is not None and isinstance(uuid, str) and uuid:
                    counters[idx] = {"mj": value, "uuid": uuid, "ts": time.time()}
            except Exception:
                continue  # NVML_ERROR_NOT_SUPPORTED is not a measurement.
    except Exception:
        pass
    finally:
        try:
            pynvml.nvmlShutdown()
        except Exception:
            pass
    return counters


def _record_sample(rows, *, now, dt, counters_mj=None):
    """Record one poll; absent GPUs fail closed and gaps are not extrapolated."""
    seen = set()
    counters_mj = counters_mj or {}
    with _state_lock:
        for idx, smi_uuid, name, raw_power in rows:
            seen.add(idx)
            power_w = _finite_nonnegative(raw_power)
            previous = _last_sample.get(idx)
            prior_power = _finite_nonnegative(previous.get("power_w")) if previous else None
            counter_reading = counters_mj.get(idx) or {}
            counter_mj = _finite_nonnegative(counter_reading.get("mj"))
            counter_uuid = counter_reading.get("uuid")
            counter_ts = _finite_nonnegative(counter_reading.get("ts"))
            if (not isinstance(counter_uuid, str) or not counter_uuid
                    or not isinstance(smi_uuid, str) or smi_uuid != counter_uuid):
                counter_mj = None
                counter_uuid = None
            if not _fresh_observation(counter_ts, now):
                counter_mj = None
            prior_counter = (_finite_nonnegative(previous.get("counter_mj"))
                             if previous else None)
            prior_uuid = previous.get("counter_uuid") if previous else None
            continuous = (previous is not None and previous.get("live") is True
                          and _fresh_observation(previous.get("ts"), now)
                          and 0 < dt <= MAX_SAMPLE_AGE_S)
            if (power_w is not None and prior_power is not None
                    and continuous):
                prior_joules = _finite_nonnegative(_cum_joules.get(idx, 0.0))
                integrated = _finite_nonnegative((prior_joules or 0.0) + power_w * dt)
                if integrated is not None:
                    _cum_joules[idx] = integrated
            elif power_w is not None:
                _cum_joules.setdefault(idx, 0.0)
            valid_delta = (power_w is not None and continuous
                           and counter_mj is not None and prior_counter is not None
                           and isinstance(smi_uuid, str) and bool(smi_uuid)
                           and smi_uuid == counter_uuid
                           and counter_uuid == prior_uuid
                           and counter_mj >= prior_counter)
            counter_epoch = (previous.get("counter_epoch") if valid_delta else uuid.uuid4().hex)
            if valid_delta:
                prior_joules = _finite_nonnegative(_cum_counter_joules.get(idx, 0.0))
                observed = _finite_nonnegative(
                    (prior_joules if prior_joules is not None else 0.0)
                    + (counter_mj - prior_counter) / 1000.0
                )
                valid_delta = observed is not None
                if valid_delta:
                    _cum_counter_joules[idx] = observed
            if not valid_delta:
                _cum_counter_joules[idx] = 0.0
                if previous and counter_epoch == previous.get("counter_epoch"):
                    counter_epoch = uuid.uuid4().hex
            _last_sample[idx] = {
                "power_w": power_w,
                "name": name,
                "live": power_w is not None,
                "ts": counter_ts if counter_mj is not None else now,
                "smi_uuid": smi_uuid,
                "counter_mj": counter_mj,
                "counter_uuid": counter_uuid,
                "counter_epoch": counter_epoch,
                "counter_delta_valid": valid_delta,
            }
        for idx in _last_sample.keys() - seen:
            _last_sample[idx]["live"] = False
            _last_sample[idx]["power_w"] = None
            _last_sample[idx]["counter_mj"] = None
            _last_sample[idx]["counter_uuid"] = None
            _last_sample[idx]["counter_epoch"] = uuid.uuid4().hex
            _last_sample[idx]["counter_delta_valid"] = False
            _cum_counter_joules[idx] = 0.0


def _sampler():
    """Background loop: integrate observed power into a MODELED cumulative estimate."""
    prev_ts = time.time()
    while True:
        time.sleep(SAMPLE_EVERY_S)
        rows = _read_gpu_power()
        counters_mj = _read_gpu_energy_counters()
        now = time.time()  # observation completion, not the next HTTP request time
        dt = now - prev_ts
        prev_ts = now
        _record_sample(rows, now=now, dt=dt, counters_mj=counters_mj)


def _local_engine(*, now=None):
    """This node's fresh observed power, counter deltas and modeled estimate."""
    now = time.time() if now is None else now
    with _state_lock:
        gpus = []
        estimates = []
        measured = []
        for idx in sorted(_last_sample.keys()):
            s = _last_sample[idx]
            power_w = _finite_nonnegative(s.get("power_w"))
            live = (s.get("live") is True and power_w is not None
                    and _fresh_observation(s.get("ts"), now))
            estimate = (_finite_nonnegative(_cum_joules.get(idx)) if live else None)
            joules = (_finite_nonnegative(_cum_counter_joules.get(idx))
                      if live and s.get("counter_delta_valid") is True else None)
            if estimate is not None:
                estimates.append(estimate)
            if joules is not None:
                measured.append(joules)
            gpus.append({
                "index": idx,
                "name": s.get("name"),
                "power_w": power_w if live else None,
                "joules": round(joules, 3) if joules is not None else None,
                "joules_method": "NVML_COUNTER_DELTA" if joules is not None else None,
                "gpu_uuid": s.get("counter_uuid") if joules is not None else None,
                "counter_epoch": s.get("counter_epoch") if joules is not None else None,
                "estimated_joules": round(estimate, 3) if estimate is not None else None,
                "estimated_joules_label": "MODELED" if estimate is not None else "UNAVAILABLE",
                "sample_ts": s.get("ts"),
                "live": live,
            })
    total_estimate = _finite_nonnegative(sum(estimates)) if estimates else None
    total_measured = (_finite_nonnegative(sum(measured))
                      if gpus and len(measured) == len(gpus) else None)
    return {
        "engine": ENGINE_NAME,
        "joules": round(total_measured, 3) if total_measured is not None else None,
        "joules_method": "NVML_COUNTER_DELTA" if total_measured is not None else None,
        "estimated_joules": (round(total_estimate, 3)
                              if total_estimate is not None else None),
        "estimated_joules_label": "MODELED" if total_estimate is not None else "UNAVAILABLE",
        "gpus": gpus,
    }, total_measured


def _fetch_peer_engines():
    """Fetch peer engines and whether every configured peer returned valid engines."""
    engines = []
    complete = True
    for url in PEER_EXPORTERS:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "omen-joule-exporter/peer"})
            with urllib.request.urlopen(req, timeout=PEER_TIMEOUT_S) as r:  # noqa: S310
                data = json.loads(r.read().decode("utf-8", "replace"))
            peer_engines = data.get("engines")
            if not isinstance(peer_engines, list) or not peer_engines:
                complete = False
                continue
            valid = 0
            for e in peer_engines:
                if not isinstance(e, dict) or not e.get("engine"):
                    continue
                engines.append(e)
                valid += 1
            if valid != len(peer_engines):
                complete = False
        except Exception:
            # Peer down/unreachable => omit it; aggregate completeness fails closed.
            complete = False
            continue
    return engines, complete


def _sanitize_peer_engine(engine, *, now):
    """Rebuild peer totals only from fresh per-GPU hardware-counter evidence."""
    gpus = []
    measured = []
    estimates = []
    raw_gpus = engine.get("gpus")
    for raw in raw_gpus if isinstance(raw_gpus, list) else []:
        if not isinstance(raw, dict):
            continue
        gpu = dict(raw)
        fresh = (gpu.get("live") is True
                 and _fresh_observation(gpu.get("sample_ts"), now))
        power = _finite_nonnegative(gpu.get("power_w")) if fresh else None
        live = fresh and power is not None
        joules = (_finite_nonnegative(gpu.get("joules"))
                  if live and gpu.get("joules_method") == "NVML_COUNTER_DELTA"
                  and isinstance(gpu.get("gpu_uuid"), str) and gpu.get("gpu_uuid")
                  and isinstance(gpu.get("counter_epoch"), str) and gpu.get("counter_epoch")
                  else None)
        estimate = (_finite_nonnegative(gpu.get("estimated_joules"))
                    if live and gpu.get("estimated_joules_label") == "MODELED"
                    else None)
        gpu.update({
            "live": live,
            "power_w": power if live else None,
            "joules": joules,
            "joules_method": "NVML_COUNTER_DELTA" if joules is not None else None,
            "gpu_uuid": gpu.get("gpu_uuid") if joules is not None else None,
            "counter_epoch": gpu.get("counter_epoch") if joules is not None else None,
            "estimated_joules": estimate,
            "estimated_joules_label": "MODELED" if estimate is not None else "UNAVAILABLE",
        })
        gpus.append(gpu)
        if joules is not None:
            measured.append(joules)
        if estimate is not None:
            estimates.append(estimate)
    total_measured = (_finite_nonnegative(sum(measured))
                      if gpus and len(measured) == len(gpus) else None)
    total_estimate = _finite_nonnegative(sum(estimates)) if estimates else None
    out = dict(engine)
    out.update({
        "gpus": gpus,
        "joules": total_measured,
        "joules_method": "NVML_COUNTER_DELTA" if total_measured is not None else None,
        "estimated_joules": total_estimate,
        "estimated_joules_label": "MODELED" if total_estimate is not None else "UNAVAILABLE",
    })
    return out


def _read_models():
    """Project an unverified external model file without promoting its claims.

    The ollama_energy_probe.py source/harness is absent here. Even a fresh file
    self-labeled MEASURED is not proof of a direct NVML counter window, so public
    model joules and joules/token remain null/UNKNOWN. The source file is untouched.
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
    if stale or r.get("label") == "UNAVAILABLE":
        return [{
            "name": name,
            "joules_per_token": None,
            "energy_joules": None,
            "label": "UNAVAILABLE",
            "source": "external_probe_unverified",
            "stale": bool(stale),
            "provenance_status": "EXTERNAL_PROBE_PROVENANCE_UNVERIFIED",
        }]
    return [{
        "name": name,
        "joules_per_token": None,
        "energy_joules": None,
        "label": "UNKNOWN",
        "source": "external_probe_unverified",
        "stale": False,
        "provenance_status": "EXTERNAL_PROBE_PROVENANCE_UNVERIFIED",
    }]


def _meter_json(*, now=None):
    now = time.time() if now is None else now
    local, _ = _local_engine(now=now)
    engines = [local]
    seen = {str(local["engine"]).lower()}
    complete = True
    if PEER_EXPORTERS:
        peer_engines, complete = _fetch_peer_engines()
        for e in peer_engines:
            name = str(e.get("engine")).lower()
            if name in seen:
                complete = False
                continue  # local wins on name collision; never double-count
            seen.add(name)
            engines.append(_sanitize_peer_engine(e, now=now))
    measured = [_finite_nonnegative(e.get("joules")) for e in engines]
    estimated = [_finite_nonnegative(e.get("estimated_joules")) for e in engines]
    measured_uuids = [g.get("gpu_uuid") for e in engines for g in e.get("gpus", [])
                      if _finite_nonnegative(g.get("joules")) is not None]
    unique_devices = (len(measured_uuids) == len(set(measured_uuids))
                      and all(isinstance(u, str) and u for u in measured_uuids))
    total = (_finite_nonnegative(sum(measured))
             if complete and unique_devices and engines
             and all(v is not None for v in measured) else None)
    modeled_total = _finite_nonnegative(sum(v for v in estimated if v is not None)) \
        if any(v is not None for v in estimated) else None
    payload = {
        "engines": engines,
        "totals": {
            "joules": round(total, 3) if total is not None else None,
            "joules_method": "NVML_COUNTER_DELTA" if total is not None else None,
            "estimated_joules": round(modeled_total, 3) if modeled_total is not None else None,
            "estimated_joules_label": "MODELED" if modeled_total is not None else "UNAVAILABLE",
        },
        "exporter": "omen-joule-exporter (power via nvidia-smi; optional NVML counter)"
                    + (" + %d peer(s)" % len(PEER_EXPORTERS) if PEER_EXPORTERS else ""),
        "ts": now,  # response time only; each GPU carries its actual sample_ts
    }
    # Additive unverified model file is normalized to UNKNOWN/null if present.
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
    server_version = "omen-joule-exporter/1.0"

    def do_GET(self):
        if not _client_allowed(self.client_address[0]):
            self.send_error(403)
            return
        payload = json.dumps(_meter_json()).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        try:
            self.wfile.write(payload)
        except BrokenPipeError:
            pass

    def log_message(self, *a):  # quiet
        pass


def main():
    threading.Thread(target=_sampler, daemon=True).start()
    # Warm one immediate sample so the first scrape isn't empty.
    rows = _read_gpu_power()
    counters_mj = _read_gpu_energy_counters()
    _record_sample(rows, now=time.time(), dt=0.0, counters_mj=counters_mj)
    httpd = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    peers = (" + peers: %s" % ", ".join(PEER_EXPORTERS)) if PEER_EXPORTERS else ""
    print("omen-joule-exporter serving on 0.0.0.0:%d (engine=%s)%s" % (PORT, ENGINE_NAME, peers))
    httpd.serve_forever()


if __name__ == "__main__":
    main()
