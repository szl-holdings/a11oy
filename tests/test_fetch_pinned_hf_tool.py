from __future__ import annotations

import importlib.util
import hashlib
import io
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".github" / "scripts" / "fetch_pinned_hf_tool.py"
SPEC = importlib.util.spec_from_file_location("fetch_pinned_hf_tool", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class Response(io.BytesIO):
    status = 200


class PinnedToolTests(unittest.TestCase):
    def test_accepts_exact_bytes(self) -> None:
        raw = b"exact tool\n"
        original_digest = MODULE.PINNED_SHA256
        MODULE.PINNED_SHA256 = hashlib.sha256(raw).hexdigest()
        try:
            with tempfile.TemporaryDirectory() as temporary:
                output = Path(temporary) / "tool.py"
                receipt = MODULE.fetch_tool(
                    output,
                    opener=lambda _request, timeout: Response(raw) if timeout == 30 else None,
                )
                self.assertEqual(output.read_bytes(), raw)
                self.assertEqual(receipt["bytes"], len(raw))
        finally:
            MODULE.PINNED_SHA256 = original_digest

    def test_rejects_wrong_digest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "tool.py"
            with self.assertRaisesRegex(MODULE.FetchError, "digest mismatch"):
                MODULE.fetch_tool(
                    output,
                    opener=lambda _request, timeout: Response(b"wrong\n"),
                )
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
