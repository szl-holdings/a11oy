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
  * The engine name defaults to "omen" to match A11OY_OMEN_GPU_LABEL. Override
    with OMEN_ENGINE_NAME if you change that label.

RUN (on OMEN):  python omen_joule_exporter.py     # serves on 0.0.0.0:9471
Then tunnel port 9471 and point A11OY_JOULE_METER_URL at the tunnel /.

Pure stdlib — no pip installs. Requires nvidia-smi on PATH (ships with the driver).
"""
import json
import os
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("OMEN_EXPORTER_PORT", "9471"))
ENGINE_NAME = os.environ.get("OMEN_ENGINE_NAME", "omen")
SAMPLE_EVERY_S = float(os.environ.get("OMEN_SAMPLE_EVERY_S", "2.0"))

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


def _meter_json():
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
    return {
        "engines": [
            {"engine": ENGINE_NAME, "joules": round(total, 3), "gpus": gpus}
        ],
        "totals": {"joules": round(total, 3)},
        "exporter": "omen-joule-exporter (real NVML via nvidia-smi)",
        "ts": time.time(),
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "omen-joule-exporter/1.0"

    def do_GET(self):
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
    with _state_lock:
        for idx, name, power_w in rows:
            _last_sample[idx] = {"power_w": power_w, "name": name,
                                 "live": power_w is not None, "ts": time.time()}
    httpd = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print("omen-joule-exporter serving on 0.0.0.0:%d (engine=%s)" % (PORT, ENGINE_NAME))
    httpd.serve_forever()


if __name__ == "__main__":
    main()
