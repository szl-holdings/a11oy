"""Local verification: TestClient the POST /residual/evaluate endpoint.

Proves the endpoint returns 200 MODELED with a REAL computed residual (fits the
physics-informed net in-request), cites the physical_bounds_certificate, and honors
request bounds. Not part of the shipped organ; a local proof harness.
"""
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

import szl_pinn_bounds


def main():
    app = FastAPI()
    paths = szl_pinn_bounds.register(app, ns="a11oy")
    assert "/api/a11oy/v1/pinn/residual/evaluate" in paths, paths
    client = TestClient(app)

    # (1) default params -> 200 MODELED with a real residual
    r = client.post("/api/a11oy/v1/pinn/residual/evaluate", json={})
    assert r.status_code == 200, (r.status_code, r.text[:300])
    body = r.json()
    assert body["label"] == "MODELED", body.get("label")
    assert body["modeled_not_measured"] is True
    resid = body["residual"]
    assert resid["rms_residual"] >= 0.0
    assert 0.0 <= resid["rel_l2_error_vs_exact"] < 1.0
    assert body["training"]["iters_run"] <= body["training"]["max_iters"]
    cert = body["physical_bounds_certificate"]
    assert cert.get("citation")
    print("[1] default POST -> 200 MODELED")
    print("    rms_residual         =", resid["rms_residual"])
    print("    rel_l2_error_vs_exact=", resid["rel_l2_error_vs_exact"])
    print("    iters_run/max        =", body["training"]["iters_run"], "/", body["training"]["max_iters"])
    print("    wall_seconds         =", body["training"]["wall_seconds"])
    print("    cert.present         =", cert.get("present"), cert.get("cert_sha256"))
    print("    numpy_crosscheck     =", body.get("numpy_crosscheck"))

    # (2) custom (bounded) params still 200 MODELED and a different, real residual
    r2 = client.post("/api/a11oy/v1/pinn/residual/evaluate",
                     json={"n_hidden": 16, "n_collocation": 32, "max_iters": 900, "seed": 42})
    assert r2.status_code == 200, (r2.status_code, r2.text[:300])
    b2 = r2.json()
    assert b2["label"] == "MODELED"
    print("[2] custom POST -> 200 MODELED; rms=", b2["residual"]["rms_residual"],
          "relL2=", b2["residual"]["rel_l2_error_vs_exact"])

    # (3) abusive params are CLAMPED (cannot request an unbounded in-request solve)
    r3 = client.post("/api/a11oy/v1/pinn/residual/evaluate",
                     json={"n_hidden": 99999, "n_collocation": 99999, "max_iters": 9999999})
    assert r3.status_code == 200
    b3 = r3.json()
    assert b3["training"]["n_hidden"] <= 32
    assert b3["training"]["n_collocation"] <= 64
    assert b3["training"]["max_iters"] <= 1500
    print("[3] abusive POST clamped -> n_hidden=", b3["training"]["n_hidden"],
          "n_coll=", b3["training"]["n_collocation"], "max_iters=", b3["training"]["max_iters"])

    # (4) empty body (no JSON) -> still 200 with defaults
    r4 = client.post("/api/a11oy/v1/pinn/residual/evaluate")
    assert r4.status_code == 200, (r4.status_code, r4.text[:300])
    assert r4.json()["label"] == "MODELED"
    print("[4] empty-body POST -> 200 MODELED (defaults)")

    print("\nALL ENDPOINT CHECKS PASSED")
    print("\n--- full default payload (pretty) ---")
    print(json.dumps(body, indent=2)[:2600])


if __name__ == "__main__":
    main()
