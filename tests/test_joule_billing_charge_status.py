#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""joule_billing.charge_stripe must not report an unconfirmed PaymentIntent as "charged".

Monetization audit G-22: the CLI created a Stripe PaymentIntent with no payment method
and no confirmation, then printed {"status": "charged"} although no money had moved.
These tests install a fake ``stripe`` module (no network, no real key) so the reported
status is pinned to the intent's actual state.
"""
from __future__ import annotations

import json
import sys
import types

import pytest

import joule_billing
from joule_billing import JouleReading, build_receipt, charge_stripe

TS = "2026-11-06T00:00:00+00:00"
NOT_A_KEY = "test-key-not-used"


def _receipt() -> dict:
    reading = JouleReading("node-a", 78369.586, "MEASURED", 5.0, 62.08, TS)
    receipt = build_receipt(reading, 45)
    assert receipt["decision"]["amount_cents"] > 0
    return receipt


class _FakePaymentIntentApi:
    def __init__(self, status):
        self._status = status
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        intent = types.SimpleNamespace(id="pi_fake_0001")
        if self._status is not None:
            intent.status = self._status
        return intent


def _install_fake_stripe(monkeypatch, status):
    fake = types.ModuleType("stripe")
    fake.api_key = None
    fake.PaymentIntent = _FakePaymentIntentApi(status)
    monkeypatch.setitem(sys.modules, "stripe", fake)
    return fake


@pytest.mark.parametrize(
    "stripe_status",
    [
        "requires_payment_method",
        "requires_confirmation",
        "requires_action",
        "processing",
        "requires_capture",
        "canceled",
        None,
    ],
)
def test_unconfirmed_intent_is_reported_as_intent_created(monkeypatch, stripe_status):
    fake = _install_fake_stripe(monkeypatch, stripe_status)
    receipt = _receipt()

    out = charge_stripe(receipt, "cus_fake", NOT_A_KEY)

    assert out["status"] == "intent_created"
    assert "amount_cents" not in out
    assert out["would_charge_cents"] == receipt["decision"]["amount_cents"]
    assert out["payment_intent"] == "pi_fake_0001"
    assert out["stripe_status"] == stripe_status
    assert out["idempotency_key"] == joule_billing.d_idem(receipt)
    assert len(fake.PaymentIntent.calls) == 1
    assert "confirm" not in fake.PaymentIntent.calls[0]


def test_succeeded_intent_is_reported_as_charged(monkeypatch):
    _install_fake_stripe(monkeypatch, "succeeded")
    receipt = _receipt()

    out = charge_stripe(receipt, "cus_fake", NOT_A_KEY)

    assert out["status"] == "charged"
    assert out["amount_cents"] == receipt["decision"]["amount_cents"]
    assert out["stripe_status"] == "succeeded"


def test_cli_with_key_prints_intent_created_not_charged(monkeypatch, capsys):
    _install_fake_stripe(monkeypatch, "requires_payment_method")
    monkeypatch.setenv("STRIPE_API_KEY", NOT_A_KEY)

    rc = joule_billing.main([
        "--node", "node-a", "--joules", "78369.586", "--label", "MEASURED",
        "--nvml-age-s", "5", "--grid-price-eur-mwh", "62.08",
        "--customer", "cus_fake", "--price-per-kwh-cents", "45",
    ])

    assert rc == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["charge"]["status"] == "intent_created"
    assert "amount_cents" not in printed["charge"]


def test_without_key_stays_dry_run_and_never_calls_stripe(monkeypatch):
    fake = _install_fake_stripe(monkeypatch, "succeeded")

    out = charge_stripe(_receipt(), "cus_fake", "")

    assert out["status"] == "dry-run"
    assert fake.PaymentIntent.calls == []
