#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""The research handoff is a fixed navigation target, with no data or actions."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

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
    assert 'registered result remains <strong>FAILED</strong>' in page
    assert 'https://' not in page and 'http://' not in page


@pytest.mark.parametrize('query', (
    '',
    '?url=https://example.invalid',
    '?next=//example.invalid&destination=https://example.invalid',
    '?redirect_uri=https%3A%2F%2Fexample.invalid%2F%3Fx%3D1',
    '?url=https%3A%2F%2Fexample.invalid%2F%0D%0AX-Injected%3Ayes',
))
def test_workbench_handoff_has_one_fixed_destination_and_no_cookie(query):
    app = FastAPI()
    a11oy_frontier_page.register(app)
    client = TestClient(app)
    response = client.get('/research/confirmation/workbench' + query, follow_redirects=False)
    assert response.status_code == 307
    assert response.headers['location'] == 'https://szlholdings-szl-foundation-confirmation.hf.space'
    assert not response.headers.get('set-cookie')
    assert not response.headers.get('x-injected')


def test_workbench_link_discloses_execution_and_receipt_scope():
    app = FastAPI()
    a11oy_frontier_page.register(app)
    client = TestClient(app)
    page = client.get('/frontier').text
    assert 'href="/research/confirmation/workbench"' in page
    assert 'Fresh model trials run on demand in a separate synthetic CPU workbench' in page
    assert 'may sleep when idle' in page
    assert 'do not change the frozen experiment or qualify the wider system' in page
    assert 'at most 128 receipts in process memory for up to 24 hours' in page
    assert 'restarting the workbench discards them' in page
    assert 'registered result remains <strong>FAILED</strong>' in page
    assert 'https://' not in page and 'http://' not in page
    assert client.post('/research/confirmation/workbench', json={}).status_code == 405
