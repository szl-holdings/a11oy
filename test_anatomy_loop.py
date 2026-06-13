# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""
test_anatomy_loop.py — offline self-test for szl_anatomy_loop.

Imports the module, registers the endpoint on a FAKE app, drives the handler,
and asserts the doctrine v11 invariants hold OFFLINE (no network, no serve.py):

  - joules_label == "sample" by default (off-box, no real meter wired);
  - ayni.balanced is True (reciprocal, never net-positive);
  - no "key" anywhere in the output (no leaked/secret key in the response);
  - every organ carries "experimental" (organs are never claimed proven);
  - YARQA appears as the named CIRCULATORY organ INSIDE the unified loop
    (the irrigation-canal / flow-router / vascular system), tagged EXPERIMENTAL,
    with the heart as the pump and YARQA as the vessels of ONE circulatory
    subsystem — the consolidation invariant (#yarqa-anatomy-consolidation).

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

    # (5) CONSOLIDATION: YARQA is the named CIRCULATORY organ INSIDE this loop.
    names = [o["name"] for o in out["organs"]]
    assert "YARQA" in names, f"YARQA must be a named organ in the unified loop: {names}"
    yarqa = next(o for o in out["organs"] if o["name"] == "YARQA")
    # role names the circulatory function (flow-router / irrigation-canal).
    assert "circulatory" in yarqa["role"].lower(), yarqa["role"]
    # YARQA is EXPERIMENTAL — never claimed proven.
    assert "experimental" in yarqa["note"].lower(), yarqa
    # flowing is a real bool reflecting dispersal (not a fabricated truthy flag).
    assert isinstance(yarqa["flowing"], bool), yarqa
    # The unified body exposes ONE circulatory subsystem: heart = pump, YARQA = vessels.
    assert out["circulatory"]["vessels"] == "YARQA", out["circulatory"]
    assert "heart" in out["circulatory"]["pump"].lower(), out["circulatory"]
    assert "circulatory" in out["circulatory"]["vessels_role"].lower(), out["circulatory"]
    # ONE canonical loop surface + the standalone canal alias kept ALIVE.
    assert "unified_loop" in out["surfaces"], out["surfaces"]
    assert "/yarqa" in out["surfaces"]["standalone_canal"], out["surfaces"]

    # Shape sanity: required top-level keys present and honest.
    assert out["kind"] == "anatomy-circulation-loop"
    assert out["ns"] == "a11oy"
    assert out["doctrine"] == "v11"
    assert "honesty" in out and isinstance(out["honesty"], str)
    assert isinstance(out["beats_last_cycle"], int)

    return out


def test_yarqa_is_circulatory_organ():
    """Focused consolidation assertion: YARQA is the circulatory organ, honest joules.

    Asserts the founder-approved architecture: YARQA is the named circulatory
    organ (vascular system) INSIDE the unified anatomy loop — not a sibling peer.
    Also re-checks the doctrine v11 honesty floor: joules_label is MEASURED only
    when a real on-box source is present, else SAMPLE (here, offline -> sample).
    """
    out = loop.run_loop(ns="a11oy")

    # YARQA present, circulatory, EXPERIMENTAL.
    yarqa = next((o for o in out["organs"] if o["name"] == "YARQA"), None)
    assert yarqa is not None, [o["name"] for o in out["organs"]]
    assert yarqa["role"] == "circulatory (flow-router / irrigation-canal)", yarqa["role"]
    assert "experimental" in yarqa["note"].lower(), yarqa

    # YARQA's flowing mirrors real dispersal; dispersed credits are 0 when idle.
    assert isinstance(yarqa["flowing"], bool), yarqa
    if not yarqa["flowing"]:
        assert yarqa.get("dispersed_work_credits", 0) == 0, yarqa

    # joules_label honest: MEASURED only with a real on-box source, else SAMPLE.
    # This module runs offline in CI, so it MUST be sample (never fabricated).
    assert out["joules_label"] in ("sample", "measured"), out["joules_label"]
    assert out["joules_label"] == "sample", "offline must degrade to sample, never measured"

    # Ayni balances — reciprocal, never net-positive.
    assert out["ayni"]["balanced"] is True, out["ayni"]

    # No "key" anywhere in the serialized output (no leaked secret).
    assert "key" not in json.dumps(out).lower(), "output must not contain any 'key'"
    return out


if __name__ == "__main__":
    result = test_loop_invariants()
    yarqa_out = test_yarqa_is_circulatory_organ()
    print("PASS — anatomy loop self-test (YARQA consolidated as circulatory organ)")
    print(json.dumps({
        "joules_label": result["joules_label"],
        "ayni_balanced": result["ayni"]["balanced"],
        "organs": [o["name"] for o in result["organs"]],
        "beats_last_cycle": result["beats_last_cycle"],
        "last_receipt_id": result["last_receipt_id"][:12] + "..." if result["last_receipt_id"] else "",
    }, indent=2))
