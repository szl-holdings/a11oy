#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Guard the isolated route-contract invocation, not default-on concurrency.

Synthetic controls neither boot serve nor start the warmer. The unchanged route
suite remains the executable GET/HEAD no-side-effect contract.
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
    assert isolated["env"]["SZL_EVIDENCE_WARM"] == "0"
    assert "SZL_EVIDENCE_WARM_DELAY" not in isolated["env"]
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
    for kind in ("masked-main", "masked-isolated", "global-off", "isolated-on"):
        changed = deepcopy(baseline)
        job, main, isolated = _steps(changed)
        if kind == "masked-main":
            main["run"] += " || true"
        elif kind == "masked-isolated":
            isolated["run"] += " || true"
        elif kind == "global-off":
            job.setdefault("env", {})["SZL_EVIDENCE_WARM"] = "0"
        else:
            isolated["env"]["SZL_EVIDENCE_WARM"] = "1"
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
