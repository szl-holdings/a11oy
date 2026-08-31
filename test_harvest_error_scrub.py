# SPDX-License-Identifier: Apache-2.0
# © 2026 SZL Holdings · Doctrine v11 LOCKED · Λ = Conjecture 1 (advisory, NOT proven trust)
"""test_harvest_error_scrub — reliability tests for a11oy_harvest_endpoints.

The harvest handlers degrade honestly (never 500) when a free feed is down. The
degraded body carries the exception string, so it must be BOUNDED (truncated) and
ADDRESS-SCRUBBED — a down-feed exception must never leak a private tailnet/box
address into a served response. These assert that hygiene without weakening the
honest diagnostic content (a benign 503/timeout message survives intact).
"""
import a11oy_harvest_endpoints as h


def test_safe_err_scrubs_private_tailnet_and_box_addresses():
    e = Exception("connect failed: http://100.96.129.45:9471/probe and 167.233.50.75:443")
    out = h._safe_err(e)
    assert "100.96.129.45" not in out
    assert "167.233.50.75" not in out
    assert "9471" not in out and "443" not in out
    assert "(private)" in out


def test_safe_err_preserves_honest_diagnostic_content():
    out = h._safe_err(Exception("aWATTar feed returned 503 Service Unavailable"))
    assert "aWATTar" in out
    assert "503" in out


def test_safe_err_is_bounded():
    out = h._safe_err(Exception("x" * 5000))
    assert len(out) <= 200


def test_safe_err_does_not_overscrub_public_feed_hosts():
    # Public feed hosts are NOT private addressing and must remain readable.
    out = h._safe_err(Exception("api.energy-charts.info timed out after 6s"))
    assert "api.energy-charts.info" in out


def test_degraded_handlers_never_raise_and_are_scrubbed(monkeypatch):
    """Force each live-feed handler to raise a private-address exception; the
    handler must return a degraded dict (ok=False) with the address scrubbed."""
    boom = Exception("upstream 100.110.0.7:9471 refused connection")

    def _raise(*a, **k):
        raise boom

    # Only meaningful when the harvest package imported in this env.
    if not h._HARVEST_OK:
        return

    for fn_name, patch_name in (
        ("handle_posture", "current_harvest_posture"),
        ("handle_world", "scan_world_renshare"),
        ("handle_receipt", "harvest_provenance"),
    ):
        monkeypatch.setattr(h, patch_name, _raise, raising=False)
        out = getattr(h, fn_name)()
        assert out["ok"] is False, fn_name
        assert "100.110.0.7" not in str(out), fn_name
        assert "9471" not in str(out), fn_name


if __name__ == "__main__":
    import traceback
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in fns:
        try:
            if "monkeypatch" in fn.__code__.co_varnames:
                continue  # needs pytest fixture
            fn()
            passed += 1
            print(f"PASS {fn.__name__}")
        except Exception:
            print(f"FAIL {fn.__name__}")
            traceback.print_exc()
    print(f"\n{passed} (non-fixture) passed")
