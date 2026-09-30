#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Offline invariants for a proposed catalog policy, not a live readiness test."""
import json
from pathlib import Path

import szl_spaces_surface as surface


def decision():
    path = Path(__file__).parents[1] / 'data' / 'space-catalog-admission-decision.json'
    return json.loads(path.read_text(encoding='utf-8'))


def test_production_set_preserves_existing_five_doors():
    value = decision()
    assert value['production_candidates'] == [row['name'] for row in surface.SPACES]
    assert len(set(value['production_candidates'])) == 5
    assert value['runtime_effect'] == 'NONE'
    assert value['production_authorization'] is False
    assert value['public_visibility_authorized'] is False


def test_nonproduction_is_unique_disjoint_and_not_promoted():
    value = decision()
    rows = value['additional_observed_public']
    names = [row['name'] for row in rows]
    assert len(names) == len(set(names)) == 16
    assert set(names).isdisjoint(value['production_candidates'])
    assert all(row['production_eligible'] is False for row in rows)
    assert all(row['classification'] in {'VISIBILITY_REVIEW_REQUIRED', 'RESEARCH_STAGING_UNQUALIFIED'} for row in rows)
    assert next(row for row in rows if row['name'] == 'david-leads')['classification'] == 'VISIBILITY_REVIEW_REQUIRED'
    assert value['unknown_space_policy'] == 'REVIEW_REQUIRED'


def test_promotion_keeps_source_publication_and_runtime_gates_separate():
    assert set(decision()['readiness_required']) == {
        'admitted_source_revision', 'canonical_publisher_readback',
        'deployed_source_binding', 'exact_api_contracts',
        'authentication_and_data_review', 'witnessed_backend_request',
        'required_receipt_verification',
    }
