# SPDX-License-Identifier: Apache-2.0
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('html_delta', ROOT/'scripts/model_pretraining_html_diagnostics.py')
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)
TAG = b'<script src="/assets/known.js" defer></script>'
PAGE = b'<html><body>reviewed page</body></html>'

class DiagnosticsTests(unittest.TestCase):
    def test_insertion_matches_source_without_body_or_permission(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            source=b'TAG = '+repr(TAG).encode()+b'\n'
            (root/'producer.py').write_bytes(source)
            report=M.describe_delta(root,PAGE,PAGE.replace(b'</body>',TAG+b'</body>'))
            self.assertEqual(report['expectedMiddleBytes'],0)
            self.assertEqual(report['observedMiddleBytes'],len(TAG))
            self.assertEqual(report['matches'][0]['literalSha256'],M.digest(TAG))
            self.assertEqual(report['matches'][0]['sourceFileSha256'],M.digest(source))
            self.assertNotIn('known.js',str(report))
            self.assertFalse(report['transformationAccepted'])
            self.assertFalse(report['responseBodyRecorded'])

    def test_exact_bytes_skip_source_scan(self):
        report=M.describe_delta(Path('/nonexistent'),PAGE,PAGE)
        self.assertEqual(report['state'],'IDENTICAL')
        self.assertFalse(report['transformationAccepted'])

    def test_unknown_dynamic_material_is_hashed_not_leaked(self):
        with tempfile.TemporaryDirectory() as folder:
            report=M.describe_delta(Path(folder),PAGE,PAGE.replace(b'</body>',b'SENSITIVE_DYNAMIC_TEXT</body>'))
            self.assertEqual(report['matches'],[])
            self.assertNotIn('SENSITIVE_DYNAMIC_TEXT',str(report))

    def test_source_side_effects_not_executed(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/'producer.py').write_text("raise RuntimeError('must not execute')\nTAG = "+repr(TAG))
            report=M.describe_delta(root,PAGE,PAGE.replace(b'</body>',TAG+b'</body>'))
            self.assertEqual(len(report['matches']),1)

    def test_malformed_source_reports_incomplete_scan(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); (root/'broken.py').write_bytes(b'\xff')
            report=M.describe_delta(root,PAGE,PAGE+b'x')
            self.assertTrue(report['sourceScanIncomplete'])

    def test_symlink_never_followed(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); (root/'real.py').write_text('X=1')
            with patch.object(Path,'is_symlink',return_value=True):
                report=M.describe_delta(root,PAGE,PAGE+b'x')
            self.assertEqual(report['sourceFilesParsed'],0)
            self.assertTrue(report['sourceScanIncomplete'])

    def test_only_root_python_scanned(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); (root/'.env').write_bytes(TAG)
            sub=root/'nested'; sub.mkdir(); (sub/'secret.py').write_text('TAG='+repr(TAG))
            report=M.describe_delta(root,PAGE,PAGE.replace(b'</body>',TAG+b'</body>'))
            self.assertEqual(report['matches'],[])

    def test_limits_fail_without_scan(self):
        for value in (b'', b'x'*(M.MAX_PAGE+1),'text',None):
            with self.subTest(value_type=type(value).__name__):
                self.assertEqual(M.describe_delta(Path('/nonexistent'),PAGE,value)['state'],'UNAVAILABLE')

    def test_source_byte_limit_is_explicit(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); (root/'large.py').write_bytes(b'x'*100)
            with patch.object(M,'MAX_SOURCE_FILE',16):
                report=M.describe_delta(root,PAGE,PAGE+b'x')
            self.assertTrue(report['sourceScanIncomplete'])
            self.assertEqual(report['sourceFilesParsed'],0)

    def test_replacement_not_mislabeled_pure_insertion(self):
        with tempfile.TemporaryDirectory() as folder:
            report=M.describe_delta(Path(folder),b'abcDEFxyz',b'abcGHIxyz')
            self.assertEqual(report['expectedMiddleBytes'],3)
            self.assertEqual(report['observedMiddleBytes'],3)

    def test_deleted_bytes_are_not_unavailable(self):
        with tempfile.TemporaryDirectory() as folder:
            report=M.describe_delta(Path(folder),b'abcDEFxyz',b'abcxyz')
            self.assertEqual(report['observedMiddleBytes'],0)
            self.assertEqual(report['expectedMiddleBytes'],3)

    def test_bounds_remain_with_optimized_python(self):
        self.assertEqual(M.describe_delta(Path('/nonexistent'),PAGE,None)['reason'],'BODY_TYPE_OR_SIZE')

if __name__=='__main__':unittest.main()
