# SPDX-License-Identifier: Apache-2.0
"""Regression controls for the real page's shared-shell integration."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = spec_from_file_location('model_pretraining_browser', ROOT / 'scripts/test_model_pretraining_browser.py')
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
STYLE = '<link rel="stylesheet" href="/assets/szl-flow.css" data-szl-flow-asset="style" />'
SCRIPT = '<script src="/assets/szl-flow.js" defer data-szl-flow-asset="script"></script>'
DOCUMENT = '<html><head>' + STYLE + '</head><body>' + SCRIPT + '</body></html>'


class ShellDocumentTests(unittest.TestCase):
    def test_real_page_has_exact_canonical_shell(self):
        page = (ROOT / 'pages/model-pretraining.html').read_text(encoding='utf-8')
        MODULE.validate_shell_document(page)
        self.assertEqual(page.count(STYLE), 1)
        self.assertEqual(page.count(SCRIPT), 1)

    def test_valid_document(self):
        MODULE.validate_shell_document(DOCUMENT)

    def test_missing_stylesheet(self):
        with self.assertRaises(RuntimeError):
            MODULE.validate_shell_document(DOCUMENT.replace(STYLE, ''))

    def test_missing_script(self):
        with self.assertRaises(RuntimeError):
            MODULE.validate_shell_document(DOCUMENT.replace(SCRIPT, ''))

    def test_commented_markers_do_not_pass(self):
        with self.assertRaises(RuntimeError):
            MODULE.validate_shell_document('<!--' + DOCUMENT + '-->')

    def test_duplicate_tag_rejected(self):
        with self.assertRaises(RuntimeError):
            MODULE.validate_shell_document(DOCUMENT + SCRIPT)

    def test_duplicate_attribute_rejected(self):
        with self.assertRaises(RuntimeError):
            MODULE.validate_shell_document(DOCUMENT.replace('defer', 'defer defer'))

    def test_foreign_asset_rejected(self):
        with self.assertRaises(RuntimeError):
            MODULE.validate_shell_document(DOCUMENT.replace('/assets/szl-flow.js', 'https://example.com/x.js'))

    def test_nonstylesheet_rejected(self):
        with self.assertRaises(RuntimeError):
            MODULE.validate_shell_document(DOCUMENT.replace('rel="stylesheet"', 'rel="preload"'))

    def test_nondeferred_script_rejected(self):
        with self.assertRaises(RuntimeError):
            MODULE.validate_shell_document(DOCUMENT.replace(' defer ', ' '))


class ShellTransportTests(unittest.TestCase):
    def test_realistic_css_transport_passes(self):
        result = MODULE.verify_shell_asset('/assets/szl-flow.css', 200, 'text/css; charset=utf-8', b'body{}', b'body{}')
        self.assertEqual(len(result), 64)

    def test_javascript_content_types_pass(self):
        for media in ('text/javascript', 'application/javascript'):
            MODULE.verify_shell_asset('/assets/szl-flow.js', 200, media, b'void 0;', b'void 0;')

    def test_404_does_not_pass(self):
        with self.assertRaises(RuntimeError):
            MODULE.verify_shell_asset('/assets/szl-flow.css', 404, 'text/css', b'body{}', b'body{}')

    def test_redirect_does_not_pass(self):
        with self.assertRaises(RuntimeError):
            MODULE.verify_shell_asset('/assets/szl-flow.css', 302, 'text/css', b'body{}', b'body{}')

    def test_html_fallback_does_not_pass(self):
        with self.assertRaises(RuntimeError):
            MODULE.verify_shell_asset('/assets/szl-flow.js', 200, 'text/html', b'void 0;', b'void 0;')

    def test_changed_bytes_do_not_pass(self):
        with self.assertRaises(RuntimeError):
            MODULE.verify_shell_asset('/assets/szl-flow.css', 200, 'text/css', b'body{ }', b'body{}')

    def test_empty_asset_does_not_pass(self):
        with self.assertRaises(RuntimeError):
            MODULE.verify_shell_asset('/assets/szl-flow.css', 200, 'text/css', b'', b'')

    def test_unexpected_path_does_not_pass(self):
        with self.assertRaises(RuntimeError):
            MODULE.verify_shell_asset('/assets/unreviewed.js', 200, 'text/javascript', b'void 0;', b'void 0;')

    def test_nonbytes_payload_does_not_pass(self):
        with self.assertRaises(RuntimeError):
            MODULE.verify_shell_asset('/assets/szl-flow.css', 200, 'text/css', 'body{}', b'body{}')

    def test_oversized_payload_does_not_pass(self):
        body = b'x' * (2 * 1024 * 1024 + 1)
        with self.assertRaises(RuntimeError):
            MODULE.verify_shell_asset('/assets/szl-flow.css', 200, 'text/css', body, body)


if __name__ == '__main__':
    unittest.main()
