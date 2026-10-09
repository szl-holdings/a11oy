# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Canonical signed-price reads; offline components are pinned to PURIQ source."""
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import time
import httpx

from .transport import FinanceError, digest as sha256_json, source_revision

ROOT = Path(__file__).parent / "components" / "puriq_verity"
COMPONENT = json.loads((ROOT / "source.json").read_text(encoding="utf-8"))

def component(name):
    path = ROOT / name
    if hashlib.sha256(path.read_bytes()).hexdigest() != COMPONENT["files"][name]:
        raise RuntimeError("PURIQ component digest mismatch")
    spec = importlib.util.spec_from_file_location("szl_" + name[:-3], path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

verifier = component("puriq_verity.py")
reference = component("puriq_reference.py")
verify_print = verifier.verify_print

class SourceUnavailable(ValueError):
    pass

ORIGIN = "https://mcp.thepulse.markets"
KEY_URL = ORIGIN + "/api/index/v1/pubkey"
SAMPLE_URL = ORIGIN + "/api/index/v1/sample"
POLICY = {
    "id": "puriq.signed-price-review/v1",
    "max_age_seconds": 30,
    "require_full_record": True,
    "allowed_grades": ["consensus", "blended"],
    "min_reported_sources": 3,
    "market_accuracy_verified": False,
    "source_independence_verified": False,
}


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _not_finite(_):
    raise ValueError("nonfinite JSON value")


def _finite_float(text):
    value = float(text)
    if (not math.isfinite(value)
            or value == 0 and any(c in "123456789" for c in text.lower().split("e", 1)[0])):
        raise ValueError("nonfinite JSON number")
    return value


class SignedPriceClient:
    def __init__(self, transport=None, clock=time.time):
        self.transport, self.clock = transport, clock

    def _get(self, client, url, *, params=None, limit=65_536):
        # Destinations originate only in this module, never a request URL.
        if url not in (KEY_URL, SAMPLE_URL):
            raise SourceUnavailable()
        started = time.monotonic()
        try:
            with client.stream("GET", url, params=params) as response:
                if (response.status_code != 200
                        or response.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json"
                        or response.headers.get("content-encoding", "identity") not in ("", "identity")):
                    raise SourceUnavailable()
                chunks, size = [], 0
                for chunk in response.iter_bytes():
                    if time.monotonic() - started > 6:
                        raise SourceUnavailable()
                    size += len(chunk)
                    if size > limit:
                        raise SourceUnavailable()
                    chunks.append(chunk)
                if time.monotonic() - started > 6:
                    raise SourceUnavailable()
            raw = b"".join(chunks)
            data = json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_not_finite,
                              parse_float=_finite_float)
            if not isinstance(data, dict) or data.get("success") is False:
                raise ValueError("invalid source response")
            return raw, data
        except (httpx.HTTPError, ValueError, RecursionError) as error:
            raise SourceUnavailable() from error

    def observe(self, symbol="BTC"):
        if symbol not in ("BTC", "ETH", "SOL"):
            raise ValueError("Only public BTC, ETH and SOL samples are supported")
        with httpx.Client(transport=self.transport, timeout=4, follow_redirects=False, trust_env=False,
                          headers={"Accept": "application/json", "Accept-Encoding": "identity",
                          "User-Agent": "SZL-PURIQ-Signed-Price/1.0"}) as http:
            key_raw, ring = self._get(http, KEY_URL)
            raw, print_data = self._get(http, SAMPLE_URL, params={"symbol": symbol})
        observed_at = self.clock()
        verification = verify_print(print_data, ring, now=observed_at,
                                    expected_symbol=symbol,
                                    max_age_seconds=POLICY["max_age_seconds"])
        reasons = list(verification["reasons"])
        if not verification["record_valid"]:
            reasons.append("FULL_RECORD_REQUIRED")
        if not verification["fresh"]:
            reasons.append("FRESH_PRINT_REQUIRED")
        if print_data.get("grade") not in POLICY["allowed_grades"]:
            reasons.append("GRADE_NOT_ELIGIBLE")
        count = print_data.get("sources")
        if type(count) is not int or count < POLICY["min_reported_sources"]:
            reasons.append("INSUFFICIENT_REPORTED_SOURCES")
        eligible = not reasons
        body = {
            "schema": "szl.puriq-signed-price-observation/v1",
            "source_url": SAMPLE_URL + "?symbol=" + symbol,
            "key_source_url": KEY_URL,
            "key_trust": "HTTPS_PROVIDER_KEYRING_NOT_INDEPENDENTLY_PINNED",
            "observed_at": observed_at,
            "source_at": print_data.get("at"),
            "raw_payload_sha256": hashlib.sha256(raw).hexdigest(),
            "keyring_sha256": hashlib.sha256(key_raw).hexdigest(),
            "verification": verification,
            "policy": POLICY,
            "decision": "REVIEW" if eligible else "ABSTAIN",
            "decision_reasons": sorted(set(reasons)),
            "local_signature_claimed": False,
        }
        return {
            "status": body["decision"], "truth_label": "REPORTED", "symbol": symbol,
            "price_text": print_data.get("priceText") if eligible else None,
            "provider_print": print_data,
            "verification": verification,
            "decision_reasons": body["decision_reasons"],
            "receipt": {**body, "receipt_id": sha256_json(body), "receipt_algorithm": "SHA-256"},
            "trading_enabled": False, "capital_transferred": False, "can_authorize": False,
        }


CLIENT = SignedPriceClient()

def envelope(environ, result, *, modeled=False):
    revision = source_revision(environ)
    if revision == "UNBOUND":
        raise FinanceError("CANONICAL_SOURCE_UNBOUND")
    body = {"schema": "szl.finance.signed-price/v1", "source_revision": revision,
        "component": COMPONENT, "ok": True, "state": "MODELED" if modeled else result["status"],
        "truth_label": "MODELED" if modeled else "REPORTED", "execution_enabled": False,
        "advisory_only": True, "result": result}
    receipt = {"schema": "szl.finance.signed-price-receipt/v1", "signing": "UNSIGNED_HONEST",
        "signed": False, "authority": "NONE", "persistence": "CALLER_HELD",
        "source_revision": revision, "payload_sha256": sha256_json(body)}
    receipt["receipt_sha256"] = sha256_json(receipt)
    return {**body, "receipt": receipt}
