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
import szl_energy_operator as eo  # noqa: E402

# The full private-addressing ban-list for ANY served energy dict. A re-leak of a
# private IP (100.x), a private :port (:9471/:11434), or a raw tailnet hostname
# (betterwithage / rtx-betterwithage / omen-betterwithage / chaski) is a RED gate —
# these are the exact tokens the CTO found in the live served JSON of the
# /energy/sovereign and /energy/operator/status endpoints.
_PRIVATE_TOKENS = (
    "100.96.129.45", ":9471", "167.233.50.75", ":11434", "100.",
    "betterwithage", "rtx-betterwithage", "omen-betterwithage", "chaski",
)


def _assert_no_private_addr(panel: dict) -> None:
    blob = json.dumps(panel)
    for tok in _PRIVATE_TOKENS:
        assert tok not in blob, f"served energy dict leaked private token {tok!r}: {blob}"


def test_metrics_panel_unreachable_fallback_has_no_private_addr():
    # In the sandbox the real tailnet meter is unreachable -> honest fallback dict.
    panel = es._metrics_panel()
    _assert_no_private_addr(panel)
    # Honest posture preserved: it is the unreachable/ROADMAP fallback, not faked.
    assert panel["metric"] == "energy_metrics"
    assert panel["label"] in ("ROADMAP", "MEASURED")
    # The exporter field is a safe label, not a URL.
    assert panel["exporter"] == es._JOULE_METER_PUBLIC
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
    assert panel["exporter"] == es._JOULE_METER_PUBLIC


def test_internal_meter_url_is_still_the_real_private_address():
    # Doctrine: we hide the address at EGRESS only. The box must still probe the
    # real tailnet meter internally — the constant is unchanged.
    assert es._JOULE_METER_URL.startswith("http://100.")
    assert es._JOULE_METER_URL != es._JOULE_METER_PUBLIC


# ---------------------------------------------------------------------------
# /energy/sovereign — _posture() must never leak the orchestrator's private base_url.
# ---------------------------------------------------------------------------
def test_sovereign_posture_offline_has_no_private_addr():
    # Sandbox: orchestrator/GPU unreachable -> honest not-sovereign posture, no leak.
    posture = es._posture()
    _assert_no_private_addr(posture)
    assert posture["service"] == "energy-sovereign"
    # The honest booleans still flow through (no fact hidden).
    assert posture["sovereign"] in (True, False)
    assert posture["gpu_reachable"] in (True, False)


def test_sovereign_posture_live_local_base_is_scrubbed(monkeypatch):
    # Drive the served posture with a LIVE-shaped sovereign state whose base_url is the
    # real private tailnet endpoint the CTO saw leaking. The served inference_state must
    # carry the public descriptor instead — but keep every honest boolean fact.
    fake_state = {
        "inference": "self-hosted-gpu", "mode": "live", "backend": "generative",
        "sovereign": True, "base_url": "http://betterwithage:11434/v1",
        "gpu": "betterwithage",
    }
    monkeypatch.setattr(es, "_sovereign_state", lambda: fake_state)
    # Keep the panels offline/honest (no metrics network) — gpu_reachable derives from
    # the fake state, so neutralize the prom fetch to stay deterministic.
    monkeypatch.setattr(es, "_fetch_metrics_text", lambda *a, **k: None)
    posture = es._posture()
    _assert_no_private_addr(posture)
    ist = posture["inference_state"]
    # Honest facts preserved, address scrubbed.
    assert ist["sovereign"] is True
    assert ist["inference"] == "self-hosted-gpu"
    assert ist["base_url"] == es._SOVEREIGN_BASE_PUBLIC
    assert "gpu" in ist and ist["gpu"] == es._SOVEREIGN_BASE_PUBLIC


def test_sovereign_public_hf_router_base_passes_through():
    # The HF Router base is public by definition — it must NOT be collapsed away.
    state = {"inference": "hf-router", "mode": "live", "backend": "hf-router",
             "sovereign": False, "base_url": "https://router.huggingface.co/v1"}
    out = es._public_inference_state(state)
    assert out["base_url"] == "https://router.huggingface.co/v1"
    assert out["sovereign"] is False
    _assert_no_private_addr(out)


# ---------------------------------------------------------------------------
# /energy/operator/status — status() must never leak the joule-meter URL, the raw
# exporter_node, the raw node names, or per-job evidence node names.
# ---------------------------------------------------------------------------
def test_operator_status_offline_has_no_private_addr():
    # Fresh operator over the real default nodes (private tailnet hostnames). The
    # served status dict must carry public display names + the public exporter label.
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        op = eo.OperatorDaemon(state_path=os.path.join(d, "ledger.json"))
        st = op.status()
    _assert_no_private_addr(st)
    assert st["service"] == "energy-operator"
    # The exporter is the public label, never the 100.x:9471 URL.
    assert st["exporter"] == eo._JOULE_METER_PUBLIC
    assert "http://" not in st["exporter"]


def test_operator_status_live_shape_has_no_private_addr():
    # Populate the served status with a live-shaped state: real default node names in
    # node_status / by_node, plus a recent job carrying a raw exporter_node in evidence.
    # The served dict must scrub ALL of them while keeping the real numbers intact.
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        op = eo.OperatorDaemon(state_path=os.path.join(d, "ledger.json"))
        # Simulate a sweep result: nodes computing/standby/degraded by raw name.
        op._node_status = {"rtx-betterwithage": "computing",
                           "omen-betterwithage": "standby",
                           "chaski": "DEGRADED"}
        op._state.by_node = {"rtx-betterwithage": {"jobs": 3, "tokens": 120,
                                                   "joules_measured": 45.6}}
        op._last_records = [{
            "node": "rtx-betterwithage", "model": "llama3.1:8b", "kind": "generate",
            "tokens": 40, "wall_s": 1.2, "joules_measured": 15.0,
            "joules_label": "MEASURED",
            "joules_evidence": {"joules_measured_total": 78369.586,
                                "exporter_node": "betterwithage",
                                "exporter_last_seen_ts": 1_000_000.0,
                                "power_w_sample": 200.0},
            "ts": "2026-06-18T00:00:00Z", "seq": 7,
        }]
        st = op.status()
    _assert_no_private_addr(st)
    # Public display names present; real numbers untouched.
    assert "Sovereign GPU 1" in st["nodes_computing"]
    assert "Sovereign GPU 2 (always-on anchor)" in st["nodes_standby"]
    assert "Sovereign GPU 3 (tailnet)" in st["nodes_degraded"]
    bn = st["by_node"]["Sovereign GPU 1"]
    assert bn["jobs"] == 3 and bn["tokens"] == 120 and bn["joules_measured"] == 45.6
    job = st["recent_jobs"][0]
    assert job["node"] == "Sovereign GPU 1"
    assert job["joules_label"] == "MEASURED"
    assert job["joules_measured"] == 15.0
    # The real measured joules number stays; only the exporter_node label is scrubbed.
    assert job["joules_evidence"]["joules_measured_total"] == 78369.586
    assert job["joules_evidence"]["exporter_node"] == "Sovereign GPU 1"


def test_operator_internal_constants_unchanged():
    # Doctrine: scrub at EGRESS only. The box must still probe the real tailnet meter
    # and real node hostnames internally — the constants are unchanged.
    assert eo._JOULE_METER_URL.startswith("http://100.")
    nodes = eo._default_nodes()
    names = {n.name for n in nodes}
    assert "rtx-betterwithage" in names  # internal identity unchanged
    # But the public projection of each carries no private token.
    for n in nodes:
        pub = eo._public_node(n.name)
        for tok in _PRIVATE_TOKENS:
            assert tok not in str(pub), (n.name, pub)


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
