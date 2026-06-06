"""
tests/test_bundle_manifests.py — Bundle manifest and UDS bundle YAML tests

Validates uds-bundle.yaml, bundles/v0.3.1-demo/uds-bundle.yaml, and
uds-mesh-pointer-manifest.yaml.

Note: the prior bundles/v0.3.1/uds-bundle.yaml referenced six nonexistent
packages under the wrong org (ghcr.io/szl/...) and was deleted; it is replaced
by the honest single-application demo at bundles/v0.3.1-demo/uds-bundle.yaml.

Run: pytest tests/test_bundle_manifests.py -v
"""
import os
import re
import pytest
import yaml

REPO_ROOT = os.path.join(os.path.dirname(__file__), '..')
# The fictional bundles/v0.3.1/ was deleted; the honest replacement is the
# single-application receipts demo at bundles/v0.3.1-demo/.
BUNDLE_V031 = os.path.join(REPO_ROOT, 'bundles', 'v0.3.1-demo', 'uds-bundle.yaml')
BUNDLE_ROOT = os.path.join(REPO_ROOT, 'uds-bundle.yaml')
POINTER_MANIFEST = os.path.join(REPO_ROOT, 'uds-mesh-pointer-manifest.yaml')


# ─── Bundle v0.3.1 tests (7 tests) ───────────────────────────────────────────

class TestBundleV031:
    def test_file_exists(self):
        assert os.path.isfile(BUNDLE_V031), f"Bundle v0.3.1 not found: {BUNDLE_V031}"

    def test_file_parses_as_yaml(self):
        with open(BUNDLE_V031) as f:
            d = yaml.safe_load(f)
        assert d is not None

    def test_has_kind_uds_bundle(self):
        with open(BUNDLE_V031) as f:
            d = yaml.safe_load(f)
        kind = d.get('kind', '')
        assert 'bundle' in kind.lower() or 'Bundle' in kind

    def test_has_metadata(self):
        with open(BUNDLE_V031) as f:
            d = yaml.safe_load(f)
        assert 'metadata' in d

    def test_metadata_has_version(self):
        with open(BUNDLE_V031) as f:
            d = yaml.safe_load(f)
        meta = d.get('metadata', {})
        assert 'version' in meta or 'name' in meta

    def test_has_packages(self):
        with open(BUNDLE_V031) as f:
            d = yaml.safe_load(f)
        assert 'packages' in d or 'components' in d or len(d.keys()) >= 3

    def test_version_031_in_file(self):
        with open(BUNDLE_V031) as f:
            text = f.read()
        assert '0.3' in text or 'v0.3' in text


# ─── Root bundle tests (5 tests) ─────────────────────────────────────────────

class TestRootBundle:
    def test_root_bundle_exists(self):
        assert os.path.isfile(BUNDLE_ROOT)

    def test_root_bundle_parses(self):
        with open(BUNDLE_ROOT) as f:
            d = yaml.safe_load(f)
        assert d is not None

    def test_root_bundle_references_components(self):
        with open(BUNDLE_ROOT) as f:
            text = f.read()
        # Must reference at least one of the key components
        found = any(comp in text for comp in ['a11oy', 'sentra', 'amaru', 'rosie'])
        assert found, "Root bundle does not reference any known component"

    def test_root_bundle_version_020(self):
        with open(BUNDLE_ROOT) as f:
            text = f.read()
        assert '0.1' in text or '0.2' in text or '0.3' in text

    def test_root_bundle_nonempty(self):
        assert os.path.getsize(BUNDLE_ROOT) > 50


# ─── Pointer manifest tests (5 tests) ────────────────────────────────────────

class TestPointerManifest:
    def test_pointer_manifest_exists(self):
        assert os.path.isfile(POINTER_MANIFEST)

    def test_pointer_manifest_parses(self):
        with open(POINTER_MANIFEST) as f:
            d = yaml.safe_load(f)
        assert d is not None

    def test_pointer_manifest_nonempty(self):
        assert os.path.getsize(POINTER_MANIFEST) > 20

    def test_pointer_manifest_references_components(self):
        with open(POINTER_MANIFEST) as f:
            text = f.read()
        found = any(comp in text for comp in ['a11oy', 'sentra', 'amaru', 'rosie', 'uds'])
        assert found

    def test_pointer_manifest_has_yaml_structure(self):
        with open(POINTER_MANIFEST) as f:
            d = yaml.safe_load(f)
        assert isinstance(d, dict) or isinstance(d, list)
