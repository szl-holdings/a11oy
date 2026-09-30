# SPDX-License-Identifier: Apache-2.0
"""Offline pin extraction for the Lyte Space revision probe. No network."""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "scripts" / "probe_lyte_space_revision.py"
PUBLISHER = ROOT / "scripts" / "hf_publish_lyte_enterprise.py"


def _load_probe():
    spec = importlib.util.spec_from_file_location("probe_lyte_space_revision", PROBE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_probe_reads_publisher_pin() -> None:
    module = _load_probe()
    pin = module.publisher_pin()
    text = PUBLISHER.read_text(encoding="utf-8")
    assert f'SOURCE_REVISION = "{pin}"' in text
    assert len(pin) == 40
