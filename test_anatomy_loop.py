# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""
test_anatomy_loop.py — offline self-test for szl_anatomy_loop.

Imports the module, registers the endpoint on a FAKE app, drives the handler,
and asserts the doctrine v11 invariants hold OFFLINE (no network, no serve.py):

  - joules_label == "sample" by default (off-box, no real meter wired);
  - ayni.balanced is True (reciprocal, never net-positive);
  - no "key" anywhere in the output (no leaked/secret key in the response);
  - every organ carries "experimental" (organs are never claimed proven).

Pure stdlib. Run: python3 test_anatomy_loop.py
"""
import json

import szl_anatomy_loop as loop


class _FakeApp:
    """Minimal app exposing add_api_route — records what register() wires."""

    def __init__(self):
        self.routes = []

    def add_api_route(self, path, fn, methods=None):
        self.routes.append((path, fn, tuple(methods or [])))


def _extract_body(resp):
    """Pull the JSON dict out of whatever the handler returned (JSONResponse or dict)."""
    if isinstance(resp, dict):
        return resp
    # Starlette JSONResponse keeps the encoded bytes on .body
    body = getattr(resp, "body", None)
    if body is not None:
        return json.loads(body.decode("utf-8") if isinstance(body, (bytes, bytearray)) else body)
    raise AssertionError(f"could not extract body from {resp!r}")


def test_register_wires_loop_route():
    app = _FakeApp()
    registered = loop.register(app, ns="a11oy")
    assert registered == ["/api/a11oy/v1/anatomy/loop"], registered
    assert len(app.routes) == 1
    path, fn, methods = app.routes[0]
    assert path == "/api/a11oy/v1/anatomy/loop"
    assert "GET" in methods
    return fn


def test_loop_invariants():
    # Drive the registered handler exactly as the app would (offline).
    fn = test_register_wires_loop_route()
    resp = fn(None)
    out = _extract_body(resp)

    # (1) joules_label is "sample" by default — never a fabricated measurement.
    assert out["joules_label"] == "sample", out["joules_label"]
    assert out["intake"]["joules_label"] == "sample", out["intake"]
    assert out["reservoir"]["joules_label"] == "sample", out["reservoir"]

    # (2) Ayni balances — reciprocal, never net-positive.
    assert out["ayni"]["balanced"] is True, out["ayni"]

    # (3) No "key" anywhere in the serialized output (no leaked secret key).
    blob = json.dumps(out).lower()
    assert "key" not in blob, "output must not contain any 'key'"

    # (4) Every organ carries "experimental" — organs are never claimed proven.
    assert out["organs"], "expected at least one organ"
    for organ in out["organs"]:
        assert "experimental" in organ["note"].lower(), organ
        assert "flowing" in organ and isinstance(organ["flowing"], bool)

    # Shape sanity: required top-level keys present and honest.
    assert out["kind"] == "anatomy-circulation-loop"
    assert out["ns"] == "a11oy"
    assert out["doctrine"] == "v11"
    assert "honesty" in out and isinstance(out["honesty"], str)
    assert isinstance(out["beats_last_cycle"], int)

    return out


if __name__ == "__main__":
    result = test_loop_invariants()
    print("PASS — anatomy loop self-test")
    print(json.dumps({
        "joules_label": result["joules_label"],
        "ayni_balanced": result["ayni"]["balanced"],
        "organs": [o["name"] for o in result["organs"]],
        "beats_last_cycle": result["beats_last_cycle"],
        "last_receipt_id": result["last_receipt_id"][:12] + "..." if result["last_receipt_id"] else "",
    }, indent=2))
