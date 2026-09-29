#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""The research handoff is a fixed navigation target, with no data or actions."""
from fastapi import FastAPI
from fastapi.testclient import TestClient

import a11oy_frontier_page


def test_research_handoff_is_fixed_and_page_preserves_failed_result():
    app = FastAPI()
    a11oy_frontier_page.register(app)
    client = TestClient(app)
    response = client.get('/research/confirmation?url=https://example.invalid', follow_redirects=False)
    assert response.status_code == 307
    assert response.headers['location'] == 'https://a11oy.net/experiments/confirmation/'
    assert not response.headers.get('set-cookie')
    page = client.get('/frontier').text
    assert 'href="/research/confirmation"' in page
    assert 'clean-sensor guard and overall registered gate failed' in page
    assert 'The learned selector did not outperform the strongest simple control' in page
    assert 'https://' not in page and 'http://' not in page
