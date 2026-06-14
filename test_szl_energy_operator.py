# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · Doctrine v11
"""test_szl_energy_operator.py — guards the press-play ENERGY OPERATOR daemon.

Doctrine v11 — proves, OFFLINE and deterministically (no real GPU needed):
  (1) the operator runs >= 3 REAL jobs against a REACHABLE node (a faithful local
      HTTP stub of the Ollama OpenAI-compatible API + a fake NVML joule-meter that
      advances cumulative joules each call) and measures joules_measured > 0;
  (2) jobs_done increments and tokens_total grows from real responses;
  (3) start() / stop() are clean and idempotent; the loop is graceful;
  (4) a restart RESUMES cumulative counts from the persisted ledger;
  (5) an UNREACHABLE node is marked DEGRADED — never a fabricated job or joule;
  (6) the no-GPU sandbox path falls back to a clearly-marked STUB whose energy is
      ALWAYS SAMPLE and NEVER billable (no fabricated measured joule);
  (7) the JobRecord interface Dev2/3/4 consume is stable and self-verifying;
  (8) a STALE meter sample (>30s) downgrades a job's energy to SAMPLE (not billable).

Run: python test_szl_energy_operator.py   (also collectable by pytest)
"""
from __future__ import annotations

import http.server
import json
import os
import tempfile
import threading
import time

import szl_energy_operator as OP
import szl_joules_truth as J


# ---------------------------------------------------------------------------
# A faithful local stand-in for an Ollama GPU node: an OpenAI-compatible
# /v1/chat/completions + /v1/models + native /api/embeddings, AND a joule-meter
# JSON endpoint whose cumulative joules ADVANCE on every inference call (so the
# operator's before/after NVML delta is a real positive measured number).
# ---------------------------------------------------------------------------
class _FakeNode:
    def __init__(self):
        self._joules = 1000.0          # cumulative joules counter (advances per call)
        self._lock = threading.Lock()
        self._server = None
        self._thread = None
        self.port = None

    def _advance(self, j: float) -> None:
        with self._lock:
            self._joules += j

    def meter_json(self) -> dict:
        with self._lock:
            j = self._joules
        return {"engines": [{"engine": "betterwithage", "power_source": "nvml",
                             "joules": j,
                             "gpus": [{"gpu": 0, "name": "RTX", "power_w": 210.0,
                                       "live": True, "joules": j}]}],
                "totals": {"joules": j, "kwh": j / 3_600_000.0, "eur_per_mwh": 62.08},
                "generated_at": "now"}

    def start(self) -> str:
        node = self

        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):  # silence
                pass

            def _send(self, obj, code=200):
                body = json.dumps(obj).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if self.path.rstrip("/") == "/v1/models" or self.path == "/v1/models":
                    self._send({"object": "list", "data": [{"id": "llama3.1:8b"}]})
                elif self.path.rstrip("/") in ("", "/v1"):
                    self._send({"ok": True})
                elif self.path.rstrip("/") == "/meter":
                    self._send(node.meter_json())
                else:
                    self._send({"ok": True})

            def do_POST(self):
                length = int(self.headers.get("Content-Length", "0") or "0")
                _ = self.rfile.read(length)
                # Every real inference call burns measurable energy on this "GPU".
                node._advance(15.0)
                if self.path.endswith("/chat/completions"):
                    self._send({
                        "id": "cmpl-test", "object": "chat.completion",
                        "choices": [{"message": {"role": "assistant",
                                                 "content": "Sovereign compute is metered."}}],
                        "usage": {"completion_tokens": 7, "prompt_tokens": 9,
                                  "total_tokens": 16}})
                elif self.path.endswith("/api/embeddings"):
                    self._send({"embedding": [0.1, 0.2, 0.3, 0.4]})
                else:
                    self._send({"ok": True})

        self._server = http.server.HTTPServer(("127.0.0.1", 0), H)
        self.port = self._server.server_port
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return f"http://127.0.0.1:{self.port}/v1"

    def stop(self):
        if self._server:
            self._server.shutdown()
            self._server.server_close()


def _node_cfg(base_url: str) -> OP.NodeCfg:
    return OP.NodeCfg(name="rtx-betterwithage", base_url=base_url,
                      gen_model="llama3.1:8b", embed_model="bge-large",
                      exporter_node="betterwithage")


# ---------------------------------------------------------------------------
# (1)+(2) >= 3 REAL jobs against a REACHABLE node, measures joules > 0.
# ---------------------------------------------------------------------------
def test_real_jobs_measure_joules(monkeypatch):
    node = _FakeNode()
    base = node.start()
    try:
        meter_url = f"http://127.0.0.1:{node.port}/meter"
        monkeypatch.setattr(OP, "_JOULE_METER_URL", meter_url)
        with tempfile.TemporaryDirectory() as d:
            op = OP.OperatorDaemon(nodes=[_node_cfg(base)],
                                   state_path=os.path.join(d, "ledger.json"),
                                   allow_stub=False)
            # Two sweeps => 4 jobs (generate+embed each) — well over the >=3 mandate.
            op.run_once()
            op.run_once()
            st = op.status()
            assert st["jobs_done"] >= 3, st
            assert st["tokens_total"] > 0, st
            assert st["stub_mode"] is False, st
            # Real NVML delta => MEASURED billable joules > 0.
            assert st["joules_measured_total"] > 0, st
            assert st["measured_jobs"] >= 3, st
            assert "rtx-betterwithage" in st["nodes_computing"], st
            assert st["nodes_degraded"] == [], st
    finally:
        node.stop()


# ---------------------------------------------------------------------------
# (3) start()/stop() clean + idempotent; loop is graceful.
# ---------------------------------------------------------------------------
def test_start_stop_clean(monkeypatch):
    node = _FakeNode()
    base = node.start()
    try:
        monkeypatch.setattr(OP, "_JOULE_METER_URL", f"http://127.0.0.1:{node.port}/meter")
        with tempfile.TemporaryDirectory() as d:
            op = OP.OperatorDaemon(nodes=[_node_cfg(base)],
                                   state_path=os.path.join(d, "ledger.json"),
                                   job_interval_s=0.01, allow_stub=False)
            assert op.is_running() is False
            op.start()
            assert op.is_running() is True
            op.start()  # idempotent: second start does not spawn a second thread
            time.sleep(0.4)
            op.stop()
            assert op.is_running() is False
            op.stop()  # idempotent stop
            st = op.status()
            assert st["running"] is False
            assert st["jobs_done"] >= 3, st
            assert st["joules_measured_total"] > 0, st
    finally:
        node.stop()


# ---------------------------------------------------------------------------
# (4) restart RESUMES cumulative counts from the persisted ledger.
# ---------------------------------------------------------------------------
def test_restart_resumes_state(monkeypatch):
    node = _FakeNode()
    base = node.start()
    try:
        monkeypatch.setattr(OP, "_JOULE_METER_URL", f"http://127.0.0.1:{node.port}/meter")
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "ledger.json")
            op = OP.OperatorDaemon(nodes=[_node_cfg(base)], state_path=path,
                                   allow_stub=False)
            op.run_once()
            st1 = op.status()
            assert st1["jobs_done"] >= 2
            assert os.path.exists(path), "ledger must be persisted"
            # Fresh daemon, same ledger path => counts resume (not reset to zero).
            op2 = OP.OperatorDaemon(nodes=[_node_cfg(base)], state_path=path,
                                    allow_stub=False)
            st2 = op2.status()
            assert st2["jobs_done"] == st1["jobs_done"], (st1, st2)
            assert st2["joules_measured_total"] == st1["joules_measured_total"]
            assert st2["tokens_total"] == st1["tokens_total"]
            # And it keeps counting up from the resumed baseline.
            op2.run_once()
            assert op2.status()["jobs_done"] > st1["jobs_done"]
    finally:
        node.stop()


# ---------------------------------------------------------------------------
# (5) UNREACHABLE node => DEGRADED, never a fabricated job/joule.
# ---------------------------------------------------------------------------
def test_unreachable_node_degraded_not_faked():
    with tempfile.TemporaryDirectory() as d:
        # 192.0.2.1 is TEST-NET-1 (RFC 5737) — guaranteed unreachable.
        op = OP.OperatorDaemon(
            nodes=[OP.NodeCfg("rtx-betterwithage", "http://192.0.2.1:11434/v1",
                              "llama3.1:8b", "bge-large", "betterwithage")],
            state_path=os.path.join(d, "ledger.json"), allow_stub=False)
        produced = op.run_once()
        assert produced == [], "unreachable node must produce NO job records"
        st = op.status()
        assert "rtx-betterwithage" in st["nodes_degraded"], st
        assert st["jobs_done"] == 0, st
        assert st["joules_measured_total"] == 0.0, st  # never fabricated


# ---------------------------------------------------------------------------
# (6) no reachable node => STUB fallback; real work, energy SAMPLE, NOT billable.
# ---------------------------------------------------------------------------
def test_stub_mode_real_work_no_billable_joules():
    with tempfile.TemporaryDirectory() as d:
        op = OP.OperatorDaemon(
            nodes=[OP.NodeCfg("rtx-betterwithage", "http://192.0.2.1:11434/v1",
                              "llama3.1:8b", "bge-large", "betterwithage")],
            state_path=os.path.join(d, "ledger.json"), stub_work=5000, allow_stub=True)
        produced = op.run_once()
        assert len(produced) >= 2, produced
        st = op.status()
        assert st["stub_mode"] is True, st
        assert st["jobs_done"] >= 2 and st["tokens_total"] > 0, st
        # Stub energy is SAMPLE by construction — NEVER billable.
        assert st["joules_measured_total"] == 0.0, st
        assert st["sample_jobs"] >= 2, st
        for rec in produced:
            assert rec["joules_label"] == OP.LABEL_SAMPLE, rec
            assert rec["joules_measured"] is None, rec
            assert rec["node"] == "local-stub", rec


# ---------------------------------------------------------------------------
# (7) JobRecord interface is stable + self-verifying (the Dev2/3/4 contract).
# ---------------------------------------------------------------------------
def test_jobrecord_interface_contract():
    with tempfile.TemporaryDirectory() as d:
        op = OP.OperatorDaemon(nodes=[], state_path=os.path.join(d, "l.json"))
        captured = []
        op.subscribe(lambda r: captured.append(r))
        sample = {"joules_measured_total": 500.0, "exporter_node": "betterwithage",
                  "exporter_last_seen_ts": time.time(), "power_w_sample": 210.0}
        rec = op._commit("betterwithage", "llama3.1:8b", "generate", 7, 0.9, sample, 15.0)
        d_rec = rec.to_dict()
        for key in ("node", "model", "kind", "tokens", "wall_s", "joules_measured",
                    "joules_label", "joules_evidence", "ts", "seq"):
            assert key in d_rec, (key, d_rec)
        assert d_rec["joules_label"] == OP.LABEL_MEASURED
        assert d_rec["joules_measured"] == 15.0
        # Evidence present iff MEASURED, and self-verifying off szl_joules_truth.
        assert d_rec["joules_evidence"]["joules_measured_total"] == 500.0
        # The subscribe() callback (Dev2 receipts hook) fired with the same record.
        assert captured and captured[-1]["seq"] == d_rec["seq"]


# ---------------------------------------------------------------------------
# (8) STALE meter sample (>30s) => job energy SAMPLE, not billable.
# ---------------------------------------------------------------------------
def test_stale_sample_not_billable():
    with tempfile.TemporaryDirectory() as d:
        op = OP.OperatorDaemon(nodes=[], state_path=os.path.join(d, "l.json"))
        stale_ts = time.time() - (J.FRESHNESS_WINDOW_S + 60.0)
        stale = {"joules_measured_total": 500.0, "exporter_node": "betterwithage",
                 "exporter_last_seen_ts": stale_ts, "power_w_sample": 210.0}
        rec = op._commit("betterwithage", "llama3.1:8b", "generate", 7, 0.9, stale, 15.0)
        assert rec.joules_label == OP.LABEL_SAMPLE, rec
        assert rec.joules_measured is None, rec
        st = op.status()
        assert st["joules_measured_total"] == 0.0, st
        assert st["sample_jobs"] == 1, st


# ---------------------------------------------------------------------------
# (9) endpoints register (dual-namespace) on a FastAPI app.
# ---------------------------------------------------------------------------
def test_register_dual_namespace():
    from fastapi import FastAPI
    app = FastAPI()
    res = OP.register(app, ns="a11oy")
    assert res["ok"] is True
    paths = {r.path for r in app.routes}
    for p in ("/api/a11oy/v1/energy/operator/start",
              "/api/a11oy/v1/energy/operator/stop",
              "/api/a11oy/v1/energy/operator/status",
              "/v1/energy/operator/start",
              "/v1/energy/operator/stop",
              "/v1/energy/operator/status"):
        assert p in paths, (p, sorted(paths))


if __name__ == "__main__":
    import sys
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]

    class _MP:
        def __init__(self): self._undo = []
        def setattr(self, obj, name, val):
            self._undo.append((obj, name, getattr(obj, name)))
            setattr(obj, name, val)
        def undo(self):
            for obj, name, old in reversed(self._undo):
                setattr(obj, name, old)
            self._undo = []

    passed = 0
    for fn in fns:
        mp = _MP()
        try:
            if "monkeypatch" in fn.__code__.co_varnames[:fn.__code__.co_argcount]:
                fn(mp)
            else:
                fn()
            print(f"  PASS {fn.__name__}")
            passed += 1
        except Exception as e:  # noqa: BLE001
            print(f"  FAIL {fn.__name__}: {e}")
            raise
        finally:
            mp.undo()
    print(f"\n{passed}/{len(fns)} tests passed")
    sys.exit(0 if passed == len(fns) else 1)
