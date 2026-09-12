# SPDX-License-Identifier: Apache-2.0
"""Installed-module Hub version is not the Dockerfile pin."""
from __future__ import annotations

import sys
import types

from szl_huggingface_hub_version import huggingface_hub_version


def test_unavailable_without_module(monkeypatch):
    monkeypatch.setitem(sys.modules, "huggingface_hub", None)
    assert huggingface_hub_version() == "UNAVAILABLE"


def test_does_not_invent_pin(monkeypatch):
    fake = types.ModuleType("huggingface_hub")
    fake.__version__ = "9.9.9-test"
    monkeypatch.setitem(sys.modules, "huggingface_hub", fake)
    assert huggingface_hub_version() == "9.9.9-test"
    assert huggingface_hub_version() != "1.31.0"
