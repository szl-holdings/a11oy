"""Offline, side-effect-free contract tests for public buyer-journey witness."""

from __future__ import annotations

from datetime import datetime, timezone
from email.message import Message
import io
import unittest
import urllib.error
from unittest.mock import Mock

from scripts import audit_commercial_funnel as watch


class Response(io.BytesIO):
    def __init__(self, url: str, body: bytes, *, content_type="text/html", status=200):
        super().__init__(body)
        self.url = url
        self.status = status
        self.headers = Message()
        self.headers["Content-Type"] = content_type

    def getcode(self):
        return self.status

    def geturl(self):
        return self.url

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class FakeReader:
    def __init__(self, pricing: bytes, denied=()):
        self.calls = []
        self.pricing = pricing
        self.denied = set(denied)

    def __call__(self, request, timeout):
        self.calls.append((request.full_url, request.get_method(), timeout,
                           request.get_header("Authorization")))
        path = request.full_url.removeprefix(watch.ORIGIN)
        if path in self.denied:
            raise urllib.error.HTTPError(request.full_url, 403, "blocked", None, None)
        body = self.pricing if path == "/pricing" else b"{}"
        content_type = "text/html" if path == "/pricing" else "application/json"
        return Response(request.full_url, body, content_type=content_type)


NOW = lambda: datetime(2026, 11, 19, 20, 0, tzinfo=timezone.utc)
PRICING = b'''<main><a href="mailto:hello@a-11-oy.com?subject=Governed%20Evidence%20Pilot">Pilot</a>
<a href="/verify">Sample verifier</a></main>'''


class CommercialWitnessTests(unittest.TestCase):
    def test_mailto_does_not_become_verified_lead_or_cash(self):
        reader = FakeReader(PRICING)
        report = watch.observe(opener=reader, clock=NOW)
        self.assertEqual(report["inquiry_routing_state"], "MAILTO_ONLY_DELIVERY_UNVERIFIED")
        self.assertEqual(report["pricing_calls_to_action"]["pilot_mailto_count"], 1)
        self.assertEqual(report["pricing_calls_to_action"]["verify_link_count"], 1)
        self.assertFalse(report["mailbox_delivery_verified"])
        self.assertFalse(report["paid_customer_conversion_verified"])
        self.assertFalse(report["settled_payment_verified"])
        self.assertEqual(report["production_or_revenue_admission"], "HOLD")
        self.assertEqual(len(reader.calls), len(watch.PATHS))
        self.assertTrue(all(method == "GET" and auth is None and timeout <= 8 for _, method, timeout, auth in reader.calls))

    def test_edge_refusal_is_not_classified_as_missing_page_or_customer_failure(self):
        report = watch.observe(opener=FakeReader(PRICING, denied={"/contact", "/demo"}), clock=NOW)
        self.assertEqual(report["routes"]["/contact"], {"state": "HTTP_REFUSED", "http_status": 403})
        self.assertEqual(report["routes"]["/demo"]["state"], "HTTP_REFUSED")
        self.assertEqual(report["routes"]["/pricing"]["state"], "REACHABLE")

    def test_oversized_page_keeps_intake_unavailable(self):
        report = watch.observe(opener=FakeReader(b"x" * (watch.MAX_RESPONSE_BYTES + 1)), clock=NOW)
        self.assertEqual(report["routes"]["/pricing"]["state"], "OVERSIZE")
        self.assertIsNone(report["pricing_calls_to_action"]["mailto_count"])
        self.assertEqual(report["inquiry_routing_state"], "UNAVAILABLE")

    def test_form_presence_does_not_prove_delivery(self):
        report = watch.observe(opener=FakeReader(b'<form action="/api/leads"><button>Send</button></form>'), clock=NOW)
        self.assertEqual(report["inquiry_routing_state"], "FORM_PRESENT_DELIVERY_UNVERIFIED")
        self.assertFalse(report["form_delivery_verified"])

    def test_missing_calls_to_action_is_explicit(self):
        report = watch.observe(opener=FakeReader(b'<h1>Pricing</h1>'), clock=NOW)
        self.assertEqual(report["inquiry_routing_state"], "NO_VISIBLE_INTAKE")
        self.assertEqual(report["pricing_calls_to_action"]["forms_count"], 0)

    def test_disallow_arbitrary_url_and_source_identity(self):
        with self.assertRaises(ValueError):
            watch.probe("/api/admin")
        with self.assertRaises(ValueError):
            watch.observe(source_revision="main", opener=FakeReader(PRICING), clock=NOW)
        with self.assertRaises(ValueError):
            watch.observe(source_revision="A" * 40, opener=FakeReader(PRICING), clock=NOW)

    def test_no_redirect_followed(self):
        self.assertIsNone(watch.NoRedirect().redirect_request(None, None, 302, "", {}, "https://malicious.example/"))
        reader = Mock(return_value=Response("https://evil.example/", b"trick"))
        result, body = watch.probe("/pricing", opener=reader)
        self.assertEqual(result["state"], "NON_200_OR_REDIRECT")
        self.assertIsNone(body)
        reader.assert_called_once()

    def test_unexpected_content_type_does_not_count_sales_cta(self):
        reader = Mock(return_value=Response(watch.ORIGIN + "/pricing", b"<a href=mailto:test@example.org>Call</a>", content_type="image/svg+xml"))
        result, body = watch.probe("/pricing", opener=reader)
        self.assertEqual(result["state"], "UNSUPPORTED_CONTENT_TYPE")
        self.assertIsNone(body)

    def test_transport_failure_is_unavailable_no_retry(self):
        reader = Mock(side_effect=OSError("PRIVATE_DATA_THAT_MUST_NOT_LEAK"))
        result, body = watch.probe("/pricing", opener=reader)
        self.assertEqual(result, {"state": "UNAVAILABLE", "http_status": None})
        self.assertIsNone(body)
        reader.assert_called_once()

    def test_bad_utf8_is_unavailable_and_not_delivered(self):
        report = watch.observe(opener=FakeReader(b"\xff\xfe"), clock=NOW)
        self.assertEqual(report["inquiry_routing_state"], "UNAVAILABLE")
        self.assertFalse(report["mailbox_delivery_verified"])

    def test_source_binding_and_utc_requirements(self):
        report = watch.observe(opener=FakeReader(PRICING), source_revision="a" * 40, clock=NOW)
        self.assertEqual(report["source_revision"], "a" * 40)
        self.assertEqual(report["source_identity_scope"], "CALLER_DECLARED_NOT_ATTESTED")
        with self.assertRaises(ValueError):
            watch.observe(opener=FakeReader(PRICING), clock=lambda: datetime(2026, 11, 19))


if __name__ == "__main__":
    unittest.main()
