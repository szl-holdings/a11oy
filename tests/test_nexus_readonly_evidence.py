#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Local status-reader regressions; no provider, signer, or runtime is invoked."""
import hashlib
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import szl_khipu
import szl_nexus as nexus


class NexusReadOnlyEvidenceTests(unittest.TestCase):
    def test_status_does_not_create_a_receipt_chain(self):
        with patch.object(szl_khipu, "_REGISTRY", {}):
            nexus.status()
            self.assertEqual(szl_khipu._REGISTRY, {})

    def test_repeated_status_does_not_append_to_existing_chain(self):
        with patch.object(szl_khipu, "_REGISTRY", {}):
            chain = szl_khipu.get_dag("nexus", ns="a11oy")
            chain.emit("unit-test.fixture", {"evidence_class": "SIMULATED"})
            before = chain.tail(chain.depth())
            head = chain.head()
            first = nexus.status()
            second = nexus.status()
            self.assertEqual(chain.tail(chain.depth()), before)
            self.assertEqual(chain.head(), head)
            self.assertEqual(first["khipu_receipt"], second["khipu_receipt"])

    def test_status_digest_is_unsigned_even_with_khipu_installed(self):
        with patch.object(szl_khipu, "_REGISTRY", {}):
            receipt = nexus.status()["khipu_receipt"]
        self.assertIs(receipt["signed"], False)
        self.assertIsNone(receipt["signature"])
        self.assertIs(receipt["proven_trust"], False)
        self.assertEqual(receipt["kind"], "UNSIGNED-honest")
        self.assertIs(receipt["emitted"], False)
        self.assertIs(receipt["chain_verified"], False)

    def test_digest_binds_status_body_without_signature_claim(self):
        payload = {"state": "BIND", "certified": False}
        result = nexus._unsigned_receipt(payload)
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        self.assertEqual(result["digest"], hashlib.sha3_256(canonical).hexdigest())
        self.assertNotEqual(result["digest"], nexus._unsigned_receipt({"state": "OTHER"})["digest"])
        self.assertIs(result["signed"], False)


if __name__ == "__main__":
    unittest.main()
