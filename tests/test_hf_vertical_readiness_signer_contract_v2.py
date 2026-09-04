#!/usr/bin/env python3
"""Regression tests for the public combined-runtime readiness verifier."""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "hf_publish_vertical_services.py"
SPEC = importlib.util.spec_from_file_location("hf_publish_vertical_services", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class VerticalReadinessSignerContractV2Tests(unittest.TestCase):
    def ready_payload(self) -> dict:
        return {
            "ready": True,
            "service": "szl-vertical-services",
            "version": "2.0.0",
            "build": {
                "state": "OBSERVED",
                "revision": MODULE.SOURCE_REVISION,
            },
            "verticals": {
                name: {
                    "ready": True,
                    "status": "READY",
                    "requirements": {
                        "formula_registry_bound": True,
                        "observation_store_writable": True,
                        "persistent_signing_key": True,
                        "required_connector_contracts_ready": True,
                        "source_bound": True,
                    },
                    "live_data": {
                        "wired": True,
                        "observed_in_scope": False,
                        "connectors_observed": 0,
                        "observations": 0,
                    },
                }
                for name in MODULE.EXPECTED_VERTICALS
            },
        }

    def build_payload(self) -> dict:
        return {
            "schema": "szl.build-info/v1",
            "service": "szl-vertical-services",
            "version": "2.0.0",
            "source_repository": MODULE.SOURCE_REPOSITORY,
            "build": {
                "state": "OBSERVED",
                "revision": MODULE.SOURCE_REVISION,
            },
            "source_binding": {
                "evidence_sources": ["adjacent-file", "container-file", "env"],
                "bindings_agree": True,
            },
            "receipt_minted": False,
            "truth_label": "MEASURED",
        }

    def test_accepts_actual_v2_readiness_without_secret_source_field(self) -> None:
        ready = self.ready_payload()
        self.assertNotIn("sentra_signing_key_source", ready)
        self.assertTrue(MODULE.persistent_signer_ready(ready))

        with patch.object(
            MODULE,
            "get_json",
            side_effect=[(200, ready), (200, self.build_payload())],
        ):
            proof = MODULE.verify_contract()

        self.assertTrue(proof["persistent_signer_ready"])
        self.assertTrue(proof["complete"])
        self.assertEqual(
            proof["expected_verticals"],
            sorted(MODULE.EXPECTED_VERTICALS),
        )

    def test_rejects_missing_extra_or_unready_engine(self) -> None:
        missing = self.ready_payload()
        missing["verticals"].pop("sentra")
        self.assertFalse(MODULE.persistent_signer_ready(missing))

        extra = self.ready_payload()
        extra["verticals"]["vessels"] = dict(extra["verticals"]["killinchu"])
        self.assertFalse(MODULE.persistent_signer_ready(extra))

        unready = self.ready_payload()
        unready["verticals"]["terra"]["ready"] = False
        self.assertFalse(MODULE.persistent_signer_ready(unready))

    def test_rejects_absent_or_false_persistent_signer_requirement(self) -> None:
        absent = self.ready_payload()
        absent["verticals"]["counsel"]["requirements"].pop(
            "persistent_signing_key"
        )
        self.assertFalse(MODULE.persistent_signer_ready(absent))

        false = self.ready_payload()
        false["verticals"]["finance"]["requirements"][
            "persistent_signing_key"
        ] = False
        self.assertFalse(MODULE.persistent_signer_ready(false))


if __name__ == "__main__":
    unittest.main(verbosity=2)
