# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Actual daemon transitions retain live workers and serialize control intent."""
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import szl_energy_operator as operator


@pytest.fixture
def op(tmp_path, monkeypatch):
    daemon = operator.OperatorDaemon(nodes=[], state_path=str(tmp_path / "state.json"),
                                     job_interval_s=0.1, allow_stub=False)
    monkeypatch.setattr(daemon, "any_lung_reachable", lambda: True)
    return daemon


def fake_workers(monkeypatch):
    created = []

    class Worker:
        def __init__(self, **kwargs):
            self.alive = False
            created.append(self)
        def start(self): self.alive = True
        def is_alive(self): return self.alive
        def join(self, timeout=None): self.alive = False

    monkeypatch.setattr(operator, "threading", SimpleNamespace(
        Thread=Worker, current_thread=threading.current_thread))
    return created


@pytest.mark.parametrize("active_status", ["computing", "computing (STUB)"])
def test_join_timeout_retains_worker_until_exit_and_restart(op, monkeypatch, active_status):
    entered = threading.Event()
    release = threading.Event()

    def sweep():
        with op._lock:
            op._node_status["synthetic-node"] = active_status
        entered.set()
        assert release.wait(5)

    monkeypatch.setattr(op, "run_once", sweep)
    op.start()
    first = op._thread
    try:
        assert entered.wait(2)
        result = op.stop(join_timeout=0.01)
        assert first.is_alive()
        assert op._thread is first
        assert result["running"] is True
        assert result["lifecycle_state"] == "STOPPING"
        assert op.start()["lifecycle_state"] == "STOPPING"
        assert op._thread is first and op._stop.is_set()
        monkeypatch.setattr(operator, "get_operator", lambda: op)
        readiness = operator.readiness()
        assert readiness["ready"] is False and readiness["service_ready"] is False
        assert readiness["state"] == "stopping"
        assert readiness["operator_running"] is True
    finally:
        release.set()
        first.join(timeout=2)
    assert not first.is_alive()
    stopped = op.status()
    assert stopped["lifecycle_state"] == "STOPPED" and stopped["running"] is False
    assert stopped["nodes_computing"] == []
    assert op._node_status["synthetic-node"] == "idle"
    assert op._thread is first  # dead handle remains safe until the next transition
    op.start()
    second = op._thread
    try:
        assert second is not first and op.is_running()
    finally:
        op.stop(join_timeout=2)
    assert not second.is_alive() and op._thread is None


def test_start_cannot_replace_worker_during_stop_cleanup(op, monkeypatch):
    created = fake_workers(monkeypatch)
    entered = threading.Event()
    release = threading.Event()

    class OldWorker:
        alive = True
        def is_alive(self): return self.alive
        def join(self, timeout=None):
            self.alive = False
            entered.set()
            assert release.wait(5)

    old = OldWorker()
    op._thread = old
    with ThreadPoolExecutor(max_workers=1) as pool:
        stopping = pool.submit(op.stop, 0.25)
        try:
            assert entered.wait(2)
            result = op.start()
            assert created == [], "a replacement was started before stop cleanup finished"
            assert op._thread is old
            assert result["lifecycle_state"] == "STOPPING"
        finally:
            release.set()
        assert stopping.result(timeout=2)["lifecycle_state"] == "STOPPED"
    assert op._thread is None


def test_concurrent_starts_share_one_transition_and_probe(op, monkeypatch):
    created = fake_workers(monkeypatch)
    entered = threading.Event()
    release = threading.Event()
    probes = []

    def probe():
        probes.append("probe")
        entered.set()
        assert release.wait(5)
        return True

    monkeypatch.setattr(op, "any_lung_reachable", probe)
    with ThreadPoolExecutor(max_workers=4) as pool:
        leader = pool.submit(op.start)
        try:
            assert entered.wait(2)
            followers = [pool.submit(op.start) for _ in range(3)]
            results = [future.result(timeout=2) for future in followers]
            assert all(value["lifecycle_state"] == "STARTING" for value in results)
            assert probes == ["probe"]
        finally:
            release.set()
        assert leader.result(timeout=2)["lifecycle_state"] == "RUNNING"
    assert len(created) == 1
    assert op.stop()["lifecycle_state"] == "STOPPED"


def test_stop_cancels_pending_start_without_waiting_for_its_probe(op, monkeypatch):
    created = fake_workers(monkeypatch)
    entered = threading.Event()
    release = threading.Event()

    def probe():
        entered.set()
        assert release.wait(5)
        return True

    monkeypatch.setattr(op, "any_lung_reachable", probe)
    with ThreadPoolExecutor(max_workers=1) as pool:
        starting = pool.submit(op.start)
        try:
            assert entered.wait(2)
            assert op.stop(join_timeout=0)["lifecycle_state"] == "STOPPING"
        finally:
            release.set()
        result = starting.result(timeout=2)
    assert result["started"] is False
    assert result["reason"] == "start_cancelled_by_stop"
    assert result["lifecycle_state"] == "STOPPED"
    assert created == [] and not op.is_running()
    assert op.start()["lifecycle_state"] == "RUNNING"
    op.stop()


def test_concurrent_stops_share_join_and_cleanup(op):
    entered = threading.Event()
    release = threading.Event()
    joins = []

    class Worker:
        alive = True
        def is_alive(self): return self.alive
        def join(self, timeout=None):
            joins.append(timeout)
            entered.set()
            assert release.wait(5)
            self.alive = False

    op._thread = Worker()
    with ThreadPoolExecutor(max_workers=2) as pool:
        leader = pool.submit(op.stop, 0.25)
        try:
            assert entered.wait(2)
            follower = pool.submit(op.stop, 0.01)
            assert follower.result(timeout=2)["lifecycle_state"] == "STOPPING"
            assert joins == [0.25]
        finally:
            release.set()
        assert leader.result(timeout=2)["lifecycle_state"] == "STOPPED"
    assert op._thread is None


def test_probe_failure_clears_start_transition_for_retry(op, monkeypatch):
    created = fake_workers(monkeypatch)
    def fail(): raise RuntimeError("synthetic probe error")
    monkeypatch.setattr(op, "any_lung_reachable", fail)
    with pytest.raises(RuntimeError, match="synthetic probe error"):
        op.start()
    assert op.status()["lifecycle_state"] == "STOPPED"
    monkeypatch.setattr(op, "any_lung_reachable", lambda: True)
    assert op.start()["running"] is True
    assert len(created) == 1
    op.stop()


@pytest.mark.parametrize("action", ["start", "stop"])
def test_control_wait_does_not_block_unrelated_async_route(op, monkeypatch, action):
    app = FastAPI()
    entered = threading.Event()
    release = threading.Event()

    @app.get("/audit/ping")
    async def ping():
        return {"ok": True}

    def probe():
        entered.set()
        assert release.wait(5)
        return False

    if action == "start":
        monkeypatch.setattr(op, "any_lung_reachable", probe)
    else:
        monkeypatch.setattr(op, "run_once", lambda: (entered.set(), release.wait(5)))
        op.start()
        assert entered.wait(2)
    monkeypatch.setattr(operator, "get_operator", lambda: op)
    operator.register(app)
    with TestClient(app) as client, ThreadPoolExecutor(max_workers=2) as pool:
        control = pool.submit(client.post, "/api/a11oy/v1/energy/operator/" + action)
        try:
            assert (entered.wait(2) if action == "start" else op._stop.wait(2))
            other = pool.submit(client.get, "/audit/ping")
            assert other.result(timeout=2).json() == {"ok": True}
            assert not control.done()
        finally:
            release.set()
        response = control.result(timeout=3)
    assert response.status_code == 200
    assert response.json()["running"] is False
    assert response.json()["lifecycle_state"] == "STOPPED"
    if action == "start":
        assert response.json()["reason"] == "no_lung_reachable"


@pytest.mark.parametrize("prefix", ["/api/a11oy/v1", "/v1"])
@pytest.mark.parametrize("action", ["start", "stop"])
def test_existing_operator_gate_still_precedes_control_handlers(op, monkeypatch, prefix, action):
    import szl_operator_auth as auth

    app = FastAPI()
    monkeypatch.setenv(auth.OPERATOR_KEY_ENV, "synthetic-lifecycle-test-key")
    monkeypatch.setattr(operator, "get_operator", lambda: op)
    monkeypatch.setattr(op, "any_lung_reachable", lambda: False)
    calls = []
    original = getattr(op, action)

    def counted():
        calls.append(action)
        return original()

    monkeypatch.setattr(op, action, counted)
    auth.install_gate(app)
    operator.register(app)
    with TestClient(app) as client:
        for headers in ({}, {"Authorization": "Bearer wrong-test-key"}):
            denied = client.post(prefix + "/energy/operator/" + action, headers=headers,
                                 json={"two_person_attested": True})
            assert denied.status_code == 401
            assert denied.json()["status"] == "BLOCKED"
            assert calls == []
        allowed = client.post(prefix + "/energy/operator/" + action,
                              headers={"Authorization": "Bearer synthetic-lifecycle-test-key"})
    assert allowed.status_code == 200 and calls == [action]
    assert allowed.json()["lifecycle_state"] == "STOPPED"


def test_thread_start_failure_does_not_leave_an_owned_or_pending_worker(op, monkeypatch):
    class FailedWorker:
        def __init__(self, **kwargs): pass
        def start(self): raise RuntimeError("synthetic thread creation failure")
        def is_alive(self): return False

    monkeypatch.setattr(operator, "threading", SimpleNamespace(
        Thread=FailedWorker, current_thread=threading.current_thread))
    with pytest.raises(RuntimeError, match="synthetic thread creation failure"):
        op.start()
    assert op._thread is None
    assert op.status()["lifecycle_state"] == "STOPPED"
    created = fake_workers(monkeypatch)
    assert op.start()["lifecycle_state"] == "RUNNING"
    assert len(created) == 1
    op.stop()


def test_join_error_releases_transition_and_allows_stop_retry(op):
    class Worker:
        alive = True
        attempts = 0
        def is_alive(self): return self.alive
        def join(self, timeout=None):
            self.attempts += 1
            if self.attempts == 1:
                raise RuntimeError("synthetic join failure")
            self.alive = False

    worker = Worker()
    op._thread = worker
    with pytest.raises(RuntimeError, match="synthetic join failure"):
        op.stop(join_timeout=0)
    assert op._thread is worker
    assert op.status()["lifecycle_state"] == "STOPPING"
    assert op.stop(join_timeout=0)["lifecycle_state"] == "STOPPED"
    assert worker.attempts == 2 and op._thread is None


def test_worker_can_request_stop_without_joining_itself(op, monkeypatch):
    results = []
    called = threading.Event()

    def sweep():
        results.append(op.stop(join_timeout=0))
        called.set()

    monkeypatch.setattr(op, "run_once", sweep)
    op.start()
    worker = op._thread
    try:
        assert called.wait(2)
    finally:
        op._stop.set()
        worker.join(timeout=2)
    assert not worker.is_alive()
    assert results[0]["lifecycle_state"] == "STOPPING"
    assert op.stop(join_timeout=0)["lifecycle_state"] == "STOPPED"


def test_running_read_retains_one_worker_reference_during_cleanup():
    worker = SimpleNamespace(is_alive=lambda: True)

    class ConcurrentCleanup:
        current = worker
        @property
        def _thread(self):
            observed = self.current
            self.current = None  # cleanup after the reader captures the reference
            return observed

    assert operator.OperatorDaemon.is_running(ConcurrentCleanup()) is True


def test_readiness_keeps_stop_intent_when_worker_exits_between_observations(op, monkeypatch):
    entered = threading.Event()
    release = threading.Event()

    def sweep():
        entered.set()
        assert release.wait(5)

    monkeypatch.setattr(op, "run_once", sweep)
    op.start()
    worker = op._thread
    try:
        assert entered.wait(2)
        assert op.stop(join_timeout=0.01)["lifecycle_state"] == "STOPPING"
        observed_running = op.is_running
        observed_lifecycle = op.lifecycle_state

        def running_then_exit():
            running = observed_running()
            release.set()
            return running

        def lifecycle_after_exit():
            # The old split-read path calls this outside the status lock, so the
            # worker can finish before the second observation. The fixed path
            # takes both fields in status() and never makes this second read.
            worker.join(timeout=2)
            assert not worker.is_alive()
            return observed_lifecycle()

        monkeypatch.setattr(op, "is_running", running_then_exit)
        monkeypatch.setattr(op, "lifecycle_state", lifecycle_after_exit)
        monkeypatch.setattr(operator, "get_operator", lambda: op)
        result = operator.readiness()
        assert result["ready"] is False and result["service_ready"] is False
        assert result["state"] == "stopping"
    finally:
        release.set()
        worker.join(timeout=2)
    assert not worker.is_alive()


def test_autostart_reports_cancelled_start(op, monkeypatch):
    created = fake_workers(monkeypatch)
    entered = threading.Event()
    release = threading.Event()
    starting = threading.Event()
    original_start = op.start

    def probe():
        # If the boot hook performs an earlier probe, only gate the probe inside
        # the actual start transition so stop invalidates that generation.
        if starting.is_set():
            entered.set()
            assert release.wait(5)
        return True

    def start():
        starting.set()
        return original_start()

    monkeypatch.setenv(operator.A11OY_ENERGY_AUTOSTART_ENV, "1")
    monkeypatch.setattr(operator, "get_operator", lambda: op)
    monkeypatch.setattr(op, "any_lung_reachable", probe)
    monkeypatch.setattr(op, "start", start)
    with ThreadPoolExecutor(max_workers=1) as pool:
        boot = pool.submit(operator.autostart_if_lung_reachable)
        try:
            assert entered.wait(2)
            assert op.stop(join_timeout=0)["lifecycle_state"] == "STOPPING"
        finally:
            release.set()
        result = boot.result(timeout=2)
    assert result == {"autostarted": False, "reason": "start_cancelled_by_stop", "running": False}
    assert created == [] and op.status()["lifecycle_state"] == "STOPPED"


def test_autostart_reports_existing_start_and_stop_transitions(op, monkeypatch):
    created = fake_workers(monkeypatch)
    entered = threading.Event()
    release = threading.Event()

    def probe():
        entered.set()
        assert release.wait(5)
        return True

    monkeypatch.setenv(operator.A11OY_ENERGY_AUTOSTART_ENV, "1")
    monkeypatch.setattr(operator, "get_operator", lambda: op)
    monkeypatch.setattr(op, "any_lung_reachable", probe)
    with ThreadPoolExecutor(max_workers=1) as pool:
        leader = pool.submit(op.start)
        try:
            assert entered.wait(2)
            assert operator.autostart_if_lung_reachable() == {
                "autostarted": False, "reason": "start_in_progress", "running": False}
            op.stop(join_timeout=0)
            assert operator.autostart_if_lung_reachable() == {
                "autostarted": False, "reason": "operator_stopping", "running": False}
        finally:
            release.set()
        assert leader.result(timeout=2)["reason"] == "start_cancelled_by_stop"
    assert created == []
