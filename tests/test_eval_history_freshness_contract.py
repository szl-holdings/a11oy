"""Regression contracts for honest eval-arena history freshness.

These tests isolate the pure freshness helper from the very large service
module, so they do not start servers, schedulers, subprocesses, or network I/O.
"""

from __future__ import annotations

import ast
import collections
import json
import sys
import threading
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVE = ROOT / "serve.py"
PROBE = ROOT / "tools" / "readiness-harness" / "probe_runner.mjs"
CONSOLE = ROOT / "pages" / "console.html"


def _freshness_function():
    tree = ast.parse(SERVE.read_text(encoding="utf-8"))
    node = next(
        item
        for item in tree.body
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
        and item.name == "_a11oy_eval_hist_freshness"
    )
    namespace = {
        "_A11OY_EVAL_HIST": collections.deque(maxlen=50),
        "_A11OY_EVAL_HIST_LOCK": threading.Lock(),
        "_A11OY_EVAL_HIST_SLA_SEC": 86400,
        "_A11OY_EVAL_HIST_MAX_FUTURE_SKEW_SEC": 300,
    }
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(SERVE), "exec"), namespace)
    return namespace["_a11oy_eval_hist_freshness"], namespace


def test_history_without_latest_run_fails_closed():
    freshness, _ = _freshness_function()
    state = freshness(now=datetime(2026, 8, 11, tzinfo=timezone.utc))
    assert state["status"] == "unavailable"
    assert state["latest_run_at"] is None
    assert state["age_s"] is None


def test_history_reports_live_and_stale_from_latest_run_clock():
    freshness, namespace = _freshness_function()
    now = datetime(2026, 8, 11, 12, tzinfo=timezone.utc)
    namespace["_A11OY_EVAL_HIST"].append(
        {"timestamp": (now - timedelta(hours=2)).isoformat(), "mode": "live"}
    )
    assert freshness(now=now)["status"] == "live"

    namespace["_A11OY_EVAL_HIST"].append(
        {"timestamp": (now - timedelta(hours=25)).isoformat(), "mode": "live"}
    )
    state = freshness(now=now)
    assert state["status"] == "stale"
    assert state["age_s"] == 25 * 3600


def test_history_invalid_timestamp_fails_closed():
    freshness, namespace = _freshness_function()
    namespace["_A11OY_EVAL_HIST"].append(
        {"timestamp": "not-a-clock", "mode": "live"}
    )
    state = freshness(now=datetime(2026, 8, 11, tzinfo=timezone.utc))
    assert state["status"] == "unavailable"
    assert "invalid latest run timestamp" in state["reason"]


def test_history_non_live_and_future_records_fail_closed():
    freshness, namespace = _freshness_function()
    now = datetime(2026, 8, 11, 12, tzinfo=timezone.utc)
    namespace["_A11OY_EVAL_HIST"].append(
        {"timestamp": now.isoformat(), "mode": "recorded"}
    )
    assert freshness(now=now)["status"] == "unavailable"

    namespace["_A11OY_EVAL_HIST"].append(
        {"timestamp": (now + timedelta(minutes=6)).isoformat(), "mode": "live"}
    )
    state = freshness(now=now)
    assert state["status"] == "unavailable"
    assert "future clock skew" in state["reason"]


def test_corrupt_persisted_records_are_disclosed(tmp_path):
    tree = ast.parse(SERVE.read_text(encoding="utf-8"))
    node = next(
        item
        for item in tree.body
        if isinstance(item, ast.FunctionDef)
        and item.name == "_a11oy_eval_hist_load"
    )
    history_path = tmp_path / "history.ndjson"
    history_path.write_text(
        json.dumps({"timestamp": "2026-08-11T00:00:00+00:00", "mode": "live"})
        + "\n{not-json}\n42\n"
        + json.dumps({"timestamp": "2026-08-11T00:00:00+00:00", "mode": "recorded"})
        + "\n",
        encoding="utf-8",
    )
    namespace = {
        "_A11OY_EVAL_HIST_PATH": history_path,
        "_A11OY_EVAL_HIST_MAX": 50,
        "_A11OY_EVAL_HIST": collections.deque(maxlen=50),
        "_A11OY_EVAL_HIST_STORAGE_LAST_ERROR": None,
        "_aeh_datetime": datetime,
        "json": json,
    }
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(SERVE), "exec"), namespace)
    namespace["_a11oy_eval_hist_load"]()
    assert len(namespace["_A11OY_EVAL_HIST"]) == 1
    assert namespace["_A11OY_EVAL_HIST_STORAGE_LAST_ERROR"] == (
        "history load skipped 3 invalid record(s)"
    )


def test_scheduler_can_replace_a_stopped_but_draining_generation():
    tree = ast.parse(SERVE.read_text(encoding="utf-8"))
    nodes = [
        item
        for item in tree.body
        if isinstance(item, ast.FunctionDef)
        and item.name in {"_a11oy_eval_autorun_start", "_a11oy_eval_autorun_stop"}
    ]
    release = threading.Event()
    worker_started = threading.Event()
    captured_events = []

    class ShortJoinThread(threading.Thread):
        def join(self, timeout=None):
            return super().join(timeout=0.01)

    def draining_worker(stop_event):
        captured_events.append(stop_event)
        worker_started.set()
        release.wait()

    namespace = {
        "_A11OY_EVAL_AUTORUN_STARTED": False,
        "_A11OY_EVAL_AUTORUN_THREAD": None,
        "_A11OY_EVAL_AUTORUN_STOP": threading.Event(),
        "_A11OY_EVAL_AUTORUN_LOCK": threading.Lock(),
        "_a11oy_eval_autorun_interval": lambda: 1,
        "_a11oy_eval_autorun_loop": draining_worker,
        "_aeh_threading": types.SimpleNamespace(
            Event=threading.Event,
            Thread=ShortJoinThread,
        ),
        "sys": sys,
    }
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SERVE), "exec"), namespace)
    start = namespace["_a11oy_eval_autorun_start"]
    stop = namespace["_a11oy_eval_autorun_stop"]

    start()
    assert worker_started.wait(1)
    first_thread = namespace["_A11OY_EVAL_AUTORUN_THREAD"]
    first_event = namespace["_A11OY_EVAL_AUTORUN_STOP"]
    stop()
    assert first_thread.is_alive()
    assert first_event.is_set()

    worker_started.clear()
    start()
    assert worker_started.wait(1)
    second_thread = namespace["_A11OY_EVAL_AUTORUN_THREAD"]
    assert second_thread is not first_thread
    assert namespace["_A11OY_EVAL_AUTORUN_STOP"] is not first_event

    release.set()
    first_thread.join(1)
    second_thread.join(1)
    stop()


def test_scheduler_is_lifecycle_owned_and_six_hour_default():
    source = SERVE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    import_time_calls = [
        node
        for node in tree.body
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "_a11oy_eval_autorun_start"
    ]
    assert import_time_calls == []
    assert 'A11OY_EVAL_AUTORUN_INTERVAL_SEC", "21600"' in source
    assert "refresh_interval = min(" in source
    assert "_a11oy_eval_autorun_start()" in source
    assert "_a11oy_eval_autorun_stop()" in source
    assert "stop_event.wait" in source


def test_history_endpoint_discloses_freshness_and_storage_errors():
    source = SERVE.read_text(encoding="utf-8")
    assert '"latest_run_at": freshness.get("latest_run_at")' in source
    assert '"latest_run_age_s": freshness.get("age_s")' in source
    assert '"freshness": freshness' in source
    assert '"storage": _a11oy_eval_hist_storage()' in source
    assert "os.replace(_tmp_path, _A11OY_EVAL_HIST_PATH)" in source
    assert "history persist failed" in source


def test_rerun_mutation_is_post_only_and_console_uses_post():
    source = SERVE.read_text(encoding="utf-8")
    assert '@app.post("/api/a11oy/v1/eval-arena/rerun")' in source
    assert "await anyio.to_thread.run_sync(" in source
    assert "_a11oy_eval_run_live_serialized," in source
    assert '@app.get("/api/a11oy/v1/eval-arena/rerun", include_in_schema=False)' in source
    assert "a11oy_eval_arena_rerun_get_not_allowed_v2" in source
    assert 'headers={"Allow": "POST"}' in source
    assert "_a11oy_eval_authorise" in source
    assert 'required_scopes=("eval:run",)' in source
    assert "_a11oy_eval_rerun_claim" in source
    assert 'status_code=429' in source
    assert 'rec["state"] = "unavailable"' in source
    assert 'return JSONResponse(rec, status_code=503)' in source
    assert '"triggered_by": actor' in source
    console = CONSOLE.read_text(encoding="utf-8")
    assert 'id="ar-gov-token" type="password"' in console
    assert "headers:{Authorization:'Bearer '+token}" in console
    assert "var rr=await fetch(url,requestOptions)" in console
    assert "window._szlFetch(url,requestOptions)" not in console


def test_readiness_requires_explicit_latest_run_timestamp():
    source = PROBE.read_text(encoding="utf-8")
    assert 'path === "/api/a11oy/v1/eval-arena/history"' in source
    assert "toDate(body?.latest_run_at)" in source
    assert 'lies.push("latest eval run timestamp missing")' in source
    assert "latest eval run timestamp exceeds allowed future clock skew" in source
    assert "declaredFreshness !== \"live\"" in source
