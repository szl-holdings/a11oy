from __future__ import annotations

import importlib.util
import json
import math
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build_public_source_of_truth.py"
SPEC = importlib.util.spec_from_file_location("build_public_source_of_truth", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PublicSourceOfTruthTests(unittest.TestCase):
    def build(self, observations=None, verified=True):
        return MODULE.build_snapshot(
            observations=observations or {},
            generated_at="2026-08-11T00:00:00Z",
            source_revision="a" * 40,
            contract_verified=verified,
        )

    def test_missing_external_metrics_are_unavailable_not_stale(self):
        snapshot = self.build()
        for section in snapshot["inventory"].values():
            for metric in section.values():
                self.assertEqual(metric["label"], "UNAVAILABLE")
                self.assertIsNone(metric["value"])
                self.assertIsNone(metric["observed_at"])
        self.assertEqual(snapshot["state"], "DEGRADED")

    def test_fresh_measured_metric_is_preserved(self):
        snapshot = self.build(
            {
                "inventory": {
                    "github": {
                        "public_repositories": {
                            "value": 58,
                            "label": "MEASURED",
                            "observed_at": "2026-08-11T00:00:00Z",
                            "source": "github-api",
                        }
                    }
                }
            }
        )
        metric = snapshot["inventory"]["github"]["public_repositories"]
        self.assertEqual(metric["value"], 58)
        self.assertEqual(metric["label"], "MEASURED")

    def test_metric_without_nonblank_source_fails_closed(self):
        for source in (None, "", "   "):
            with self.subTest(source=source):
                snapshot = self.build(
                    {
                        "inventory": {
                            "github": {
                                "public_repositories": {
                                    "value": 58,
                                    "label": "MEASURED",
                                    "observed_at": "2026-08-11T00:00:00Z",
                                    "source": source,
                                }
                            }
                        }
                    }
                )
                metric = snapshot["inventory"]["github"]["public_repositories"]
                self.assertEqual(metric["label"], "UNAVAILABLE")
                self.assertIsNone(metric["value"])

    def test_metric_without_timestamp_fails_closed(self):
        snapshot = self.build(
            {
                "inventory": {
                    "huggingface": {
                        "spaces_total": {
                            "value": 27,
                            "label": "MEASURED",
                            "source": "hf-api",
                        }
                    }
                }
            }
        )
        metric = snapshot["inventory"]["huggingface"]["spaces_total"]
        self.assertEqual(metric["label"], "UNAVAILABLE")
        self.assertIsNone(metric["value"])

    def test_non_finite_metric_fails_closed(self):
        for value in (math.nan, math.inf, -math.inf, {"nested": math.nan}):
            with self.subTest(value=value):
                snapshot = self.build(
                    {
                        "inventory": {
                            "github": {
                                "public_repositories": {
                                    "value": value,
                                    "label": "MEASURED",
                                    "observed_at": "2026-08-11T00:00:00Z",
                                    "source": "github-api",
                                }
                            }
                        }
                    }
                )
                metric = snapshot["inventory"]["github"]["public_repositories"]
                self.assertEqual(metric["label"], "UNAVAILABLE")

    def test_stale_future_and_malformed_metrics_fail_closed(self):
        for observed_at in (
            "2026-08-10T23:44:59Z",
            "2026-08-11T00:01:01Z",
            "not-a-timestamp",
            "2026-08-11T00:00:00",
        ):
            with self.subTest(observed_at=observed_at):
                snapshot = self.build(
                    {
                        "inventory": {
                            "github": {
                                "public_repositories": {
                                    "value": 58,
                                    "label": "MEASURED",
                                    "observed_at": observed_at,
                                    "source": "github-api",
                                }
                            }
                        }
                    }
                )
                metric = snapshot["inventory"]["github"]["public_repositories"]
                self.assertEqual(metric["label"], "UNAVAILABLE")
                self.assertIsNone(metric["value"])

    def test_nonterminal_runtime_observation_fails_closed(self):
        snapshot = self.build(
            {
                "runtime": {
                    "a11oy": {
                        "state": "CHECKING",
                        "observed_at": "2026-08-11T00:00:00Z",
                        "source": "test",
                    }
                }
            }
        )
        self.assertEqual(snapshot["runtime"]["a11oy"]["state"], "UNAVAILABLE")

    def test_only_verified_runtime_observations_allow_verified_aggregate(self):
        inventory = {
            "github": {
                name: {
                    "value": 1,
                    "label": "MEASURED",
                    "observed_at": "2026-08-11T00:00:00Z",
                    "source": "github-api",
                }
                for name in ("public_repositories", "active_repositories", "archived_repositories")
            },
            "huggingface": {
                name: {
                    "value": 1,
                    "label": "MEASURED",
                    "observed_at": "2026-08-11T00:00:00Z",
                    "source": "hf-api",
                }
                for name in ("spaces_total", "spaces_public", "models", "datasets", "kernels", "collections", "buckets")
            },
        }
        for state in ("REACHABLE", "DEGRADED", "STALE", "FAILED", "BLOCKED", "UNAVAILABLE"):
            with self.subTest(state=state):
                snapshot = self.build(
                    {
                        "inventory": inventory,
                        "runtime": {
                            "a11oy": {
                                "state": state,
                                "observed_at": "2026-08-11T00:00:00Z",
                                "source": "runtime-probe",
                            }
                        },
                    }
                )
                self.assertEqual(snapshot["state"], "DEGRADED")

        snapshot = self.build(
            {
                "inventory": inventory,
                "runtime": {
                    "a11oy": {
                        "state": "VERIFIED",
                        "observed_at": "2026-08-11T00:00:00Z",
                        "source": "runtime-probe",
                    }
                },
            }
        )
        self.assertEqual(snapshot["state"], "VERIFIED")

    def test_lambda_contract_is_fixed(self):
        snapshot = self.build()
        self.assertEqual(snapshot["doctrine"]["lambda_uniqueness"]["label"], "CONJECTURE")
        self.assertEqual(snapshot["doctrine"]["lambda_uniqueness"]["name"], "Conjecture 1")
        self.assertEqual(snapshot["doctrine"]["lambda_uniqueness"]["limitation"], MODULE.LAMBDA_LIMITATION)

    def test_validator_enforces_locked_doctrine(self):
        for field, value, error in (
            ("state", "UNLOCKED", "doctrine_state"),
            ("version", "v10", "doctrine_version"),
        ):
            with self.subTest(field=field):
                snapshot = self.build()
                snapshot["doctrine"][field] = value
                snapshot["digest_sha3_256"] = MODULE.digest_snapshot(snapshot)
                self.assertIn(error, MODULE.validate_snapshot(snapshot))

    def test_validator_enforces_lambda_limitation(self):
        snapshot = self.build()
        snapshot["doctrine"]["lambda_uniqueness"]["limitation"] = "Verified theorem."
        snapshot["digest_sha3_256"] = MODULE.digest_snapshot(snapshot)
        self.assertIn("lambda_uniqueness_limitation", MODULE.validate_snapshot(snapshot))

    def test_verified_state_requires_public_contract_evidence(self):
        self.assertEqual(MODULE.expected_aggregate_state({}, {}, "a" * 40), "DEGRADED")

    def test_verified_state_requires_source_revision(self):
        snapshot = self.build()
        snapshot["source_revision"] = None
        snapshot["state"] = "VERIFIED"
        snapshot["digest_sha3_256"] = MODULE.digest_snapshot(snapshot)
        self.assertIn("aggregate_state", MODULE.validate_snapshot(snapshot))

    def test_validator_recomputes_runtime_aggregate(self):
        snapshot = self.build()
        snapshot["runtime"]["public_contract"]["state"] = "STALE"
        snapshot["state"] = "VERIFIED"
        snapshot["digest_sha3_256"] = MODULE.digest_snapshot(snapshot)
        self.assertIn("aggregate_state", MODULE.validate_snapshot(snapshot))

    def test_digest_is_deterministic(self):
        first = self.build()
        second = self.build()
        self.assertEqual(first["digest_sha3_256"], second["digest_sha3_256"])
        self.assertEqual(MODULE.validate_snapshot(first), [])

    def test_tamper_breaks_digest_validation(self):
        snapshot = self.build()
        snapshot["doctrine"]["state"] = "UNLOCKED"
        self.assertIn("digest_sha3_256", MODULE.validate_snapshot(snapshot))

    def test_validator_rejects_stale_unavailable_value(self):
        snapshot = self.build()
        snapshot["inventory"]["github"]["public_repositories"]["value"] = 58
        snapshot["digest_sha3_256"] = MODULE.digest_snapshot(snapshot)
        self.assertIn("stale_unavailable_metric", MODULE.validate_snapshot(snapshot))

    def test_validator_executes_canonical_json_schema(self):
        snapshot = self.build()
        snapshot["state"] = "BOGUS"
        snapshot["digest_sha3_256"] = MODULE.digest_snapshot(snapshot)
        self.assertIn("json_schema:state", MODULE.validate_snapshot(snapshot))

        snapshot = self.build()
        del snapshot["claim_classes"]
        snapshot["digest_sha3_256"] = MODULE.digest_snapshot(snapshot)
        self.assertIn("json_schema:root", MODULE.validate_snapshot(snapshot))

    def test_cli_round_trip_contract(self):
        snapshot = self.build()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "truth.json"
            path.write_text(json.dumps(snapshot), encoding="utf-8")
            loaded = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(MODULE.validate_snapshot(loaded), [])


if __name__ == "__main__":
    unittest.main()
