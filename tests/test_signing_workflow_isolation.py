#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Guard the isolated route-contract invocation without disabling the warmer.

The unchanged route suite remains the executable GET/HEAD no-side-effect
contract. Its process postpones the first cache sweep. A separate test runs
the real cache writer and still rejects request writes on every thread.
"""
import ast
from copy import deepcopy
from pathlib import Path
import shlex
import subprocess
import sys
import threading
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
ROUTE_TEST = "tests/test_signing_state_routes.py"
MAIN_STEP = "Run demo-critical, Frontier Now, and nested-static delivery guards"
ISOLATED_STEP = "Verify signing state route no-write guard in isolation"
ISOLATED_COMMAND = "python -B -m pytest -q -p no:cacheprovider " + ROUTE_TEST


def _workflow():
    return yaml.safe_load((ROOT / ".github/workflows/tests.yml").read_text(encoding="utf-8"))


def _steps(workflow):
    job = workflow["jobs"]["python-demo-critical-routes"]
    main, isolated = ([step for step in job["steps"] if step.get("name") == name]
                      for name in (MAIN_STEP, ISOLATED_STEP))
    assert len(main) == len(isolated) == 1
    return job, main[0], isolated[0]


def _assert_isolation_contract(workflow):
    job, main, isolated = _steps(workflow)
    for scope in (job, main, isolated):
        assert "if" not in scope
        assert "continue-on-error" not in scope
    for scope in (workflow, job, main):
        env = scope.get("env", {})
        assert "SZL_EVIDENCE_WARM" not in env
        assert "SZL_EVIDENCE_WARM_DELAY" not in env
    assert isolated.get("env", {}).get("SZL_EVIDENCE_WARM_DELAY") == "3600"
    assert "SZL_EVIDENCE_WARM" not in isolated.get("env", {})
    assert isolated["run"].strip() == ISOLATED_COMMAND
    command = shlex.split(main["run"])
    assert command[0] == "pytest" and command[-1] == "-q"
    assert all(token.endswith(".py") and "::" not in token for token in command[1:-1])
    assert ROUTE_TEST not in command
    assert "tests/test_signing_workflow_isolation.py" in command


def test_route_contract_runs_mandatorily_in_its_own_process():
    _assert_isolation_contract(_workflow())


def test_isolation_contract_rejects_skip_failure_masks_and_global_opt_out():
    baseline = _workflow()
    for scope_index in range(3):
        for key, value in (("if", False), ("continue-on-error", True)):
            changed = deepcopy(baseline)
            _steps(changed)[scope_index][key] = value
            with pytest.raises(AssertionError):
                _assert_isolation_contract(changed)
    for kind in ("masked-main", "masked-isolated", "global-off", "isolated-disabled", "delay-removed"):
        changed = deepcopy(baseline)
        job, main, isolated = _steps(changed)
        if kind == "masked-main":
            main["run"] += " || true"
        elif kind == "masked-isolated":
            isolated["run"] += " || true"
        elif kind == "global-off":
            job.setdefault("env", {})["SZL_EVIDENCE_WARM"] = "0"
        elif kind == "isolated-disabled":
            isolated["env"]["SZL_EVIDENCE_WARM"] = "0"
        else:
            isolated["env"].pop("SZL_EVIDENCE_WARM_DELAY", None)
        with pytest.raises(AssertionError):
            _assert_isolation_contract(changed)


def test_original_global_guard_rejects_cross_thread_writes_even_when_caught():
    # The child keeps this synthetic hook away from unrelated threads in the
    # combined app-test process; it imports stdlib only and creates no files.
    child = r'''
import ast
import builtins
from pathlib import Path
import sys
import threading
from unittest.mock import Mock, patch

path = Path(sys.argv[1])
tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
test = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
            and node.name == "test_get_head_do_not_load_sign_probe_write_or_refresh")
calls = {ast.dump(node) for node in test.body if isinstance(node, ast.Expr)}
for expression in ('monkeypatch.setattr(builtins, "open", readonly_open)',
                   'forbidden.assert_not_called()'):
    assert ast.dump(ast.parse(expression).body[0]) in calls
guard = next(node for node in test.body if isinstance(node, ast.FunctionDef)
             and node.name == "readonly_open")
module = ast.fix_missing_locations(ast.Module(body=[guard], type_ignores=[]))
for mode in ("w", "wb", "a", "ab", "r+", "w+", "x", "xb"):
    forbidden = Mock(side_effect=AssertionError("synthetic write rejected"))
    real_open = Mock()
    scope = {"forbidden": forbidden, "real_open": real_open}
    exec(compile(module, str(path), "exec"), scope)
    def worker():
        try:
            builtins.open("SYNTHETIC-NO-FILE", mode)
        except Exception:
            pass  # Swallowing an exception must not hide the forbidden call.
    with patch.object(builtins, "open", scope["readonly_open"]):
        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        thread.join(timeout=2)
        assert not thread.is_alive()
    forbidden.assert_called_once_with("SYNTHETIC-NO-FILE", mode)
    real_open.assert_not_called()
'''
    result = subprocess.run([sys.executable, "-I", "-B", "-c", child, str(ROOT / ROUTE_TEST)],
                            capture_output=True, text=True, timeout=15, check=False)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("value,enabled", [(None, True), ("1", True), ("0", False)])
def test_warmer_start_is_default_on_and_idempotent_without_starting_it(value, enabled):
    source = (ROOT / "szl_evidence_research.py").read_text(encoding="utf-8")
    function = next(node for node in ast.parse(source).body
                    if isinstance(node, ast.FunctionDef) and node.name == "_start_warmer")
    workers = []
    def parked_thread(**kwargs):
        worker = threading.Thread(**kwargs)
        worker.start = Mock()  # Never run its target or patch global Thread.start.
        workers.append(worker)
        return worker
    factory = Mock(side_effect=parked_thread)
    warm_loop = Mock()
    scope = {"_WARM_STARTED": False, "_warm_loop": warm_loop,
             "os": SimpleNamespace(environ={} if value is None else {"SZL_EVIDENCE_WARM": value}),
             "threading": SimpleNamespace(Thread=factory)}
    module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
    exec(compile(module, "<source-start-warmer>", "exec"), scope)
    scope["_start_warmer"]()
    scope["_start_warmer"]()
    assert scope["_WARM_STARTED"] is enabled
    if enabled:
        factory.assert_called_once_with(target=warm_loop, name="szl-evidence-warmer", daemon=True)
        workers[0].start.assert_called_once_with()
    else:
        factory.assert_not_called()
    warm_loop.assert_not_called()


def test_original_route_test_blob_is_unchanged():
    """The process-wide no-write test stays the committed blob."""
    result = subprocess.run(
        ["git", "rev-parse", "HEAD:tests/test_signing_state_routes.py"],
        cwd=ROOT, capture_output=True, text=True, timeout=15, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "363ecc499c9b3845b5e3e7268ea66c42bf8c8248"
    dirty = subprocess.run(
        ["git", "diff", "--", "tests/test_signing_state_routes.py"],
        cwd=ROOT, capture_output=True, text=True, timeout=15, check=False,
    )
    assert dirty.returncode == 0 and dirty.stdout == ""


def test_real_warmer_cache_write_is_visible_and_request_writes_still_fail():
    """Run the real cache writer and keep request writes failing.

    Allowing the warmer thread by itself is not enough: a request frame on that
    same thread, and a write from any other thread, still count as failures.
    """
    child = r'''
import ast
import builtins
import importlib.util
import os
import shutil
import sys
import tempfile
import threading
import traceback
from pathlib import Path
from unittest.mock import Mock, patch

root, route_path = map(Path, sys.argv[1:])
cache_dir = tempfile.mkdtemp(prefix="szl-warm-attr-")
os.environ["SZL_EVIDENCE_CACHE"] = str(Path(cache_dir) / "szl_evidence_cache.json")
os.environ["SZL_EVIDENCE_WARM"] = "1"
os.environ.pop("SZL_EVIDENCE_WARM_DELAY", None)
spec = importlib.util.spec_from_file_location(
    "szl_evidence_research_under_test", root / "szl_evidence_research.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
assert mod._WARM_INITIAL_DELAY == 15

route_tree = ast.parse(route_path.read_text(encoding="utf-8"))
route = next(node for node in route_tree.body if isinstance(node, ast.FunctionDef)
             and node.name == "test_get_head_do_not_load_sign_probe_write_or_refresh")
guard = next(node for node in route.body if isinstance(node, ast.FunctionDef)
             and node.name == "readonly_open")
forbidden = Mock(side_effect=AssertionError("status read attempted a side effect"))
real_open = builtins.open
guard_scope = {"forbidden": forbidden, "real_open": real_open}
guard_module = ast.fix_missing_locations(ast.Module(body=[guard], type_ignores=[]))
exec(compile(guard_module, str(route_path), "exec"), guard_scope)

with patch.object(builtins, "open", guard_scope["readonly_open"]):
    worker = threading.Thread(
        target=lambda: mod._store("synthetic", {"evidence_class": "SIMULATED"}, "simulated"),
        daemon=True)
    worker.start()
    worker.join(timeout=5)
    assert not worker.is_alive()
assert forbidden.call_count == 1
assert str(forbidden.call_args.args[0]).endswith("szl_evidence_cache.json.tmp")
assert forbidden.call_args.args[1] == "w"
assert not Path(mod._DISK).exists()

allowed = []
rejected = []
warmer_box = {}

def attributing_open(file, mode="r", *args, **kwargs):
    if any(flag in str(mode) for flag in ("w", "a", "+", "x")):
        stack = traceback.extract_stack()
        caller = stack[-2].name
        names = {frame.name for frame in stack}
        request_frames = {"request_induced_write", "_a11oy_signing_status"}
        cache_tmp = mod._DISK + ".tmp"
        warmer_cache_write = (
            threading.current_thread() is warmer_box.get("thread")
            and caller == "_disk_save"
            and str(file) == cache_tmp
            and not request_frames.intersection(names))
        if warmer_cache_write:
            allowed.append(str(file))
            return real_open(file, mode, *args, **kwargs)
        rejected.append((str(file), str(mode), caller))
        raise AssertionError("request write rejected")
    return real_open(file, mode, *args, **kwargs)

def sources_live(sources):
    return []

def papers(query, limit=5):
    mod._store("papers:" + query, {"evidence_class": "SIMULATED", "count": 0}, "simulated")
    try:
        builtins.open("NOT_CACHE", "w")
    except AssertionError:
        pass
    def request_induced_write():
        mod._store("request-key", {"evidence_class": "SIMULATED"}, "simulated")
    request_induced_write()
    return {"mode": "live", "count": 0}

def controlled_sleep(seconds):
    if seconds == mod._WARM_INTERVAL:
        raise SystemExit
    return None

mod._WARM_NS.add("synthetic")
mod._claims_for = lambda ns: [{
    "claim": "synthetic", "arxiv_query": "synthetic-query", "sources": []}]
mod._papers = papers
mod._sources_live = sources_live
mod.time.sleep = controlled_sleep
thread = threading.Thread(target=mod._warm_loop, name="szl-evidence-warmer", daemon=True)
warmer_box["thread"] = thread
try:
    with patch.object(builtins, "open", attributing_open):
        thread.start()
        thread.join(timeout=5)
        assert not thread.is_alive()
        other = threading.Thread(
            target=lambda: builtins.open("OTHER_THREAD", "w"), daemon=True)
        other.start()
        other.join(timeout=2)
        assert not other.is_alive()
    assert allowed == [mod._DISK + ".tmp"]
    assert Path(mod._DISK).is_file() and Path(mod._DISK).stat().st_size > 0
    assert ("NOT_CACHE", "w", "papers") in rejected
    assert (mod._DISK + ".tmp", "w", "_disk_save") in rejected
    assert ("OTHER_THREAD", "w", "<lambda>") in rejected
finally:
    shutil.rmtree(cache_dir, ignore_errors=True)
'''
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", child, str(ROOT), str(ROOT / ROUTE_TEST)],
        capture_output=True, text=True, timeout=20, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
