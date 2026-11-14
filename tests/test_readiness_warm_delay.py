#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""The readiness layer honours a requested warm-up postponement.

Regression for the lean-health no-effects guard: with SZL_EVIDENCE_WARM_DELAY
set, the import-time readiness build still wrote /tmp/szl_readiness_cache.json
and called api.github.com / huggingface.co inside the guarded window. The
guard itself is unchanged; the readiness layer must stop starting work early.
"""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _fresh(monkeypatch, tmp_path, **env):
    for name in ("SZL_READINESS_WARM_DELAY", "SZL_EVIDENCE_WARM_DELAY"):
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("SZL_READINESS_CACHE", str(tmp_path / "readiness.json"))
    monkeypatch.setenv("SZL_READINESS_WARM", "0")  # never start a real warmer thread here
    spec = importlib.util.spec_from_file_location(
        "szl_readiness_warm_delay_under_test", ROOT / "szl_readiness.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    kicked = []
    monkeypatch.setattr(mod, "_kick_background_build", kicked.append)
    return mod, kicked


def _register(mod):
    from fastapi import FastAPI
    mod.register(FastAPI(), ns="a11oy")


@pytest.mark.parametrize("env", [
    {"SZL_EVIDENCE_WARM_DELAY": "3600"},
    {"SZL_READINESS_WARM_DELAY": "3600"},
])
def test_postponed_warmup_starts_no_build_at_register(monkeypatch, tmp_path, env):
    mod, kicked = _fresh(monkeypatch, tmp_path, **env)
    assert mod._initial_warm_delay() == 3600
    _register(mod)
    assert kicked == []
    assert not (tmp_path / "readiness.json").exists()
    assert not (tmp_path / "readiness.json.tmp").exists()


@pytest.mark.parametrize("env", [{}, {"SZL_EVIDENCE_WARM_DELAY": "not-a-number"}])
def test_default_behaviour_unchanged(monkeypatch, tmp_path, env):
    mod, kicked = _fresh(monkeypatch, tmp_path, **env)
    assert mod._initial_warm_delay() == 0
    _register(mod)
    assert kicked == ["a11oy"]


def test_readiness_delay_takes_precedence(monkeypatch, tmp_path):
    mod, _ = _fresh(monkeypatch, tmp_path, SZL_READINESS_WARM_DELAY="0",
                    SZL_EVIDENCE_WARM_DELAY="3600")
    assert mod._initial_warm_delay() == 0


def test_warm_loop_first_sleep_honours_delay(monkeypatch, tmp_path):
    mod, _ = _fresh(monkeypatch, tmp_path, SZL_EVIDENCE_WARM_DELAY="3600")
    sleeps = []

    class Stop(Exception):
        pass

    def fake_sleep(seconds):
        sleeps.append(seconds)
        raise Stop

    monkeypatch.setattr(mod.time, "sleep", fake_sleep)
    with pytest.raises(Stop):
        mod._warm_loop()
    assert sleeps == [3600.0]
