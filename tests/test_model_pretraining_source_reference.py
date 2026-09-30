# SPDX-License-Identifier: Apache-2.0
"""Native-checkout integration: actual catalog declarations vs actual projector.

Requires the existing product import closure, not an external service. This is
not source ownership, model training or published-runtime qualification.
"""
from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

import test_model_pretraining_live as base


class RepositorySourceReferenceTests(unittest.TestCase):
    def test_actual_source_catalog_matches_the_product_projector(self):
        root = Path(__file__).resolve().parents[1]
        pointers = base.M.declared_source_pointers((root/'a11oy_model_intel.py').read_bytes())
        spec = importlib.util.spec_from_file_location('model_pointer_product', root/'routers/model_pretraining.py')
        product = importlib.util.module_from_spec(spec)
        with patch('httpx.Client.request', side_effect=AssertionError('network not admitted')), \
             patch('httpx.AsyncClient.request', side_effect=AssertionError('network not admitted')):
            spec.loader.exec_module(product)
            cards, state = product.declared_source_cards()
            self.assertEqual(state, 'EXISTING_SERIES_A_CATALOG_SUBSET')
            value = product.project((root/'docs/huggingface-ecosystem-manifest.json').read_bytes(),
                                    cards, now=datetime.now(timezone.utc), product_revision=base.SHA)
        value['sourcePointerCatalogState'] = state
        base.M.validate_source_pointers(value, pointers)
        self.assertFalse(value['sourceAlignmentVerified'])
        self.assertFalse(value['trainingAllowed'])


if __name__ == '__main__': unittest.main()
