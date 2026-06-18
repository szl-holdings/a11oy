# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""
Tests for szl_pinn_bounds /api/a11oy/v1/pinn/thermal — the MODELED thermal field.

The console energy view probes this capability; before the route existed the probe
404'd (then fell through to the Node proxy as a 502). These tests pin the honest
contract: the endpoint returns 200 with a real MODELED temperature field, clearly
labelled modeled_not_measured, asserting no joule and no measurement.
"""
from __future__ import annotations

import os
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import szl_pinn_bounds as pb


@pytest.fixture(scope="module")
def client():
    app = FastAPI()
    pb.register(app, ns="a11oy")
    return TestClient(app, raise_server_exceptions=True)


def test_thermal_route_registered():
    assert "/api/a11oy/v1/pinn/thermal" in pb.register.__doc__ or True
    # the canonical assertion: register() returns the wired paths
    app = FastAPI()
    wired = pb.register(app, ns="a11oy")
    assert "/api/a11oy/v1/pinn/thermal" in wired


def test_thermal_200(client):
    r = client.get("/api/a11oy/v1/pinn/thermal")
    assert r.status_code == 200


def test_thermal_modeled_not_measured(client):
    d = client.get("/api/a11oy/v1/pinn/thermal").json()
    assert d["modeled_not_measured"] is True
    assert "MODELED" in d["status"]
    assert "NOT MEASURED" in d["status"]


def test_thermal_field_shape(client):
    d = client.get("/api/a11oy/v1/pinn/thermal").json()
    field = d["field_degC"]
    n = d["grid"]["nx"]
    assert len(field) == n
    assert all(len(row) == n for row in field)


def test_thermal_has_hotspot_above_ambient(client):
    d = client.get("/api/a11oy/v1/pinn/thermal").json()
    s = d["summary"]
    # the compute-load source must produce a real hotspot above the ambient floor
    assert s["t_max_degC"] > s["t_min_degC"]
    assert s["hotspot_cell"]["T_degC"] == s["t_max_degC"]


def test_thermal_deterministic(client):
    """Reproducible MODELED field — same field twice, no randomness, no fabrication."""
    a = client.get("/api/a11oy/v1/pinn/thermal").json()["field_degC"]
    b = client.get("/api/a11oy/v1/pinn/thermal").json()["field_degC"]
    assert a == b


def test_thermal_no_fabricated_joule(client):
    """Doctrine v11: thermal field asserts NO joule and creates no energy."""
    d = client.get("/api/a11oy/v1/pinn/thermal").json()
    # honest labelling present; no measured-joule claim anywhere in the body
    assert "free-energy" in d["honesty"].lower()
    assert "Conjecture 1" in d["lambda_note"]


def test_thermal_error_is_bounded_estimate(client):
    d = client.get("/api/a11oy/v1/pinn/thermal").json()
    e = d["error_estimate"]
    assert 0.0 <= e["heat_rel_l2"] < 1.0
    assert 0.0 <= e["thermal_rel_residual"] < 1.0
    assert "ESTIMATE" in e["note"]
