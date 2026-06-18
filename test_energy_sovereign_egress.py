# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""test_energy_sovereign_egress — the served energy/metrics panel never leaks the
private joule-meter address.

The sovereign joule-meter is scraped INTERNALLY from a private tailnet address
(100.x CGNAT + :9471). The JSON returned by /api/a11oy/v1/energy/metrics renders
client-side on a public HF Space, so the raw IP/port must never appear in the
served `exporter` field (Doctrine v11: hide private addressing, change no
true/false fact — same leak class as the compute-pool egress scrub).

Pure stdlib, fully OFFLINE (no network: the meter is unreachable in the sandbox,
exercising the honest fallback; we also exercise the live-shaped path via a
monkeypatched meter so BOTH served dicts are checked).

Run:
    python3 -m pytest test_energy_sovereign_egress.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import szl_energy_sovereign as es  # noqa: E402

_PRIVATE_TOKENS = ("100.96.129.45", ":9471", "167.233.50.75", ":11434")


def _assert_no_private_addr(panel: dict) -> None:
    blob = json.dumps(panel)
    for tok in _PRIVATE_TOKENS:
        assert tok not in blob, f"served metrics panel leaked private token {tok!r}: {blob}"


def test_metrics_panel_unreachable_fallback_has_no_private_addr():
    # In the sandbox the real tailnet meter is unreachable -> honest fallback dict.
    panel = es._metrics_panel()
    _assert_no_private_addr(panel)
    # Honest posture preserved: it is the unreachable/ROADMAP fallback, not faked.
    assert panel["metric"] == "energy_metrics"
    assert panel["label"] in ("ROADMAP", "MEASURED")
    # The exporter field is a safe label, not a URL.
    assert panel["exporter"] == es._JOULE_METER_LABEL
    assert "http://" not in panel["exporter"]


def test_metrics_panel_live_shape_has_no_private_addr(monkeypatch):
    # Drive the LIVE branch with a synthetic meter payload (no network) so the
    # fully-populated served dict is also checked for address leaks.
    fake_meter = {
        "engines": [{
            "engine": "vllm-sovereign", "power_source": "nvml",
            "joules": 1234.5,
            "gpus": [{
                "gpu": 0, "name": "RTX 5050", "power_w": 42.0, "live": True,
                "joules": 1234.5, "util": 55, "temp_c": 61, "mem_used_mb": 8192,
                "samples": 10,
            }],
        }],
        "totals": {"joules": 1234.5, "kwh": 0.000343, "eur_per_mwh": 80.0,
                   "eur_cost": 0.0000274},
        "generated_at": "2026-06-18T00:00:00+00:00",
    }
    monkeypatch.setattr(es, "_joule_meter", lambda *a, **k: fake_meter)
    panel = es._metrics_panel()
    _assert_no_private_addr(panel)
    # The real measured numbers still flow through unchanged (no fact hidden).
    assert panel["label"] == "MEASURED"
    assert panel["joules_total"] == 1234.5
    assert panel["power_w"] == 42.0
    assert panel["exporter"] == es._JOULE_METER_LABEL


def test_internal_meter_url_is_still_the_real_private_address():
    # Doctrine: we hide the address at EGRESS only. The box must still probe the
    # real tailnet meter internally — the constant is unchanged.
    assert es._JOULE_METER_URL.startswith("http://100.")
    assert es._JOULE_METER_URL != es._JOULE_METER_LABEL


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
