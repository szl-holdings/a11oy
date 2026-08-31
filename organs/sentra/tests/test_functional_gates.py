# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED — 749/14/163. HONEST functional test — real in-process app.
"""
Functional proof that sentra ENFORCES, end-to-end, over the real FastAPI app.

No mocks: boots serve.app in-process via Starlette TestClient and exercises the
real verdict engine. Proves a real BLOCK and a real ALLOW for:
  * threat-signature gate (gate-01)
  * Λ-threshold gate (gate-03)  ← newly enforcing
  * Section 889 vendor screen   ← newly functional
  * DSSE-attested verdict path  (Ed25519 round-trip)
"""
from __future__ import annotations

import base64
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
for p in (str(_ROOT), str(_SRC)):
    if p not in sys.path:
        sys.path.insert(0, p)

fastapi = pytest.importorskip("fastapi", reason="fastapi required for functional app test")
from fastapi.testclient import TestClient  # noqa: E402

import serve  # noqa: E402

client = TestClient(serve.app)


# ── gate-01 threat signature ────────────────────────────────────────────────
def test_threat_signature_blocks() -> None:
    r = client.post("/api/sentra/v1/verdict",
                    json={"request_id": "t-deny", "action": "DROP TABLE users; --"})
    assert r.status_code == 200
    body = r.json()
    assert body["decision"] == "deny"
    assert any("DROP TABLE" in s for s in body["signals"])
    assert body["receipt_hash"]


def test_clean_action_allows() -> None:
    r = client.post("/api/sentra/v1/verdict",
                    json={"request_id": "t-allow", "action": "read_config"})
    assert r.status_code == 200
    body = r.json()
    assert body["decision"] == "allow"
    assert body["signals"] == []
    assert body["receipt_hash"]


# ── gate-03 Λ-threshold (real enforcement) ──────────────────────────────────
def test_lambda_gate_denies_below_floor() -> None:
    r = client.post("/api/sentra/v1/verdict",
                    json={"request_id": "lam-low", "action": "read_file",
                          "axes": [0.9, 0.1, 0.8]})
    body = r.json()
    assert body["decision"] == "deny", body
    assert body["lambda_value"] == pytest.approx(0.1)
    assert any("lambda-gate" in s for s in body["signals"])


def test_lambda_gate_allows_above_floor() -> None:
    r = client.post("/api/sentra/v1/verdict",
                    json={"request_id": "lam-hi", "action": "read_file",
                          "axes": [0.9, 0.85, 0.7]})
    body = r.json()
    assert body["decision"] == "allow", body
    assert body["lambda_value"] == pytest.approx(0.7)


def test_lambda_gate_boundary_exactly_floor_allows() -> None:
    # MIN(axes) == floor (0.5) is NOT below the floor → allow.
    r = client.post("/api/sentra/v1/verdict",
                    json={"request_id": "lam-edge", "action": "read_file",
                          "axes": [0.5, 0.9]})
    assert r.json()["decision"] == "allow"


def test_gate03_test_endpoint_exercises_lambda() -> None:
    r = client.post("/api/sentra/v1/gates/gate-03/test",
                    json={"action": {"action": "read_file", "axes": [0.9, 0.1]}})
    assert r.json()["verdict"]["decision"] == "deny"


# ── Section 889 screening (real enforcement) ────────────────────────────────
@pytest.mark.parametrize("vendor", ["Huawei", "ZTE", "Hytera", "Hikvision", "Dahua"])
def test_section889_banned_vendor_flagged(vendor: str) -> None:
    r = client.post("/api/sentra/v1/section889/screen", json={"vendor": vendor})
    res = r.json()["results"][0]
    assert res["decision"] == "deny", res
    assert res["flagged"] is True
    assert res["matched_vendor"] == vendor
    assert res["receipt_hash"]


def test_section889_alias_and_case_insensitive() -> None:
    r = client.post("/api/sentra/v1/section889/screen",
                    json={"vendor": "hangzhou hikvision digital technology co"})
    res = r.json()["results"][0]
    assert res["decision"] == "deny"
    assert res["matched_vendor"] == "Hikvision"


def test_section889_clean_vendor_allowed() -> None:
    r = client.post("/api/sentra/v1/section889/screen", json={"vendor": "Cisco Systems"})
    res = r.json()["results"][0]
    assert res["decision"] == "allow"
    assert res["flagged"] is False


def test_section889_list_is_exactly_five() -> None:
    r = client.get("/api/sentra/v1/section889/vendors")
    body = r.json()
    assert body["count"] == 5
    assert body["banned_vendors"] == ["Huawei", "ZTE", "Hytera", "Hikvision", "Dahua"]


def test_section889_requires_input() -> None:
    r = client.post("/api/sentra/v1/section889/screen", json={})
    assert r.status_code == 400


# ── DSSE attested verdict (Ed25519 round-trip) ──────────────────────────────
def test_attested_verdict_dsse_verifies() -> None:
    r = client.post("/api/sentra/v1/verdict/attested",
                    json={"request_id": "att", "action": "read_config"})
    if r.status_code == 503:
        pytest.skip("immune provenance modules unavailable in this env")
    body = r.json()
    assert body["ok"] is True
    assert body["dsse_verify"]["verified"] is True
    dsse = body["dsse"]
    # Independently re-verify the Ed25519 signature over DSSE PAE bytes.
    ed = pytest.importorskip("cryptography.hazmat.primitives.asymmetric.ed25519")
    payload = base64.b64decode(dsse["payload"])
    ptype = dsse["payloadType"]
    pae = (b"DSSEv1 " + str(len(ptype)).encode() + b" " + ptype.encode()
           + b" " + str(len(payload)).encode() + b" " + payload)
    pub = ed.Ed25519PublicKey.from_public_bytes(
        base64.b64decode(dsse["publicKey"]["raw_b64"]))
    pub.verify(base64.b64decode(dsse["signatures"][0]["sig"]), pae)  # raises if bad


# ── healthz advertises the verified SLSA level ──────────────────────────────
def test_healthz_reports_eight_gates_and_slsa_l2() -> None:
    r = client.get("/api/sentra/healthz")
    body = r.json()
    assert body["gates"] == 8
    assert "L2" in body["slsa"]
