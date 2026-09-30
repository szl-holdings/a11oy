from __future__ import annotations

import importlib.util
import json
import os
import tempfile
from pathlib import Path
from unittest import TestCase, mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "repair_hf_product_domain.py"
spec = importlib.util.spec_from_file_location("repair", SCRIPT)
assert spec is not None and spec.loader is not None
repair = importlib.util.module_from_spec(spec)
spec.loader.exec_module(repair)


class RepairHfProductDomainTests(TestCase):
    def test_token_alias_order_is_explicit(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                "HF_TOKEN": "fallback",
                "HF_ORG_TOKEN": "preferred",
                "HUGGINGFACEHUB_API_TOKEN": "later",
            },
            clear=True,
        ):
            self.assertEqual(repair.token(), "preferred")

    def test_domain_states_normalizes_runtime_shapes(self) -> None:
        value = {
            "runtime": {
                "domains": [
                    {"domain": "szlholdings-a11oy.hf.space", "stage": "READY"},
                    {"hostname": "www.a-11-oy.com.", "status": "pending_challenge"},
                    "https://a-11-oy.com",
                ]
            }
        }
        self.assertEqual(
            repair.domain_states(value),
            {
                "szlholdings-a11oy.hf.space": "READY",
                "www.a-11-oy.com": "PENDING_CHALLENGE",
                "a-11-oy.com": "UNKNOWN",
            },
        )

    def test_domain_states_accepts_mapping_shape(self) -> None:
        self.assertEqual(
            repair.domain_states(
                {"domains": {"a-11-oy.com": "ready", "native.hf.space": "ready"}}
            ),
            {"a-11-oy.com": "READY", "native.hf.space": "READY"},
        )

    def test_wrong_www_claim_is_replaced_by_apex(self) -> None:
        self.assertEqual(
            repair.mutation_plan(
                {
                    "szlholdings-a11oy.hf.space": "READY",
                    "www.a-11-oy.com": "PENDING_CHALLENGE",
                }
            ),
            ["delete-known-wrong-domain", "submit-desired-domain"],
        )

    def test_absent_claim_submits_apex_and_existing_apex_is_idempotent(self) -> None:
        self.assertEqual(
            repair.mutation_plan({"szlholdings-a11oy.hf.space": "READY"}),
            ["submit-desired-domain"],
        )
        self.assertEqual(
            repair.mutation_plan(
                {
                    "szlholdings-a11oy.hf.space": "READY",
                    "a-11-oy.com": "PENDING",
                }
            ),
            [],
        )

    def test_unexpected_custom_domain_fails_closed(self) -> None:
        with self.assertRaisesRegex(repair.DomainRepairError, "Unexpected"):
            repair.mutation_plan({"attacker.example": "READY"})

    def test_response_summary_never_copies_nested_challenge_values(self) -> None:
        body = json.dumps(
            {
                "domain": "a-11-oy.com",
                "status": "pending",
                "challenge": {"name": "_huggingface", "value": "opaque-token"},
            }
        ).encode()
        summary = repair.response_summary(202, {"content-type": "application/json"}, body)
        self.assertEqual(summary["domain"], "a-11-oy.com")
        self.assertEqual(summary["status"], "pending")
        self.assertNotIn("challenge", summary)
        self.assertNotIn("opaque-token", json.dumps(summary))

    def test_safe_error_is_single_line_bounded_and_redacted(self) -> None:
        secret = "hf_secret_value"
        rendered = repair.safe_error(
            RuntimeError(f"first\nsecond {secret} " + ("x" * 3000)),
            secret,
        )
        self.assertNotIn(secret, rendered)
        self.assertIn("<redacted>", rendered)
        self.assertNotIn("\n", rendered)
        self.assertLessEqual(len(rendered), 2000)

    def test_authenticated_actor_requires_szlholdings_membership(self) -> None:
        body = json.dumps(
            {"name": "operator", "orgs": [{"name": "SZLHOLDINGS"}]}
        ).encode()
        with mock.patch.object(repair, "_request", return_value=(200, {}, body)):
            self.assertEqual(
                repair.authenticated_actor("secret"),
                {"name": "operator", "organizations": ["SZLHOLDINGS"]},
            )
        bad = json.dumps({"name": "operator", "orgs": []}).encode()
        with mock.patch.object(repair, "_request", return_value=(200, {}, bad)):
            with self.assertRaisesRegex(repair.DomainRepairError, "not listed"):
                repair.authenticated_actor("secret")

    def test_public_root_probe_requires_200_no_redirect_and_brand_marker(self) -> None:
        with mock.patch.object(
            repair,
            "_request",
            return_value=(200, {"content-type": "text/html"}, b"<title>A11oy</title>"),
        ):
            self.assertTrue(repair.public_root_probe()["verified"])
        with mock.patch.object(
            repair,
            "_request",
            return_value=(301, {"location": "https://hf.space"}, b""),
        ):
            self.assertFalse(repair.public_root_probe()["verified"])

    def test_missing_token_reports_unavailable_without_secret_or_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report_path = Path(tmp) / "report.json"
            with (
                mock.patch.dict(os.environ, {}, clear=True),
                mock.patch(
                    "sys.argv",
                    [str(SCRIPT), "--report", str(report_path)],
                ),
            ):
                self.assertEqual(repair.main(), 2)
            report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "UNAVAILABLE")
        self.assertFalse(report["token_recorded"])
        self.assertFalse(report["dns_mutated"])
        self.assertFalse(report["cloudflare_mutated"])


if __name__ == "__main__":
    import unittest

    unittest.main()
