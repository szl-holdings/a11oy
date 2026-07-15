# SPDX-License-Identifier: Apache-2.0
"""Fail-closed host-isolation contract for the governed Code engine."""

from __future__ import annotations

import a11oy_code_engine as engine


def test_missing_isolation_prerequisites_refuse_without_subprocess(monkeypatch):
    called = False

    def forbidden_run(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("no subprocess may start without fixed isolation")

    monkeypatch.setattr(engine, "resource", None)
    monkeypatch.setattr(engine, "_UNSHARE", None)
    monkeypatch.setattr(engine.subprocess, "run", forbidden_run)

    result = engine._sandbox_exec("print('must not execute')")

    assert called is False
    assert result["ok"] is False
    assert result["execution_state"] == "UNAVAILABLE"
    assert result["isolation"] == "UNAVAILABLE — no code executed"
    assert "POSIX_RESOURCE_LIMITS" in result["capability"]["missing"]
    assert "UNSHARE_NET_NAMESPACE" in result["capability"]["missing"]


def test_windows_import_path_reports_unavailable_without_overclaim():
    capability = engine.sandbox_capability()

    if engine.os.name != "posix":
        assert capability["state"] == "UNAVAILABLE"
        assert "POSIX_HOST" in capability["missing"]
        assert capability["network_namespace_command"] is None
