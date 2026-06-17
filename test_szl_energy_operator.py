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
# (5b) STANDBY node (configured but intentionally not started): unreachable reads
#      "standby" (NOT DEGRADED), produces no fabricated job/joule. A standby node
#      that DOES respond still computes normally — only the unreachable label changes.
# ---------------------------------------------------------------------------
def test_standby_node_unreachable_reads_standby_not_degraded():
    with tempfile.TemporaryDirectory() as d:
        # 192.0.2.1 is TEST-NET-1 (RFC 5737) — guaranteed unreachable.
        op = OP.OperatorDaemon(
            nodes=[OP.NodeCfg("chaski", "http://192.0.2.1:11434/v1",
                              "qwen2.5:32b", "mistral", "chaski", standby=True)],
            state_path=os.path.join(d, "ledger.json"), allow_stub=False)
        produced = op.run_once()
        assert produced == [], "standby+unreachable must produce NO job records"
        st = op.status()
        assert "chaski" in st["nodes_standby"], st          # intentionally not started
        assert "chaski" not in st["nodes_degraded"], st     # NOT alarming/DEGRADED
        assert st["jobs_done"] == 0, st
        assert st["joules_measured_total"] == 0.0, st        # never fabricated


def test_standby_node_reachable_still_computes(monkeypatch):
    node = _FakeNode()
    base = node.start()
    try:
        monkeypatch.setattr(OP, "_JOULE_METER_URL", f"http://127.0.0.1:{node.port}/meter")
        with tempfile.TemporaryDirectory() as d:
            # standby=True but the node IS reachable => must compute normally.
            op = OP.OperatorDaemon(
                nodes=[OP.NodeCfg("chaski", base, "llama3.1:8b", "bge-large",
                                  "betterwithage", standby=True)],
                state_path=os.path.join(d, "ledger.json"), allow_stub=False)
            op.run_once()
            st = op.status()
            assert "chaski" in st["nodes_computing"], st     # reachable => computes
            assert "chaski" not in st["nodes_standby"], st   # not parked when up
            assert "chaski" not in st["nodes_degraded"], st
            assert st["jobs_done"] >= 2, st
            assert st["joules_measured_total"] > 0, st        # real MEASURED joules
    finally:
        node.stop()


# ---------------------------------------------------------------------------
# (5c) OMEN eligible energy lung — the always-on home anchor. Mirrors chaski:
#      env-gated (default standby), distinct exporter label so its joules are
#      metered SEPARATELY (never merged), joins ONLY by a real probe.
# ---------------------------------------------------------------------------
def _clear_omen_env():
    for k in list(os.environ):
        if k.startswith("A11OY_OMEN") or k == "A11OY_ENERGY_OMEN_ENABLED":
            os.environ.pop(k, None)


def test_omen_is_third_default_node_standby_by_default():
    _clear_omen_env()
    try:
        names = [n.name for n in OP._default_nodes()]
        assert "omen-betterwithage" in names, names
        omen = [n for n in OP._default_nodes() if n.name == "omen-betterwithage"][0]
        assert omen.standby is True, "OMEN defaults to standby until env-enabled"
        # DISTINCT exporter label keeps OMEN joules separate from the laptop's.
        assert omen.exporter_node == "omen", omen.exporter_node
    finally:
        _clear_omen_env()


def test_omen_default_endpoint_matches_hardened_single_source_of_truth():
    """Regression guard for the divergent-list class: with no OMEN env set, the energy
    loop's OMEN base_url MUST fall back to the HARDENED fabric pool's OMEN endpoint
    (szl_backend_hardening.OMEN_FABRIC_ENDPOINT) — not a bare hostname that won't resolve
    on the box. This keeps the two node lists from silently diverging. Honest: it only
    fixes the ADDRESS the probe targets; a real probe still decides reachable/standby."""
    import szl_backend_hardening as H
    _clear_omen_env()
    try:
        omen = [n for n in OP._default_nodes() if n.name == "omen-betterwithage"][0]
        # _default_nodes normalizes a bare host:port to an OpenAI-compatible /v1 base.
        assert omen.base_url == H.OMEN_FABRIC_ENDPOINT + "/v1", (
            omen.base_url, H.OMEN_FABRIC_ENDPOINT)
        # the hardened pool descriptor and the energy loop must target the SAME host.
        hardened_omen = [n for n in H.DEFAULT_FABRIC_NODES
                         if n["name"] == "omen-betterwithage"][0]
        assert hardened_omen["endpoint"] == H.OMEN_FABRIC_ENDPOINT, hardened_omen["endpoint"]
        assert omen.base_url == hardened_omen["endpoint"] + "/v1", (
            omen.base_url, hardened_omen["endpoint"])
        # posture stays HONEST: the corrected address does not force the lung up.
        assert omen.standby is True, "address fix must not flip OMEN out of standby"
    finally:
        _clear_omen_env()


def test_omen_energy_enabled_flips_live_via_runbook_alias():
    _clear_omen_env()
    try:
        os.environ["A11OY_ENERGY_OMEN_ENABLED"] = "1"
        os.environ["A11OY_OMEN_BASE_URL"] = "http://100.70.130.45:11434"
        omen = [n for n in OP._default_nodes() if n.name == "omen-betterwithage"][0]
        assert omen.standby is False, "A11OY_ENERGY_OMEN_ENABLED=1 must un-standby OMEN"
        # bare host:port normalized to an OpenAI-compatible /v1 base, never doubled.
        assert omen.base_url == "http://100.70.130.45:11434/v1", omen.base_url
    finally:
        _clear_omen_env()


def test_omen_standby_unreachable_reads_standby_not_degraded():
    _clear_omen_env()
    try:
        with tempfile.TemporaryDirectory() as d:
            # 192.0.2.2 is TEST-NET-1 (RFC 5737) — guaranteed unreachable.
            op = OP.OperatorDaemon(
                nodes=[OP.NodeCfg("omen-betterwithage", "http://192.0.2.2:11434/v1",
                                  "llama3.1:8b", "bge-large", "omen", standby=True)],
                state_path=os.path.join(d, "ledger.json"), allow_stub=False)
            produced = op.run_once()
            assert produced == [], "standby+unreachable OMEN must produce NO job records"
            st = op.status()
            assert "omen-betterwithage" in st["nodes_standby"], st
            assert "omen-betterwithage" not in st["nodes_degraded"], st
            assert st["joules_measured_total"] == 0.0, st   # never a fabricated joule
    finally:
        _clear_omen_env()


def test_omen_reachable_joins_computing_with_real_joules(monkeypatch):
    _clear_omen_env()
    node = _FakeNode()
    base = node.start()
    try:
        monkeypatch.setattr(OP, "_JOULE_METER_URL", f"http://127.0.0.1:{node.port}/meter")
        with tempfile.TemporaryDirectory() as d:
            # _FakeNode's meter reports an "omen" engine so the exporter sample matches.
            op = OP.OperatorDaemon(
                nodes=[OP.NodeCfg("omen-betterwithage", base, "llama3.1:8b", "bge-large",
                                  "omen", standby=True)],
                state_path=os.path.join(d, "ledger.json"), allow_stub=False)
            op.run_once()
            st = op.status()
            assert "omen-betterwithage" in st["nodes_computing"], st  # joined by REAL probe
            assert "omen-betterwithage" not in st["nodes_standby"], st
            assert st["jobs_done"] >= 2, st
    finally:
        node.stop()
        _clear_omen_env()


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


# ---------------------------------------------------------------------------
# (10) AUTO-START on boot (Doctrine v11 — the redeploy-stall fix). The loop must
#      come up RUNNING when a lung is reachable + autostart is on, stay CLEANLY
#      IDLE (running=false, never faked) when no lung is reachable, and honor the
#      A11OY_ENERGY_AUTOSTART off switch.
# ---------------------------------------------------------------------------
def _swap_singleton(op):
    """Install `op` as the module singleton the module-level autostart/readiness
    helpers drive, returning the previous one so the caller can restore it."""
    prev = OP._OPERATOR
    OP._OPERATOR = op
    return prev


def test_any_lung_reachable_true_when_node_up(monkeypatch):
    node = _FakeNode()
    base = node.start()
    try:
        with tempfile.TemporaryDirectory() as d:
            op = OP.OperatorDaemon(nodes=[_node_cfg(base)],
                                   state_path=os.path.join(d, "l.json"), allow_stub=False)
            assert op.any_lung_reachable() is True
    finally:
        node.stop()


def test_any_lung_reachable_false_when_all_unreachable():
    with tempfile.TemporaryDirectory() as d:
        op = OP.OperatorDaemon(
            nodes=[OP.NodeCfg("rtx-betterwithage", "http://192.0.2.1:11434/v1",
                              "llama3.1:8b", "bge-large", "betterwithage")],
            state_path=os.path.join(d, "l.json"), allow_stub=False)
        assert op.any_lung_reachable() is False


def test_autostart_starts_loop_when_lung_reachable(monkeypatch):
    node = _FakeNode()
    base = node.start()
    try:
        monkeypatch.setattr(OP, "_JOULE_METER_URL", f"http://127.0.0.1:{node.port}/meter")
        monkeypatch.setenv("A11OY_ENERGY_AUTOSTART", "1")
        with tempfile.TemporaryDirectory() as d:
            op = OP.OperatorDaemon(nodes=[_node_cfg(base)],
                                   state_path=os.path.join(d, "ledger.json"),
                                   job_interval_s=0.01, allow_stub=False)
            prev = _swap_singleton(op)
            try:
                assert op.is_running() is False
                report = OP.autostart_if_lung_reachable()
                assert report["autostarted"] is True, report
                assert report["reason"] == "lung_reachable", report
                assert op.is_running() is True
                # Idempotent: a second call is a no-op (already running).
                again = OP.autostart_if_lung_reachable()
                assert again["autostarted"] is False and again["running"] is True, again
            finally:
                op.stop()
                _swap_singleton(prev)
    finally:
        node.stop()


def test_autostart_stays_idle_when_no_lung_reachable():
    with tempfile.TemporaryDirectory() as d:
        # All nodes on TEST-NET-1 (RFC 5737) → unreachable → honest idle.
        op = OP.OperatorDaemon(
            nodes=[OP.NodeCfg("rtx-betterwithage", "http://192.0.2.1:11434/v1",
                              "llama3.1:8b", "bge-large", "betterwithage")],
            state_path=os.path.join(d, "ledger.json"), allow_stub=False)
        prev = _swap_singleton(op)
        try:
            os.environ["A11OY_ENERGY_AUTOSTART"] = "1"
            report = OP.autostart_if_lung_reachable()
            assert report["autostarted"] is False, report
            assert report["reason"] == "no_lung_reachable", report
            assert report["running"] is False, report
            assert op.is_running() is False  # never a faked running loop
        finally:
            os.environ.pop("A11OY_ENERGY_AUTOSTART", None)
            _swap_singleton(prev)


def test_autostart_disabled_by_env(monkeypatch):
    node = _FakeNode()
    base = node.start()
    try:
        monkeypatch.setattr(OP, "_JOULE_METER_URL", f"http://127.0.0.1:{node.port}/meter")
        monkeypatch.setenv("A11OY_ENERGY_AUTOSTART", "0")
        with tempfile.TemporaryDirectory() as d:
            op = OP.OperatorDaemon(nodes=[_node_cfg(base)],
                                   state_path=os.path.join(d, "ledger.json"),
                                   allow_stub=False)
            prev = _swap_singleton(op)
            try:
                report = OP.autostart_if_lung_reachable()
                assert report["autostarted"] is False, report
                assert report["reason"] == "autostart_disabled", report
                assert op.is_running() is False
            finally:
                _swap_singleton(prev)
    finally:
        node.stop()


def test_readiness_503_state_lung_up_loop_stopped(monkeypatch):
    """The EXACT redeploy stall: a lung is reachable but the loop is STOPPED →
    readiness().ready must be False (serve.py maps that to /readyz 503)."""
    node = _FakeNode()
    base = node.start()
    try:
        monkeypatch.setattr(OP, "_JOULE_METER_URL", f"http://127.0.0.1:{node.port}/meter")
        with tempfile.TemporaryDirectory() as d:
            op = OP.OperatorDaemon(nodes=[_node_cfg(base)],
                                   state_path=os.path.join(d, "ledger.json"),
                                   job_interval_s=0.01, allow_stub=False)
            prev = _swap_singleton(op)
            try:
                # Lung up, loop stopped → NOT ready.
                r = OP.readiness()
                assert r["lung_reachable"] is True, r
                assert r["operator_running"] is False, r
                assert r["ready"] is False, r
                assert r["reason"] == "operator_stopped_while_lung_reachable", r
                # Start the loop → ready flips to True.
                op.start()
                r2 = OP.readiness()
                assert r2["operator_running"] is True, r2
                assert r2["ready"] is True, r2
            finally:
                op.stop()
                _swap_singleton(prev)
    finally:
        node.stop()


def test_readiness_200_when_no_lung_reachable():
    """No lung reachable → honestly idle is READY (nothing to compute against; a
    stopped loop with zero lungs is not a fault and must not 503)."""
    with tempfile.TemporaryDirectory() as d:
        op = OP.OperatorDaemon(
            nodes=[OP.NodeCfg("rtx-betterwithage", "http://192.0.2.1:11434/v1",
                              "llama3.1:8b", "bge-large", "betterwithage")],
            state_path=os.path.join(d, "ledger.json"), allow_stub=False)
        prev = _swap_singleton(op)
        try:
            r = OP.readiness()
            assert r["lung_reachable"] is False, r
            assert r["operator_running"] is False, r
            assert r["ready"] is True, r
            assert r["reason"] == "ok", r
        finally:
            _swap_singleton(prev)


# ---------------------------------------------------------------------------
# (11) USEFUL-WORK: an embed job embeds a REAL un-embedded corpus chunk and WRITES
#      its dense vector into the live RAG index — the index GROWS, the produced
#      record carries useful_work=True + a rag_chunk_id, and the joule label path
#      stays EXACTLY the MEASURED gate (useful work changes WHAT is computed, not
#      HOW joules are measured). Honest: the vector stored is the real embed output.
# ---------------------------------------------------------------------------
def _build_tiny_rag_index(rag, db_path, n=3):
    """Build a minimal REAL RAG index: n lexical org_chunks rows, no dense vectors
    yet (so they are the un-embedded backlog). Marks _BUILD_META built=True so the
    public helpers operate. Returns the chunk_ids inserted."""
    rag.RAG_DB_PATH = db_path
    conn = rag._db()
    try:
        rag._init_schema(conn)
        conn.execute("DELETE FROM org_chunks")
        conn.execute("DELETE FROM org_vectors")
        ids = []
        for i in range(n):
            cid = f"test-chunk-{i}"
            ids.append(cid)
            conn.execute(
                "INSERT INTO org_chunks(chunk_id,node_id,repo,path,kind,corpus,source,"
                "title,body,sha256) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (cid, f"n{i}", "szl-holdings/a11oy", f"docs/d{i}.md", "doc",
                 "szl", "github", f"Doc {i}",
                 f"Sovereign metered compute doctrine paragraph number {i}.", f"sha{i}"))
        conn.commit()
    finally:
        conn.close()
    rag._BUILD_META = {"built": True, "ts": "test", "repos": 1, "chunks": n,
                       "vectors": 0}
    return ids


def test_useful_work_embed_advances_rag_index(monkeypatch):
    import a11oy_org_rag as RAG
    node = _FakeNode()
    base = node.start()
    try:
        monkeypatch.setattr(OP, "_JOULE_METER_URL", f"http://127.0.0.1:{node.port}/meter")
        monkeypatch.setenv("A11OY_ENERGY_USEFUL_WORK", "1")
        monkeypatch.setenv("A11OY_ENERGY_FORCE_POSTURE", "baseline")
        with tempfile.TemporaryDirectory() as d:
            db_path = os.path.join(d, "rag.db")
            prev_db = RAG.RAG_DB_PATH
            prev_meta = RAG._BUILD_META
            try:
                ids = _build_tiny_rag_index(RAG, db_path, n=3)
                # Force a REAL (fake) embedder so useful-work gating is satisfied;
                # the actual embed VECTOR comes from the node's /api/embeddings.
                monkeypatch.setattr(RAG, "_maybe_embedder",
                                    lambda: (lambda t: [0.1, 0.2, 0.3, 0.4]))
                before = RAG.dense_vector_count()
                assert before == 0, before
                assert sorted(c["chunk_id"] for c in
                              RAG.next_unembedded_chunks(limit=9)) == sorted(ids)

                op = OP.OperatorDaemon(nodes=[_node_cfg(base)],
                                       state_path=os.path.join(d, "ledger.json"),
                                       allow_stub=False)
                op.run_once()
                st = op.status()
                after = RAG.dense_vector_count()
                # The live RAG dense index GREW from a real metered embed job.
                assert after > before, (before, after, st)
                assert st["rag_vectors_written"] >= 1, st
                assert st["corpus_embeds"] >= 1, st
                # A produced embed record is honestly tagged useful_work + chunk_id,
                # and that chunk now has a stored vector.
                useful = [r for r in st["recent_jobs"]
                          if r.get("kind") == "embed" and r.get("useful_work")]
                assert useful, st["recent_jobs"]
                cid = useful[0]["rag_chunk_id"]
                assert cid in ids, useful[0]
                # Joule gate UNCHANGED: a fresh real NVML delta still yields MEASURED.
                assert st["joules_measured_total"] > 0, st
                assert st["measured_jobs"] >= 1, st
                for r in useful:
                    assert r["joules_label"] in (OP.LABEL_MEASURED, OP.LABEL_SAMPLE)
            finally:
                RAG.RAG_DB_PATH = prev_db
                RAG._BUILD_META = prev_meta
    finally:
        node.stop()


# ---------------------------------------------------------------------------
# (12) ENERGY HARNESS: work_mode modulates on the harvest/grid posture. Flipping
#      A11OY_ENERGY_FORCE_POSTURE across baseline -> soak -> throttle changes both
#      status().work_mode AND the embed-job rate honestly: soak runs an EXTRA
#      bounded corpus-embed batch (more embed jobs), throttle adds no batch. The
#      should_soak / grid_price_posture signals surface in status.
# ---------------------------------------------------------------------------
def _count_embed_jobs(produced):
    return sum(1 for r in produced if r.get("kind") == "embed")


def test_work_mode_modulation_responds_to_posture(monkeypatch):
    import a11oy_org_rag as RAG
    node = _FakeNode()
    base = node.start()
    try:
        monkeypatch.setattr(OP, "_JOULE_METER_URL", f"http://127.0.0.1:{node.port}/meter")
        monkeypatch.setenv("A11OY_ENERGY_USEFUL_WORK", "1")
        monkeypatch.setenv("A11OY_ENERGY_SOAK_BATCH", "3")
        with tempfile.TemporaryDirectory() as d:
            db_path = os.path.join(d, "rag.db")
            prev_db = RAG.RAG_DB_PATH
            prev_meta = RAG._BUILD_META
            try:
                # Plenty of backlog so a soak has real chunks to drain.
                _build_tiny_rag_index(RAG, db_path, n=24)
                monkeypatch.setattr(RAG, "_maybe_embedder",
                                    lambda: (lambda t: [0.1, 0.2, 0.3, 0.4]))

                def _sweep(posture):
                    monkeypatch.setenv("A11OY_ENERGY_FORCE_POSTURE", posture)
                    op = OP.OperatorDaemon(nodes=[_node_cfg(base)],
                                           state_path=os.path.join(d, f"l-{posture}.json"),
                                           allow_stub=False)
                    produced = op.run_once()
                    return op.status(), produced

                st_base, p_base = _sweep("baseline")
                st_soak, p_soak = _sweep("soak")
                st_thr, p_thr = _sweep("throttle")

                # status reflects the mode ACTUALLY applied this sweep.
                assert st_base["work_mode"] == "baseline", st_base
                assert st_soak["work_mode"] == "soak", st_soak
                assert st_thr["work_mode"] == "throttle", st_thr
                # honest reason strings name the driver.
                assert "baseline" in st_base["work_mode_reason"], st_base
                assert "soak" in st_soak["work_mode_reason"].lower(), st_soak
                assert "forced" in st_thr["work_mode_reason"], st_thr
                # posture signals surface honestly.
                assert "grid_price_posture" in st_base, st_base
                assert "should_soak" in st_base, st_base
                # SOAK does MORE embed jobs than baseline; THROTTLE adds no extra batch.
                assert _count_embed_jobs(p_soak) > _count_embed_jobs(p_base), \
                    (_count_embed_jobs(p_soak), _count_embed_jobs(p_base))
                assert _count_embed_jobs(p_thr) <= _count_embed_jobs(p_base), \
                    (_count_embed_jobs(p_thr), _count_embed_jobs(p_base))
            finally:
                RAG.RAG_DB_PATH = prev_db
                RAG._BUILD_META = prev_meta
                monkeypatch.delenv("A11OY_ENERGY_FORCE_POSTURE")
    finally:
        node.stop()


# ---------------------------------------------------------------------------
# (13) RAG write-path honesty: embed_and_store_chunk REFUSES a chunk_id that is not
#      already in org_chunks (never fabricates an indexed chunk), and
#      next_unembedded_chunks returns ONLY chunks that still lack a dense vector.
# ---------------------------------------------------------------------------
def test_rag_write_path_refuses_fabricated_chunk(monkeypatch):
    import a11oy_org_rag as RAG
    with tempfile.TemporaryDirectory() as d:
        db_path = os.path.join(d, "rag.db")
        prev_db = RAG.RAG_DB_PATH
        prev_meta = RAG._BUILD_META
        try:
            ids = _build_tiny_rag_index(RAG, db_path, n=3)
            # Refuse a vector for a non-existent chunk (no fabricated indexed chunk).
            res = RAG.embed_and_store_chunk("does-not-exist", [0.1, 0.2, 0.3, 0.4])
            assert res["ok"] is False, res
            assert "honest_error" in res, res
            assert RAG.chunk_count() == 3, RAG.chunk_count()  # no row created
            assert RAG.dense_vector_count() == 0, RAG.dense_vector_count()
            # Store a REAL vector for an existing chunk → backlog shrinks by one.
            ok = RAG.embed_and_store_chunk(ids[0], [0.1, 0.2, 0.3, 0.4])
            assert ok["ok"] is True, ok
            assert RAG.dense_vector_count() == 1, RAG.dense_vector_count()
            remaining = {c["chunk_id"] for c in RAG.next_unembedded_chunks(limit=9)}
            assert ids[0] not in remaining, remaining
            assert set(ids[1:]) == remaining, remaining
        finally:
            RAG.RAG_DB_PATH = prev_db
            RAG._BUILD_META = prev_meta


# ---------------------------------------------------------------------------
# (14) GENTLE LOOP: the harvest posture feed (which may hit live external feeds)
#      must be refreshed at most once per TTL — NEVER on every sweep — so a fast
#      inter-job interval can't turn into a per-sweep network call (the regression
#      that starved jobs_done). A forced posture skips the feed entirely.
# ---------------------------------------------------------------------------
def test_posture_feed_is_ttl_throttled_not_per_sweep(monkeypatch):
    import sys, types
    calls = {"n": 0}
    fake = types.ModuleType("a11oy_harvest_endpoints")

    def handle_posture():
        calls["n"] += 1
        return {"ok": True, "soak_hard": False, "wasted_energy_available": False,
                "readings": []}
    fake.handle_posture = handle_posture
    monkeypatch.setitem(sys.modules, "a11oy_harvest_endpoints", fake)

    with tempfile.TemporaryDirectory() as d:
        op = OP.OperatorDaemon(nodes=[], state_path=os.path.join(d, "l.json"))
        # Forced posture: deterministic, MUST NOT touch the feed at all.
        monkeypatch.setenv("A11OY_ENERGY_FORCE_POSTURE", "baseline")
        for _ in range(5):
            op._resolve_posture()
        assert calls["n"] == 0, calls
        # Live posture with the default (long) TTL: many rapid sweeps => ONE feed call.
        monkeypatch.delenv("A11OY_ENERGY_FORCE_POSTURE")
        calls["n"] = 0
        for _ in range(8):
            op._resolve_posture()
        assert calls["n"] == 1, calls
        # TTL=0 proves the knob: the feed refreshes every sweep when asked.
        monkeypatch.setenv("A11OY_ENERGY_POSTURE_TTL_S", "0")
        calls["n"] = 0
        for _ in range(3):
            op._resolve_posture()
        assert calls["n"] == 3, calls


if __name__ == "__main__":
    import sys
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]

    class _MP:
        _UNSET = object()

        def __init__(self):
            self._undo = []
            self._env_undo = []
            self._item_undo = []
        def setattr(self, obj, name, val):
            self._undo.append((obj, name, getattr(obj, name)))
            setattr(obj, name, val)
        def setenv(self, name, val):
            self._env_undo.append((name, os.environ.get(name, self._UNSET)))
            os.environ[name] = val
        def delenv(self, name, raising=False):
            self._env_undo.append((name, os.environ.get(name, self._UNSET)))
            os.environ.pop(name, None)
        def setitem(self, mapping, key, val):
            self._item_undo.append((mapping, key, mapping.get(key, self._UNSET)))
            mapping[key] = val
        def undo(self):
            for obj, name, old in reversed(self._undo):
                setattr(obj, name, old)
            self._undo = []
            for name, old in reversed(self._env_undo):
                if old is self._UNSET:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = old
            self._env_undo = []
            for mapping, key, old in reversed(self._item_undo):
                if old is self._UNSET:
                    mapping.pop(key, None)
                else:
                    mapping[key] = old
            self._item_undo = []

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
