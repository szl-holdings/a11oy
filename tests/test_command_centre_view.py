# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Pure renderer, immutable public projection and retained-client contracts."""

import copy
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import runpy

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from routers import command_centre as centre
from routers import command_centre_view as view


class Page(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.ids = {}
        self.duplicates = []
        self.links = []
        self.scripts = []
        self.tags = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        attrs = dict(attrs)
        if 'id' in attrs:
            if attrs['id'] in self.ids:
                self.duplicates.append(attrs['id'])
            self.ids[attrs['id']] = (tag, attrs)
        if tag == 'a':
            self.links.append(attrs.get('href'))
        if tag == 'script':
            self.scripts.append(attrs)


@pytest.fixture
def client():
    app = FastAPI()
    centre.register(app)
    return TestClient(app)


@pytest.fixture
def contract():
    return json.loads(centre.PUBLIC_ESTATE.read_bytes())


def install_contract(tmp_path, monkeypatch, value):
    path = tmp_path / 'public.json'
    path.write_text(json.dumps(value), encoding='utf-8')
    monkeypatch.setattr(centre, 'PUBLIC_ESTATE', path)
    return path


def test_retained_forms_client_ids_and_navigation_are_preserved():
    legacy = Page((centre.ROOT / 'index.html').read_text(encoding='utf-8'))
    current = Page(centre.page_bytes().decode())
    assert not current.duplicates
    assert set(legacy.ids) <= set(current.ids)
    assert set(legacy.links) <= set(current.links)
    for identity, (tag, attrs) in legacy.ids.items():
        if tag in {'form', 'input', 'select', 'textarea', 'button'}:
            current_tag, current_attrs = current.ids[identity]
            assert current_tag == tag
            for key in ('type', 'maxlength', 'required', 'readonly', 'autocomplete'):
                assert current_attrs.get(key) == attrs.get(key)
    script = (centre.ROOT / 'app.js').read_text(encoding='utf-8')
    assert set(re.findall(r"el\('([^']+)'\)", script)) <= set(current.ids)
    assert current.scripts == [{'src': '/command-centre/app.js', 'defer': None}]
    assert all('disabled' in current.ids[name][1] for name in ('send', 'local-send', 'cpu-send'))
    assert len([entry for entry in current.ids.values() if entry[0] == 'form']) == 3


def test_existing_manifest_surfaces_render_without_javascript():
    current = Page(centre.page_bytes().decode())
    assert all(row[2] in current.links for row in centre.SURFACES)


def test_page_and_manifest_get_do_not_contact_provider_or_sign(monkeypatch, client):
    def forbidden(*_args, **_kwargs):
        raise AssertionError('rendering must not perform network work')
    monkeypatch.setattr(centre, 'http_json', forbidden)
    monkeypatch.setattr(centre, 'proof_inventory', forbidden)
    for path in ('/command-centre', '/a11oy/atelier', '/api/a11oy/v1/command-centre/manifest'):
        assert client.get(path).status_code == 200
        assert client.head(path).status_code == 200
    # Pure presentation has no imported provider, state, request, or signer API.
    assert not any(name.startswith(('http', 'requests', 'sqlite', 'gdw', 'szl_', 'os', 'pathlib'))
                   for name in view.__dict__ if not name.startswith('_'))


def test_source_files_never_read_retained_html(monkeypatch):
    original = centre._bounded_source
    calls = []
    def bounded(path, *args):
        calls.append(Path(path))
        assert Path(path).name != 'index.html'
        return original(path, *args)
    monkeypatch.setattr(centre, '_bounded_source', bounded)
    assert centre.page_bytes().startswith(b'<!doctype html>')
    assert any(path.name == 'command_centre_view.py' for path in calls)


def test_presentation_sources_hash_exact_bytes():
    sources = centre.presentation_sources()
    assert len(sources) == 6
    root = Path(centre.__file__).resolve().parents[1]
    for relative, digest in sources.items():
        assert hashlib.sha256((root / relative).read_bytes()).hexdigest() == digest


def test_runtime_public_contract_and_renderer_are_in_docker_sources():
    root = Path(centre.__file__).resolve().parents[1]
    guard = runpy.run_path(str(root / 'tools' / 'check_copy_sync_lockstep.py'))
    sources, _skipped = guard['collect_copy_sources']((root / 'Dockerfile').read_text(encoding='utf-8'))
    normalized = {guard['normalize_repo_path'](source) for source, _instruction in sources}
    # The contract is an explicit deployment input, not an incidental broad COPY.
    assert 'static/shared/public-estate-contract.v1.json' in normalized
    renderer = 'routers/command_centre_view.py'
    assert any(renderer in guard['expand_source_to_files'](str(root), source)[0]
               for source in normalized if source == renderer or source.rstrip('/') == 'routers')


def test_text_and_attributes_are_never_markup():
    attack = '<img src=x onerror="alert(1)"><script>oops</script>&'
    result = view.node('p', attack, aria_label=attack).render()
    parsed = Page(result)
    assert parsed.tags == ['p']
    assert '&lt;img' in result
    assert '&quot;alert(1)&quot;' in result


def test_dynamic_surface_text_is_escaped():
    model = centre.manifest()
    model['surfaces'][0]['title'] = '<svg onload=alert(1)>'
    model['surfaces'][0]['boundary'] = '</a><script>bad()</script>'
    output = view.render_page(model).decode()
    assert '&lt;svg onload=alert(1)&gt;' in output
    assert '</a><script>bad()' not in output
    assert Page(output).scripts == [{'src': '/command-centre/app.js', 'defer': None}]


@pytest.mark.parametrize('href', [
    '', None, 5, 'javascript:alert(1)', 'data:text/html,evil', 'http://github.com',
    '//evil.example', '/\\evil.example', '/%2f%2fevil.example', '/a/../b', '/a/./b',
    'https://github.com.evil.example/a', 'https://github.com@evil.example/a',
    'https://github.com:443/a', 'https://GITHUB.com/a', 'https://github.com/a\nb',
    'https://github.com/a b', '/\t/evil', '#<script>', 'https://evil.example',
    '/x\x00y', '/x\x7fy', '/a\u2028b', '/"onclick="bad', '/x' + 'a' * 2048,
])
def test_unsafe_or_ambiguous_link_is_rejected(href):
    with pytest.raises(ValueError):
        view.safe_href(href)


@pytest.mark.parametrize('href', ['/command-centre', '/console?view=command', '#work',
    'https://github.com/szl-holdings/a11oy', 'https://a11oy.net/estate/',
    'https://huggingface.co/SZLHOLDINGS?type=model'])
def test_allowlisted_links(href):
    assert view.safe_href(href) == href


@pytest.mark.parametrize('tag,attrs', [('img', {}), ('p', {'onclick': 'bad'}),
    ('p', {'style': 'bad'}), ('script', {'src': 'https://github.com/bad'}),
    ('script', {'src': '/other.js'}), ('a', {'href': '//bad'})])
def test_unapproved_component_or_attribute_is_rejected(tag, attrs):
    with pytest.raises(ValueError):
        view.node(tag, **attrs)


def test_inline_script_cannot_be_constructed():
    with pytest.raises(ValueError):
        view.node('script', 'alert(1)')
    with pytest.raises(ValueError):
        view.node('script', 'alert(1)', src='/command-centre/app.js')


def test_canonical_public_projection_is_narrow_and_unpromoted():
    result = centre.public_estate()
    assert result['state'] == 'SOURCE_CONTRACT'
    assert result['ayllu'] == {
        'id': 'SZLHOLDINGS/ayllu', 'classification': 'INVENTORY_ONLY',
        'governedKeep': False, 'disposition': 'FOLD',
        'policySource': 'docs/series-a/hf-space-keep-list.yaml',
        'href': 'https://huggingface.co/spaces/SZLHOLDINGS/ayllu',
    }
    assert 'publicDomainBodies' not in result
    assert 'supportingSystems' not in result
    assert 'internalEngines' not in result
    assert 'inventoryOnlyHuggingFaceRepositories' not in result


def test_extra_unprojected_input_never_leaks(tmp_path, monkeypatch, contract, client):
    contract['private_inventory'] = [{'name': 'DO_NOT_EXPOSE_PRIVATE_NAME', 'token': 'DO_NOT_EXPOSE_PRIVATE_VALUE'}]
    contract['inventoryOnlyHuggingFaceRepositories'][0]['private_metadata'] = 'DO_NOT_EXPOSE_PRIVATE_METADATA'
    install_contract(tmp_path, monkeypatch, contract)
    assert centre.public_estate()['state'] == 'SOURCE_CONTRACT'
    for path in ('/command-centre', '/api/a11oy/v1/command-centre/manifest'):
        response = client.get(path)
        assert response.status_code == 200
        assert 'DO_NOT_EXPOSE' not in response.text
        assert 'private_inventory' not in response.text


@pytest.mark.parametrize('field,value', [
    ('classification', 'LIVE'), ('disposition', 'KEEP'), ('governedKeep', True),
    ('governedKeep', 0), ('policySource', '../private.json'),
])
def test_ayllu_cannot_be_promoted_by_binding(tmp_path, monkeypatch, contract, field, value):
    contract['inventoryOnlyHuggingFaceRepositories'][0][field] = value
    install_contract(tmp_path, monkeypatch, contract)
    assert centre.public_estate()['state'] == 'UNAVAILABLE'


@pytest.mark.parametrize('change', ['schema', 'version', 'canonical', 'authority', 'duplicate', 'missing', 'overlap', 'invalid-topology', 'fabric', 'null'])
def test_malformed_public_binding_fails_closed(tmp_path, monkeypatch, contract, change, client):
    if change == 'schema':
        contract['schema'] = 'private/v1'
    elif change == 'version':
        contract['version'] = '2.0.0'
    elif change == 'canonical':
        contract['canonical']['source'] = 'https://github.com.evil.example/DO_NOT_EXPOSE'
    elif change == 'authority':
        contract['authority']['productionAuthorization'] = 0
    elif change == 'duplicate':
        contract['inventoryOnlyHuggingFaceRepositories'].append(copy.deepcopy(contract['inventoryOnlyHuggingFaceRepositories'][0]))
    elif change == 'missing':
        contract['inventoryOnlyHuggingFaceRepositories'].pop(0)
    elif change == 'overlap':
        contract['laboratorySurfaces'].append('SZLHOLDINGS/ayllu')
    elif change == 'invalid-topology':
        contract['publicDomainBodies'] = [{'huggingFaceRepositories': 'SZLHOLDINGS/ayllu'}]
    elif change == 'fabric':
        contract['fabric']['githubRepository'] = 'private/DO_NOT_EXPOSE'
    else:
        contract = None
    install_contract(tmp_path, monkeypatch, contract)
    result = centre.public_estate()
    assert result['state'] == 'UNAVAILABLE'
    assert result['canonical'] is None and result['ayllu'] is None
    page = client.get('/command-centre')
    assert page.status_code == 200
    assert 'Ownership binding unavailable' in page.text
    assert 'DO_NOT_EXPOSE' not in page.text
    assert 'Ayllu · inventory only' not in page.text


@pytest.mark.parametrize('body', [b'{"schema":"szl.public-estate/v1","schema":"private"}',
    b'{"value":NaN}', b'{"value":Infinity}', b'[]', b'\xff', b'{' * 2000, b' ' * 65537])
def test_invalid_duplicate_nonfinite_oversized_binding(tmp_path, monkeypatch, body):
    path = tmp_path / 'public.json'
    path.write_bytes(body)
    monkeypatch.setattr(centre, 'PUBLIC_ESTATE', path)
    assert centre.public_estate()['state'] == 'UNAVAILABLE'


@pytest.mark.parametrize('kind', ['missing', 'directory', 'symlink'])
def test_missing_or_nonregular_binding_fails_closed(tmp_path, monkeypatch, kind):
    path = tmp_path / 'binding'
    if kind == 'directory':
        path.mkdir()
    elif kind == 'symlink':
        path.symlink_to(centre.PUBLIC_ESTATE)
    monkeypatch.setattr(centre, 'PUBLIC_ESTATE', path)
    assert centre.public_estate()['state'] == 'UNAVAILABLE'


def test_render_reproducible_from_model_and_input_digest_changes():
    model = centre.manifest()
    before = view.render_page(model)
    assert before == view.render_page(copy.deepcopy(model))
    model['source_revision'] = 'a' * 40
    after = view.render_page(model)
    assert before != after
    assert re.search(rb'data-view-input-sha256="([a-f0-9]{64})"', before).group(1) != re.search(rb'data-view-input-sha256="([a-f0-9]{64})"', after).group(1)


@pytest.mark.parametrize('model', [None, [], {}, {'schema': 'private/v1'},
    {'schema': 'szl.command-centre/v1', 'large': 'x' * 65537}])
def test_bad_or_oversized_page_model_rejected(model):
    with pytest.raises(ValueError):
        view.render_page(model)
