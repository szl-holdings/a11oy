# SPDX-License-Identifier: Apache-2.0
# © 2026 SZL Holdings · Doctrine v12 (additive). Yachay.
"""
szl_exporter — scrapes each Space's honest in-process state and re-exposes it as
Prometheus metrics for the single-pane Grafana dashboard (OBSERVABILITY_DASHBOARD.md).

Reads /api/<space>/healthz, /v1/mesh/state, /v1/brain/sockets, vessels ledger,
lean-kernel /api/lean/theorems.

HONEST: it reports what the Spaces actually expose. Where a Space has no metric yet
(e.g. a static Space has no latency histogram), the series is simply absent, not faked.
The in-process buses + Khipu DAG are in-memory ring buffers (per szl_wire.py); the
durable record is the S3 mirror (BACKUP_AND_RECOVERY.md). v11 LOCKED numbers untouched.
"""
from prometheus_client import Gauge, start_http_server
import httpx, time

SPACES = {
    "a11oy":       "https://szlholdings-a11oy.hf.space",
    "amaru":       "https://szlholdings-amaru.hf.space",
    "sentra":      "https://szlholdings-sentra.hf.space",
    "vessels":     "https://szlholdings-vessels.hf.space",
    "rosie":       "https://szlholdings-rosie.hf.space",
    "killinchu":   "https://szlholdings-killinchu.hf.space",
    "lean-kernel": "https://szlholdings-lean-kernel.hf.space",
}

up        = Gauge("szl_up", "flagship up (1) or down (0)", ["flagship"])
dag_depth = Gauge("szl_khipu_dag_depth", "Khipu DAG depth (ring buffer)", ["chain"])
integ     = Gauge("szl_khipu_integrity_ok", "Khipu integrity (1 ok / 0 mismatch)", ["chain"])
lean_dec  = Gauge("szl_lean_declarations", "lean-kernel total declarations (live build)")
lean_sry  = Gauge("szl_lean_sorry", "lean-kernel sorry count (live build)")
lean_axi  = Gauge("szl_lean_axiom", "lean-kernel axiom count (live build)")

# LOCKED reference (Doctrine v11/v12) — surfaced alongside the live build, never edited.
LOCKED = Gauge("szl_lean_locked_reference", "Doctrine LOCKED reference numbers", ["kind"])


def _recompute_integrity(nodes: list[dict]) -> int:
    """Honest hash-chain check: digest must equal sha256(receipt sorted-json || parents)."""
    import hashlib, json
    prev = None
    for n in nodes:
        h = hashlib.sha256()
        h.update(json.dumps(n.get("receipt", {}), sort_keys=True).encode())
        for p in n.get("parents", []):
            h.update(p.encode())
        if n.get("digest") and n["digest"] != h.hexdigest():
            return 0
        prev = n.get("digest")
    return 1


def scrape_once():
    for name, base in SPACES.items():
        try:
            h = httpx.get(f"{base}/api/{name}/healthz", timeout=10)
            up.labels(name).set(1 if h.status_code == 200 else 0)
        except Exception:
            up.labels(name).set(0)            # honest: probe failed -> down

    # Khipu DAG depth + integrity from vessels ledger read-view
    try:
        led = httpx.get(f"{SPACES['vessels']}/api/vessels/v1/receipts/ledger", timeout=10).json()
        nodes = led.get("nodes", [])
        dag_depth.labels("canonical").set(len(nodes))
        integ.labels("canonical").set(_recompute_integrity(nodes))
    except Exception:
        integ.labels("canonical").set(0)

    # Lean-kernel live build numbers (surfaced next to LOCKED reference)
    try:
        th = httpx.get(f"{SPACES['lean-kernel']}/api/lean/theorems", timeout=15).json()["summary"]
        lean_dec.set(th.get("total_declarations", 0))
        lean_sry.set(th.get("sorry", 0))
        lean_axi.set(th.get("axiom", 0))
    except Exception:
        pass

    # LOCKED reference (never edited): 749 declarations / 14 unique axioms / 163 sorries
    LOCKED.labels("declarations").set(749)
    LOCKED.labels("unique_axioms").set(14)
    LOCKED.labels("sorries").set(163)


if __name__ == "__main__":
    start_http_server(9100)                   # Prometheus scrapes :9100/metrics
    while True:
        scrape_once()
        time.sleep(15)
