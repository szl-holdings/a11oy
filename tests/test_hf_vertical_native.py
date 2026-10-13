# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Native rendering must preserve functional bytes and the original Forge seal."""
import base64
import hashlib
from html.parser import HTMLParser
from pathlib import Path
import re
import shutil

import pytest

from tests.test_hf_publish_vertical_flagships_v4 import load_overlay


class Tags(HTMLParser):
    def __init__(self, text):
        super().__init__(); self.tags = []; self.feed(text)
    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


def test_all_four_native_pages_preserve_every_script_and_form():
    module = load_overlay()
    present = module._native_module.present
    for item in module.FLAGSHIPS:
        page = module.html(item)
        module._native_module.present = lambda html, slug: html
        try:
            original = module.html(item)
        finally:
            module._native_module.present = present
        assert re.findall(r'<script\b[^>]*>.*?</script>', page, re.S) == re.findall(r'<script\b[^>]*>.*?</script>', original, re.S)
        assert re.findall(r'<form\b.*?</form>', page, re.S) == re.findall(r'<form\b.*?</form>', original, re.S)
        if item['slug'] in module._native_module.SLUGS:
            tags = Tags(page).tags
            assert len([t for t,a in tags if t == 'main']) == 1
            assert any(t == 'nav' and a.get('aria-label') == 'Workspace sections' for t,a in tags)
            assert any(a.get('id') == 'st' and a.get('role') == 'status' and a.get('aria-live') == 'polite' for t,a in tags)
            assert 'JavaScript is disabled. No runtime observation has been made' in page
            assert 'Trademark notice' in page
            assert 'data-iris="closed"' in page if item['slug'] == 'sentra' else True
        else:
            assert page == original


def test_native_art_and_token_prefix_are_exact_existing_sources():
    module = load_overlay(); native = module._native_module
    tokens, uri = native.assets()
    source = (native.ROOT / 'console/assets/szl/szl-design-system.css').read_text()
    assert tokens == source.split(native.TOKEN_END, 1)[0]
    assert base64.b64decode(uri.split(',',1)[1]) == (native.ROOT / 'console/assets/szl/orbit-v2/szl-icon-32.svg').read_bytes()
    page = module.html(next(x for x in module.FLAGSHIPS if x['slug'] == 'finance'))
    ids = {a.get('id') for t,a in Tags(page).tags}
    for t,a in Tags(page).tags:
        if t == 'a' and a.get('href','').startswith('#'):
            assert a['href'][1:] in ids


def test_terra_derivation_retains_exact_original_chain_and_binds_output():
    module = load_overlay()
    original, chain = module.load_terra_forge_bundle()
    derived, record = module.load_terra_native_landing()
    assert original == Path('deployments/vertical-forge/terra/index.html').read_text()
    assert {k:v for k,v in record.items() if k != 'presentation'} == chain
    assert record['presentation']['base_artifact_sha256'] == chain['artifact_sha256'] == hashlib.sha256(original.encode()).hexdigest()
    assert record['presentation']['derived_landing_sha256'] == hashlib.sha256(derived.encode()).hexdigest()
    assert re.findall(r'<script\b[^>]*>.*?</script>', original, re.S) == re.findall(r'<script\b[^>]*>.*?</script>', derived, re.S)
    assert module._BASE.load_terra_forge_bundle() == (derived, record)
    assert 'role="status"' in derived and '<noscript>' in derived
    tags = Tags(derived).tags; ids = {a.get('id') for t,a in tags}
    assert all(a['href'][1:] in ids for t,a in tags if t == 'a' and a.get('href','').startswith('#'))


def test_native_source_fails_closed_on_tamper_and_symlink(tmp_path, monkeypatch):
    native = load_overlay()._native_module
    shutil.copytree(native.ROOT / 'console/assets/szl', tmp_path/'console/assets/szl')
    monkeypatch.setattr(native, 'ROOT', tmp_path)
    target = tmp_path/'console/assets/szl/orbit-v2/szl-icon-32.svg'
    original = target.read_bytes(); target.write_bytes(original + b' ')
    with pytest.raises(ValueError, match='checksum'): native.assets()
    target.unlink(); outside = tmp_path/'outside.svg'; outside.write_bytes(original); target.symlink_to(outside)
    with pytest.raises(OSError): native.assets()


def test_native_insertion_refuses_changed_or_repeated_boundary():
    module = load_overlay(); item = next(x for x in module.FLAGSHIPS if x['slug'] == 'counsel')
    page = module.html(item)
    with pytest.raises(ValueError, match='only be applied once'): module._native_module.present(page, 'counsel')
    with pytest.raises(ValueError, match='boundary changed'): module._native_module.present('<html lang="en"><body></body></html>', 'counsel')
