# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
# Adapted from PURIQ revision 2ea8ea4bb9de2ca432f40c0c55ea5a5ed02786bf.
"""Synthetic ephemeral-key verification tests; no upstream code or network."""
import base64
from copy import deepcopy
from datetime import datetime
from decimal import localcontext
import json

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, utils
import pytest

import importlib
_verifier = importlib.import_module("verticals.puriq-markets.runtime.signed_prices").verifier
INDEX_V2_FIELDS, verify_print = _verifier.INDEX_V2_FIELDS, _verifier.verify_print


def _sign(key, text):
    der = key.sign(text.encode(), ec.ECDSA(hashes.SHA256()))
    r, s = utils.decode_dss_signature(der)
    return base64.b64encode(r.to_bytes(32, "big") + s.to_bytes(32, "big")).decode()


def _value(data, path):
    parts = path.split(".")
    return data.get(parts[0]) if len(parts) == 1 else data.get(parts[0], {}).get(parts[1])


def _resign(key, data):
    data["signature"] = _sign(key, "\n".join(("pulse-index-v1", data["symbol"],
        data["priceText"], data["at"], data["grade"])))
    canonical = "pulse-index-v2\n" + "\n".join(path + "=" + json.dumps(_value(data, path),
        separators=(",", ":")) for path in INDEX_V2_FIELDS)
    data["v2"] = {"sig": "pulse-index-v2", "kid": data["kid"],
                  "canonical": canonical, "signature": _sign(key, canonical)}


@pytest.fixture
def signed():
    key = ec.generate_private_key(ec.SECP256R1())
    pem = key.public_key().public_bytes(serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    ring = {"verificationKeys": [{"kid": "test-key-1", "pem": pem}],
            "canonicalV2Fields": {"index": list(INDEX_V2_FIELDS)}}
    data = {"symbol": "BTC", "price": 81234.56, "priceText": "81234.56",
        "at": "2026-10-07T16:48:45.646Z", "grade": "consensus",
        "kid": "test-key-1", "sig": "pulse-index-v1", "engine": "test-engine",
        "sources": 20, "tier": "consensus", "confidence": 0.75, "dispersionBps": 2.1,
        "interval": {"lower": 81200.0, "upper": 81250.0},
        "cadence": {"band": "real-time", "calculatedAgeMs": 100,
            "newestSourceAgeMs": 100, "oldestSourceAgeMs": 1200,
            "p50UpdateMs": 100, "p95UpdateMs": 500}}
    _resign(key, data)
    now = datetime.fromisoformat(data["at"].replace("Z", "+00:00")).timestamp() + 1
    return key, data, ring, now


def test_valid_record_is_fresh_and_does_not_authorize(signed):
    _, data, ring, now = signed
    before = deepcopy((data, ring))
    result = verify_print(data, ring, now=now, expected_symbol="BTC")
    assert result["core_valid"] and result["record_valid"] and result["fresh"]
    assert result["verification_scope"] == "full-record"
    assert result["freshness"]["age_seconds"] == 1
    assert result["signed_fields"] == list(INDEX_V2_FIELDS)
    assert len(result["key_fingerprint"]) == 64
    assert result["reasons"] == [] and result["can_authorize"] is False
    assert (data, ring) == before


@pytest.mark.parametrize("path,value", [("sources", 2), ("tier", "single-source"),
    ("confidence", 0.99), ("dispersionBps", 0.01), ("engine", "changed"),
    ("interval.lower", 1), ("cadence.oldestSourceAgeMs", 0)])
def test_metadata_edit_cannot_downgrade_to_price_only(signed, path, value):
    _, data, ring, now = signed
    parts = path.split(".")
    if len(parts) == 1:
        data[path] = value
    else:
        data[parts[0]][parts[1]] = value
    result = verify_print(data, ring, now=now)
    assert result["core_valid"] is True and result["record_valid"] is False
    assert result["verification_scope"] == "invalid"
    assert "V2_FIELD_MISMATCH:" + path in result["reasons"]


def test_missing_v2_is_explicitly_price_only(signed):
    _, data, ring, now = signed
    del data["v2"]
    result = verify_print(data, ring, now=now)
    assert result["core_valid"] and result["fresh"]
    assert not result["record_valid"] and result["verification_scope"] == "price-only"
    assert result["reasons"] == ["V2_MISSING"]


@pytest.mark.parametrize("block", [None, {}, {"sig": "pulse-index-v1"}])
def test_supplied_bad_v2_is_invalid(signed, block):
    _, data, ring, now = signed
    data["v2"] = block
    result = verify_print(data, ring, now=now)
    assert result["core_valid"] and result["verification_scope"] == "invalid"


@pytest.mark.parametrize("age,expected", [(31, "STALE"), (-2.001, "FUTURE"), (-2, "FRESH"), (30, "FRESH")])
def test_freshness_uses_authenticated_event_time(signed, age, expected):
    _, data, ring, now = signed
    result = verify_print(data, ring, now=now - 1 + age)
    assert result["record_valid"]
    assert result["freshness"]["status"] == expected
    assert result["fresh"] is (expected == "FRESH")


def test_wrong_key_does_not_validate(signed):
    _, data, ring, now = signed
    wrong = ec.generate_private_key(ec.SECP256R1())
    ring["verificationKeys"][0]["pem"] = wrong.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    result = verify_print(data, ring, now=now)
    assert not result["core_valid"] and not result["fresh"]
    assert "SIGNATURE_INVALID" in result["reasons"]


def test_unknown_key_never_falls_back_to_active_key(signed):
    _, data, ring, now = signed
    ring["activeKid"] = "test-key-1"
    ring["publicKeyPem"] = ring["verificationKeys"][0]["pem"]
    data["kid"] = "unknown"
    assert "UNKNOWN_KEY_ID" in verify_print(data, ring, now=now)["reasons"]


@pytest.mark.parametrize("change,reason", [("duplicate", "DUPLICATE_KEY_ID"),
    ("malformed", "INVALID_PUBLIC_KEY"), ("too_many", "INVALID_KEYRING")])
def test_entire_keyring_is_validated(signed, change, reason):
    _, data, ring, now = signed
    if change == "duplicate":
        ring["verificationKeys"].append(deepcopy(ring["verificationKeys"][0]))
    elif change == "malformed":
        ring["verificationKeys"].append({"kid": "other", "pem": "bad"})
    else:
        ring["verificationKeys"] *= 33
    assert reason in verify_print(data, ring, now=now)["reasons"]


@pytest.mark.parametrize("price", [81234.57, True, "81234.56", float("nan"), float("inf")])
def test_price_mismatch_and_nonfinite_are_rejected(signed, price):
    _, data, ring, now = signed
    data["price"] = price
    result = verify_print(data, ring, now=now)
    assert not result["core_valid"] and result["verification_scope"] == "invalid"


def test_precision_loss_must_not_hide_price_text_edit(signed):
    key, data, ring, now = signed
    data["priceText"] = "81234.5600000000001"
    _resign(key, data)
    assert "PRICE_TEXT_MISMATCH" in verify_print(data, ring, now=now)["reasons"]


@pytest.mark.parametrize("field,value", [("symbol", "BTC\nETH"),
    ("grade", "consensus\x00"), ("priceText", "81234.56\r"),
    ("grade", "consen\u202esus")])
def test_control_characters_rejected_even_if_signed(signed, field, value):
    key, data, ring, now = signed
    data[field] = value
    _resign(key, data)
    assert not verify_print(data, ring, now=now)["core_valid"]


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "extra", "reordered", "trailing", "version"])
def test_signed_but_wrong_v2_schema_is_rejected(signed, mutation):
    key, data, ring, now = signed
    lines = data["v2"]["canonical"].split("\n")
    if mutation == "missing":
        lines.pop()
    elif mutation == "duplicate":
        lines[-1] = lines[-2]
    elif mutation == "extra":
        lines.append("other=0")
    elif mutation == "reordered":
        lines[1], lines[2] = lines[2], lines[1]
    elif mutation == "version":
        lines[0] = "pulse-index-v3"
    else:
        lines.append("")
    canonical = "\n".join(lines)
    data["v2"].update(canonical=canonical, signature=_sign(key, canonical))
    result = verify_print(data, ring, now=now)
    assert result["core_valid"] and not result["record_valid"]
    assert result["verification_scope"] == "invalid"


def test_boolean_does_not_equal_number(signed):
    key, data, ring, now = signed
    data["sources"] = 1
    _resign(key, data)
    data["sources"] = True
    assert "V2_FIELD_MISMATCH:sources" in verify_print(data, ring, now=now)["reasons"]


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity", "1e99999", "1e9999999", "1e9999999999999999999999", "[]", "{}", '"bad\\nvalue"'])
def test_canonical_requires_finite_scalar_values(signed, value):
    key, data, ring, now = signed
    canonical = data["v2"]["canonical"].replace("confidence=0.75", "confidence=" + value)
    data["v2"].update(canonical=canonical, signature=_sign(key, canonical))
    assert not verify_print(data, ring, now=now)["record_valid"]


@pytest.mark.parametrize("signature", ["bad", "A" * 88, "=" * 88])
def test_invalid_p1363_encoding_is_rejected(signed, signature):
    _, data, ring, now = signed
    data["signature"] = signature
    assert not verify_print(data, ring, now=now)["core_valid"]


def test_canonical_bytes_tamper_rejected(signed):
    _, data, ring, now = signed
    data["v2"]["canonical"] += " "
    result = verify_print(data, ring, now=now)
    assert result["core_valid"] and "SIGNATURE_INVALID" in result["reasons"]


def test_symbol_and_version_are_enforced(signed):
    _, data, ring, now = signed
    assert not verify_print(data, ring, now=now, expected_symbol="ETH")["core_valid"]
    data["sig"] = "pulse-index-v2"
    assert not verify_print(data, ring, now=now)["core_valid"]


@pytest.mark.parametrize("now,max_age", [(float("nan"), 30), (True, 30), (10 ** 1000, 30), (0, 0), (0, float("inf")), (0, 86401)])
def test_invalid_clock_configuration_is_structured(signed, now, max_age):
    _, data, ring, _ = signed
    assert not verify_print(data, ring, now=now, max_age_seconds=max_age)["core_valid"]


def test_oversized_input_is_rejected(signed):
    _, data, ring, now = signed
    data["note"] = "x" * 20_000
    assert "INVALID_PRINT" in verify_print(data, ring, now=now)["reasons"]


def test_nullable_absent_metadata_is_compared_as_null(signed):
    key, data, ring, now = signed
    del data["confidence"]
    _resign(key, data)
    assert verify_print(data, ring, now=now)["record_valid"]
    data["confidence"] = 0.9
    assert not verify_print(data, ring, now=now)["record_valid"]


def test_numeric_bound_is_independent_of_decimal_context(signed):
    key, data, ring, now = signed
    data["sources"] = 1_000_000_000_000_001
    _resign(key, data)
    with localcontext() as context:
        context.prec = 4
        result = verify_print(data, ring, now=now)
    assert result["core_valid"] and not result["record_valid"]
    assert "INVALID_NUMBER" in result["reasons"]


def test_huge_max_age_is_structured_failure(signed):
    _, data, ring, now = signed
    result = verify_print(data, ring, now=now, max_age_seconds=10 ** 1000)
    assert result["reasons"] == ["INVALID_MAX_AGE"]
