# SPDX-License-Identifier: Apache-2.0
# © 2026 SZL Holdings · Doctrine v11 LOCKED · Λ = Conjecture 1 (NOT a theorem)
"""test_v4_fleet_federation — the fleet peer-health registry probes the two
genuinely-live standalone Spaces (immune-standalone, yarqa) FOR REAL, and does
so HONESTLY.

Federation guard (audit 2026-07-03): immune (/healthz=200) and yarqa
(/healthz=200) are genuinely-live standalone Spaces already proxied as
surfaces, but they were absent from PEER_HEALTH_URLS, so the fleet health view
never actually probed them. These tests lock:

  (a) both new keys are present in PEER_HEALTH_URLS (additive — existing peers
      untouched),
  (b) the aggregate fleet_status() includes them in its peer list,
  (c) a mocked-DOWN upstream (5xx AND a raised transport error) yields
      up:false with NO fabricated green — honesty over checklist,
  (d) a real 200 yields up:true (the honest signal is not hard-wired off),
  (e) these keys are surfaces, NOT flagship codenames — they must stay out of
      QUECHUA_NAMES (no G5 codename concern).

The probe is honest by construction: `up` is True ONLY on a real HTTP 200 and
False on any timeout/4xx/5xx or transport exception.
"""
import asyncio
import sys
import types

import szl_v4_fleet as fleet

NEW_KEYS = ("immune-standalone", "yarqa")


# ── (a) both new keys present; additive (existing peers intact) ───────────────
def test_new_standalone_spaces_present_and_additive():
    for k in NEW_KEYS:
        assert k in fleet.PEER_HEALTH_URLS, f"{k} missing from PEER_HEALTH_URLS"
    assert fleet.PEER_HEALTH_URLS["immune-standalone"] == \
        "https://szlholdings-immune.hf.space/healthz"
    assert fleet.PEER_HEALTH_URLS["yarqa"] == \
        "https://szlholdings-yarqa.hf.space/healthz"
    # Existing peers must remain untouched (additive-only guarantee).
    for existing in ("a11oy", "sentra", "amaru", "rosie", "killinchu"):
        assert existing in fleet.PEER_HEALTH_URLS, f"{existing} was removed"


# ── (e) surfaces, not codenames — no G5 concern ──────────────────────────────
def test_new_keys_are_not_codenames():
    for k in NEW_KEYS:
        assert k not in fleet.QUECHUA_NAMES, \
            f"{k} must not be treated as a flagship codename"


class _FakeResp:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        if self._payload is None:
            raise ValueError("no json body")
        return self._payload


def _install_fake_httpx(monkeypatch, *, status_code=None, raise_exc=None, payload=None):
    """Monkeypatch a fake httpx module so _probe_peer's local `import httpx`
    resolves to a controllable async client — no real network."""

    class _FakeAsyncClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url):
            if raise_exc is not None:
                raise raise_exc
            return _FakeResp(status_code, payload)

    fake = types.ModuleType("httpx")
    fake.AsyncClient = _FakeAsyncClient
    monkeypatch.setitem(sys.modules, "httpx", fake)


# ── (c) mocked-DOWN upstream (5xx) → up:false, never fabricated ───────────────
def test_down_5xx_upstream_reports_up_false(monkeypatch):
    _install_fake_httpx(monkeypatch, status_code=503)
    for k in NEW_KEYS:
        res = asyncio.run(fleet._probe_peer(k, fleet.PEER_HEALTH_URLS[k]))
        assert res["up"] is False, f"{k}: 503 must report up:false (no fake green)"
        assert res["status"] != "ok", f"{k}: 503 must not claim ok"
        assert res["http_code"] == 503


# ── (c) mocked-DOWN upstream (transport error/timeout) → up:false ────────────
def test_transport_error_reports_up_false(monkeypatch):
    _install_fake_httpx(monkeypatch, raise_exc=RuntimeError("connect timeout"))
    for k in NEW_KEYS:
        res = asyncio.run(fleet._probe_peer(k, fleet.PEER_HEALTH_URLS[k]))
        assert res["up"] is False, f"{k}: transport error must report up:false"
        assert res["status"] == "unreachable"


# ── (d) real 200 → up:true (the honest signal is not hard-wired off) ─────────
def test_live_200_reports_up_true(monkeypatch):
    _install_fake_httpx(monkeypatch, status_code=200,
                        payload={"ok": True, "service": "immune-standalone"})
    res = asyncio.run(fleet._probe_peer("immune-standalone",
                                        fleet.PEER_HEALTH_URLS["immune-standalone"]))
    assert res["up"] is True
    assert res["status"] == "ok"
    assert res["http_code"] == 200


# ── (b) aggregate fleet_status() includes the new peers, honestly down ────────
def test_fleet_status_includes_new_peers_and_stays_honest(monkeypatch):
    # Every upstream mocked DOWN: the aggregate must still list all peers and
    # report up:false for every one — no fabricated green anywhere.
    _install_fake_httpx(monkeypatch, status_code=503)
    agg = asyncio.run(fleet.fleet_status())
    flagships = {p["flagship"] for p in agg["peers"]}
    for k in NEW_KEYS:
        assert k in flagships, f"{k} missing from aggregate fleet_status peers"
    assert all(p["up"] is False for p in agg["peers"]), \
        "all-down fleet must not fabricate a single up:true"
