#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""The serving lifecycle must finish storage release before Uvicorn exits."""
import ast
import asyncio
import os
from pathlib import Path
import signal
import subprocess
import sys
import textwrap
import threading
from types import SimpleNamespace

import pytest
import a11oy_state_store as ss


def _serve_shutdown(**overrides):
    """Run the real shutdown hook without importing the full serving estate."""
    async def stop_signing_sampler():
        await asyncio.sleep(0)

    source = Path(__file__).resolve().parents[1] / "serve.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    hook = next(node for node in tree.body
                if isinstance(node, ast.AsyncFunctionDef) and node.name == "shutdown")
    hook.decorator_list = []
    scope = {
        "asyncio": asyncio, "sys": sys, "_rd_artifact": None,
        "_stop_a11oy_signing_state": stop_signing_sampler,
        "_a11oy_eval_autorun_stop": lambda: None,
        "_node_proc": None, "_http_client": None,
        **overrides,
    }
    exec(compile(ast.Module(body=[hook], type_ignores=[]), str(source), "exec"), scope)
    return scope["shutdown"]


def test_asgi_shutdown_awaits_state_release_outside_event_loop(monkeypatch):
    calls = []
    loop_thread = threading.get_ident()
    monkeypatch.setattr(ss, "shutdown", lambda: calls.append(("release", threading.get_ident())))
    async def stop_signing_sampler():
        calls.append(("signer-stop-start", threading.get_ident()))
        await asyncio.sleep(0)
        calls.append(("signer-stop-finished", threading.get_ident()))

    hook = _serve_shutdown(
        _stop_a11oy_signing_state=stop_signing_sampler,
        _a11oy_eval_autorun_stop=lambda: calls.append(("stop", loop_thread)))
    asyncio.run(hook())
    assert [name for name, _ in calls] == [
        "signer-stop-start", "signer-stop-finished", "stop", "release"]
    assert calls[0][1] == calls[1][1] == loop_thread
    assert calls[-1][1] != loop_thread


def test_other_shutdown_failure_cannot_skip_state_release(monkeypatch):
    calls = []

    def fail_stop():
        raise RuntimeError("reader stop failed")

    monkeypatch.setattr(ss, "shutdown", lambda: calls.append("release"))
    hook = _serve_shutdown(_rd_artifact=SimpleNamespace(reader=SimpleNamespace(stop=fail_stop)))
    with pytest.raises(RuntimeError, match="reader stop failed"):
        asyncio.run(hook())
    assert calls == ["release"]


def test_signing_sampler_shutdown_failure_cannot_skip_state_release(monkeypatch):
    calls = []

    async def fail_sampler_stop():
        await asyncio.sleep(0)
        raise RuntimeError("signing sampler stop failed")

    monkeypatch.setattr(ss, "shutdown", lambda: calls.append("release"))
    hook = _serve_shutdown(_stop_a11oy_signing_state=fail_sampler_stop)
    with pytest.raises(RuntimeError, match="signing sampler stop failed"):
        asyncio.run(hook())
    assert calls == ["release"]


@pytest.mark.skipif(os.name != "posix", reason="actual POSIX SIGTERM process semantics")
def test_asgi_state_release_precedes_uvicorn_sigterm_reraise():
    # The primary-runtime CI job installs the exact Docker dependency closure.
    source = Path(__file__).resolve().parents[1] / "serve.py"
    probe = textwrap.dedent('''
        import ast, asyncio, os, signal, sys, types
        from pathlib import Path
        from fastapi import FastAPI
        import uvicorn

        app = FastAPI()
        source = Path(sys.argv[1])
        hook = next(node for node in ast.parse(source.read_text(encoding="utf-8")).body
                    if isinstance(node, ast.AsyncFunctionDef) and node.name == "shutdown")
        async def stop_signing_sampler():
            await asyncio.sleep(0)
            print("SIGNER_STOP_FINISHED", flush=True)
        scope = {"app": app, "asyncio": asyncio, "sys": sys,
                 "_rd_artifact": None, "_a11oy_eval_autorun_stop": lambda: None,
                 "_stop_a11oy_signing_state": stop_signing_sampler,
                 "_node_proc": None, "_http_client": None}
        def release():
            print("STATE_RELEASE_FINISHED", flush=True)
        sys.modules["a11oy_state_store"] = types.SimpleNamespace(shutdown=release)
        exec(compile(ast.Module(body=[hook], type_ignores=[]), str(source), "exec"), scope)

        @app.on_event("startup")
        async def schedule_stop():
            async def stop():
                await asyncio.sleep(0.05)
                os.kill(os.getpid(), signal.SIGTERM)
            asyncio.create_task(stop())

        signal.signal(signal.SIGTERM, signal.SIG_DFL)
        try:
            uvicorn.run(app, host="127.0.0.1", port=0, lifespan="on", log_level="error")
        finally:
            print("OUTER_FINALLY_RAN", flush=True)
    ''')
    result = subprocess.run(
        [sys.executable, "-B", "-c", probe, str(source)],
        capture_output=True, text=True, timeout=15, check=False,
    )
    assert result.returncode == -signal.SIGTERM, (result.returncode, result.stdout, result.stderr)
    assert result.stdout.splitlines() == [
        "SIGNER_STOP_FINISHED", "STATE_RELEASE_FINISHED"], result.stderr


