"""Key-pin contract for the Ayllu council wall (no network, no real key loading).

The council public key is fetched from a mutable branch at request time, so an
unset A11OY_COUNCIL_PUB_SHA256 must NOT mean "trust whatever was fetched".
"""

import asyncio
import hashlib
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import a11oy_ayllu_wall as wall  # noqa: E402

KEY = (ROOT / "ayllu" / "keys" / "council-runtime-2026-07-21.pub").read_bytes()


class _Client:
    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


def _run(pem, index=b'{"decisions": []}', decision=b"{}"):
    async def fake_fetch(client, path):
        if path == wall._KEY_PATH:
            return pem
        if path == wall._INDEX_PATH:
            return index
        return decision

    wall._byte_cache.clear()
    with mock.patch.object(wall, "_fetch", fake_fetch), \
            mock.patch.object(wall, "load_pem_public_key", lambda _pem: object()), \
            mock.patch.object(wall, "_runtime_key_state", lambda _pem: {"state": "TEST"}), \
            mock.patch.object(wall.httpx, "AsyncClient", _Client):
        return asyncio.run(wall._wall_payload())


class KeyPin(unittest.TestCase):
    def test_builtin_pin_matches_committed_key(self):
        self.assertEqual(wall._BUILTIN_PIN, hashlib.sha256(KEY).hexdigest())

    def test_unset_env_accepts_only_the_code_pinned_key(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop(wall._PIN_ENV, None)
            self.assertEqual(_run(KEY)["keyHonesty"]["keyTrust"], "CODE_PINNED")

    def test_unset_env_fails_closed_on_swapped_key(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop(wall._PIN_ENV, None)
            out = _run(b"-----BEGIN PUBLIC KEY-----\nattacker\n-----END PUBLIC KEY-----\n",
                       index=b'{"decisions": ["d.json"]}')
        self.assertEqual(out["keyHonesty"]["keyTrust"], "PIN_MISMATCH")
        self.assertFalse(out["ok"])
        self.assertTrue(all(d.get("verified") is False for d in out["decisions"]))
        self.assertEqual(out["decisions"][0].get("status"), "PIN_MISMATCH_FAILED_CLOSED")

    def test_env_pin_match_and_mismatch(self):
        with mock.patch.dict(os.environ, {wall._PIN_ENV: hashlib.sha256(KEY).hexdigest().upper()}):
            self.assertEqual(_run(KEY)["keyHonesty"]["keyTrust"], "PINNED")
        with mock.patch.dict(os.environ, {wall._PIN_ENV: "0" * 64}):
            self.assertEqual(_run(KEY)["keyHonesty"]["keyTrust"], "PIN_MISMATCH")


if __name__ == "__main__":
    unittest.main()
