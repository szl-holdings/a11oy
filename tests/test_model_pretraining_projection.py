import tempfile
import unittest
from pathlib import Path

from scripts.build_model_pretraining_projection import canonical_source_bytes


class ProjectionSourceBytesTests(unittest.TestCase):
    def test_crlf_and_lf_source_bytes_have_identical_canonical_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_bytes(b'{"schemaVersion":2}\r\n{"org":"SZLHOLDINGS"}\r\n')
            self.assertEqual(
                canonical_source_bytes(path),
                b'{"schemaVersion":2}\n{"org":"SZLHOLDINGS"}\n',
            )

    def test_lone_cr_is_normalized_for_legacy_windows_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_bytes(b"first\rsecond\r\nthird\n")
            self.assertEqual(canonical_source_bytes(path), b"first\nsecond\nthird\n")
