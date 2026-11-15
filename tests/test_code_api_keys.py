#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Public API keys for POST /api/a11oy/code/v1/chat/completions.

Golden verdicts:
* only a salted HMAC-SHA256 digest of a key is stored; the key is shown once;
* keys issued before the digest scheme (plaintext rows) migrate out of
  plaintext at init_db() and keep authenticating;
* the Space's HF inference token is never accepted as a client credential;
* each key's issued rpm is enforced: past it the route answers 429 with
  Retry-After and nothing reaches the model.
"""
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_TMP = tempfile.mkdtemp(prefix="a11oy-apikeys-")
os.environ.setdefault("A11OY_CODE_DB", str(Path(_TMP) / "code.db"))
os.environ.setdefault("A11OY_CODE_SANDBOX", str(Path(_TMP) / "sandbox"))
os.environ.setdefault("A11OY_REACT_DB", str(Path(_TMP) / "react.sqlite3"))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import a11oy_code_orchestrator as orchestrator  # noqa: E402
import szl_operator_auth as opauth  # noqa: E402

OPERATOR = "op-test-secret-not-real"
OPERATOR_HEADERS = {"Authorization": f"Bearer {OPERATOR}"}
# Deliberately not shaped like a real Hugging Face token.
HF_SENTINEL = "upstream-inference-token-test-sentinel"
KEYS_PATH = "/api/a11oy/code/v1/keys"
CHAT_PATH = "/api/a11oy/code/v1/chat/completions"
CHAT_BODY = {"messages": [{"role": "user", "content": "hello"}]}
DECISION = {"tier": "T1", "model": "test-model", "provider": "test", "license_class": "GREEN",
            "reason": "test double", "fallbacks": [], "khipu_receipt": "0" * 64}


def _completion(*_args, **_kwargs):
    return {"id": "cmpl-test", "object": "chat.completion",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"}}]}


def _db_bytes(db_path: Path) -> bytes:
    out = b""
    for suffix in ("", "-journal", "-wal"):
        p = Path(str(db_path) + suffix)
        if p.exists():
            out += p.read_bytes()
    return out


def _all_text_values(db_path: Path) -> list:
    values = []
    with closing(sqlite3.connect(db_path)) as c:
        tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        for table in tables:
            for row in c.execute(f'SELECT * FROM "{table}"'):
                values.extend(v for v in row if isinstance(v, str))
    return values


class _IsolatedDb(unittest.TestCase):
    """Every test gets its own database file; the model is a test double."""

    def setUp(self):
        self.addCleanup(setattr, orchestrator, "_khipu_tip", orchestrator._khipu_tip)
        self.tmp = Path(tempfile.mkdtemp(prefix="a11oy-apikeys-case-"))
        self.db_path = self.tmp / "code.db"
        self.patches = [
            patch.object(orchestrator, "DB_PATH", str(self.db_path)),
            patch.dict(os.environ, {opauth.OPERATOR_KEY_ENV: OPERATOR, "HF_TOKEN": HF_SENTINEL}),
            patch.object(orchestrator, "route", return_value=dict(DECISION)),
            patch.object(orchestrator, "_get_client", return_value=MagicMock()),
        ]
        for p in self.patches:
            p.start()
        self.model = AsyncMock(side_effect=_completion)
        self.model_patch = patch.object(orchestrator, "_call_model", self.model)
        self.model_patch.start()
        app = FastAPI()
        orchestrator.attach(app)
        self.client = TestClient(app)

    def tearDown(self):
        self.model_patch.stop()
        for p in reversed(self.patches):
            p.stop()

    def issue(self, **body):
        r = self.client.post(KEYS_PATH, headers=OPERATOR_HEADERS, json=body)
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def chat(self, key=None, headers=None, **extra):
        h = dict(headers or {})
        if key is not None:
            h["Authorization"] = f"Bearer {key}"
        return self.client.post(CHAT_PATH, headers=h, json={**CHAT_BODY, **extra})


class IssuedKeysAreStoredAsSaltedDigests(_IsolatedDb):
    def test_issue_requires_the_operator(self):
        r = self.client.post(KEYS_PATH, json={"owner": "x"})
        self.assertEqual(r.status_code, 403)

    def test_key_is_returned_once_and_never_stored(self):
        issued = self.issue(owner="acme")
        key, key_id = issued["api_key"], issued["key_id"]
        self.assertEqual(issued["rpm"], orchestrator.API_KEY_DEFAULT_RPM)
        self.assertTrue(key.startswith(f"a11oy-{key_id}."))
        secret = key.split(".", 1)[1]
        self.assertGreaterEqual(len(secret), 43)
        for value in _all_text_values(self.db_path):
            self.assertNotIn(key, value)
            self.assertNotIn(secret, value)
        raw = _db_bytes(self.db_path)
        self.assertNotIn(key.encode(), raw)
        self.assertNotIn(secret.encode(), raw)
        with closing(sqlite3.connect(self.db_path)) as c:
            salt, digest, scheme = c.execute(
                "SELECT salt,digest,scheme FROM api_key_digests WHERE key_id=?",
                (key_id,)).fetchone()
        self.assertEqual(scheme, orchestrator.API_KEY_SCHEME_V1)
        self.assertEqual(len(bytes.fromhex(salt)), 16)
        self.assertEqual(digest, hmac.new(bytes.fromhex(salt), key.encode(),
                                          hashlib.sha256).hexdigest())
        self.assertNotEqual(digest, hashlib.sha256(key.encode()).hexdigest())

    def test_each_key_gets_its_own_salt(self):
        self.issue(owner="a")
        self.issue(owner="b")
        with closing(sqlite3.connect(self.db_path)) as c:
            salts = [r[0] for r in c.execute("SELECT salt FROM api_key_digests")]
        self.assertEqual(len(salts), 2)
        self.assertEqual(len(set(salts)), 2)

    def test_issue_receipt_names_the_key_id_not_the_key(self):
        issued = self.issue(owner="acme")
        with closing(sqlite3.connect(self.db_path)) as c:
            bodies = [r[0] for r in c.execute(
                "SELECT body FROM receipts WHERE action='apikey.issue'")]
        self.assertEqual(len(bodies), 1)
        self.assertIn(issued["key_id"], bodies[0])
        self.assertNotIn(issued["api_key"], bodies[0])

    def test_issue_rejects_bad_rpm_and_owner(self):
        for rpm in (0, -1, "60", True, 1.5, None, orchestrator.API_KEY_MAX_RPM + 1):
            r = self.client.post(KEYS_PATH, headers=OPERATOR_HEADERS, json={"rpm": rpm})
            self.assertEqual(r.status_code, 400, (rpm, r.text))
        for owner in ("", "   ", 5, "x" * 201):
            r = self.client.post(KEYS_PATH, headers=OPERATOR_HEADERS, json={"owner": owner})
            self.assertEqual(r.status_code, 400, (owner, r.text))
        with closing(sqlite3.connect(self.db_path)) as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM api_key_digests").fetchone()[0], 0)


class OnlyIssuedKeysAuthenticate(_IsolatedDb):
    def test_issued_key_reaches_the_model(self):
        key = self.issue(owner="acme")["api_key"]
        r = self.chat(key)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(self.model.await_count, 1)

    def test_digest_check_is_constant_time(self):
        issued = self.issue(owner="acme")
        with closing(sqlite3.connect(self.db_path)) as c:
            stored = c.execute("SELECT digest FROM api_key_digests WHERE key_id=?",
                               (issued["key_id"],)).fetchone()[0]
        with patch.object(orchestrator.hmac, "compare_digest",
                          wraps=hmac.compare_digest) as compare:
            self.assertIsNotNone(orchestrator._check_api_key(f"Bearer {issued['api_key']}"))
        self.assertIn(stored, [call.args[1] for call in compare.call_args_list],
                      "the stored digest must be checked with hmac.compare_digest")

    def test_tampered_unknown_and_missing_keys_are_refused(self):
        key = self.issue(owner="acme")["api_key"]
        key_id = key[len("a11oy-"):].split(".", 1)[0]
        attempts = [
            {"key": key[:-1] + ("A" if key[-1] != "A" else "B")},
            {"key": f"a11oy-{key_id}." + secrets.token_urlsafe(32)},
            {"key": f"a11oy-{secrets.token_hex(8)}." + secrets.token_urlsafe(32)},
            {"key": "a11oy-" + secrets.token_urlsafe(24)},
            {"key": "sk-" + secrets.token_urlsafe(24)},
            {"key": ""},
            {"headers": {"Authorization": f"Basic {key}"}},
            {},
        ]
        for attempt in attempts:
            r = self.chat(**attempt)
            self.assertEqual(r.status_code, 401, (attempt, r.text))
        self.model.assert_not_awaited()

    def test_hf_inference_token_is_not_a_client_credential(self):
        self.assertEqual(orchestrator._resolve_hf_token(), HF_SENTINEL)
        r = self.chat(HF_SENTINEL)
        self.assertEqual(r.status_code, 401, r.text)
        self.assertIsNone(orchestrator._check_api_key(f"Bearer {HF_SENTINEL}"))
        self.model.assert_not_awaited()

    def test_inactive_key_is_refused(self):
        issued = self.issue(owner="acme")
        with closing(sqlite3.connect(self.db_path)) as c:
            c.execute("UPDATE api_key_digests SET active=0 WHERE key_id=?", (issued["key_id"],))
            c.commit()
        self.assertEqual(self.chat(issued["api_key"]).status_code, 401)
        self.model.assert_not_awaited()


class IssuedRpmIsEnforced(_IsolatedDb):
    def test_requests_past_rpm_get_429_and_never_reach_the_model(self):
        issued = self.issue(owner="acme", rpm=2)
        real_admit = orchestrator._admit_api_key_request

        def admit_at_fixed_clock(key_id, rpm):
            return real_admit(key_id, rpm, now=60_000.0 + 15.0)

        with patch.object(orchestrator, "_admit_api_key_request",
                          side_effect=admit_at_fixed_clock):
            codes = [self.chat(issued["api_key"]).status_code for _ in range(2)]
            refused = self.chat(issued["api_key"])
            streamed = self.chat(issued["api_key"], stream=True)
        self.assertEqual(codes, [200, 200])
        for r in (refused, streamed):
            self.assertEqual(r.status_code, 429, r.text)
            self.assertEqual(r.headers.get("Retry-After"), "45")
        self.assertEqual(self.model.await_count, 2)
        with closing(sqlite3.connect(self.db_path)) as c:
            count = c.execute("SELECT count FROM api_key_usage WHERE key_id=?",
                              (issued["key_id"],)).fetchone()[0]
        self.assertEqual(count, 2, "refused requests must not be counted")

    def test_window_rolls_over_and_keys_are_counted_separately(self):
        t0 = 60_000.0 + 5.0
        admit = orchestrator._admit_api_key_request
        self.assertEqual(admit("k1", 2, now=t0), (True, 0))
        self.assertEqual(admit("k1", 2, now=t0 + 1), (True, 0))
        self.assertEqual(admit("k1", 2, now=t0 + 2), (False, 53))
        self.assertEqual(admit("k2", 2, now=t0 + 2), (True, 0))
        self.assertEqual(admit("k1", 2, now=t0 + 55), (True, 0))
        later = t0 + 55 + 86_400 + 60
        self.assertEqual(admit("k1", 2, now=later), (True, 0))
        with closing(sqlite3.connect(self.db_path)) as c:
            windows = [r[0] for r in c.execute(
                "SELECT window_start FROM api_key_usage WHERE key_id='k1'")]
        self.assertEqual(windows, [146_520], "windows older than 24 h are pruned")

    def test_limiter_failure_fails_closed(self):
        key = self.issue(owner="acme")["api_key"]
        with patch.object(orchestrator, "_admit_api_key_request",
                          side_effect=sqlite3.OperationalError("database is locked")):
            r = self.chat(key)
        self.assertEqual(r.status_code, 503, r.text)
        self.model.assert_not_awaited()


class PlaintextKeysMigrate(unittest.TestCase):
    """A database written by the previous code holds keys in plaintext."""

    def setUp(self):
        self.addCleanup(setattr, orchestrator, "_khipu_tip", orchestrator._khipu_tip)
        self.tmp = Path(tempfile.mkdtemp(prefix="a11oy-apikeys-legacy-"))
        self.db_path = self.tmp / "code.db"
        self.active = "a11oy-" + secrets.token_urlsafe(24)
        self.inactive = "a11oy-" + secrets.token_urlsafe(24)
        self.garbage_rpm = "a11oy-" + secrets.token_urlsafe(24)
        with closing(sqlite3.connect(self.db_path)) as c:
            c.execute("CREATE TABLE api_keys(key TEXT PRIMARY KEY, owner TEXT, created REAL,"
                      " rpm INTEGER, active INTEGER)")
            c.executemany("INSERT INTO api_keys VALUES(?,?,?,?,?)", [
                (self.active, "legacy-a", 1.0, 5, 1),
                (self.inactive, "legacy-b", 2.0, 60, 0),
                (self.garbage_rpm, "legacy-c", 3.0, "not-a-number", 1),
            ])
            c.commit()
        self.patches = [
            patch.object(orchestrator, "DB_PATH", str(self.db_path)),
            patch.dict(os.environ, {opauth.OPERATOR_KEY_ENV: OPERATOR}),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()

    def test_plaintext_is_removed_and_holders_keep_working(self):
        legacy = (self.active, self.inactive, self.garbage_rpm)
        self.assertIn(self.active.encode(), _db_bytes(self.db_path))
        orchestrator.init_db()
        with closing(sqlite3.connect(self.db_path)) as c:
            self.assertIsNone(c.execute(
                "SELECT 1 FROM sqlite_master WHERE name='api_keys'").fetchone())
            rows = c.execute("SELECT key_id,scheme,owner,rpm,active FROM api_key_digests"
                             " ORDER BY owner").fetchall()
        self.assertEqual([(r[1], r[2], r[3], r[4]) for r in rows], [
            (orchestrator.API_KEY_SCHEME_V0, "legacy-a", 5, 1),
            (orchestrator.API_KEY_SCHEME_V0, "legacy-b", 60, 0),
            (orchestrator.API_KEY_SCHEME_V0, "legacy-c", orchestrator.API_KEY_DEFAULT_RPM, 1),
        ])
        self.assertTrue(all(r[0].startswith("v0-") for r in rows))
        raw = _db_bytes(self.db_path)
        for key in legacy:
            self.assertNotIn(key.encode(), raw, "plaintext key bytes survived migration")
        active = orchestrator._check_api_key(f"Bearer {self.active}")
        self.assertEqual((active["owner"], active["rpm"]), ("legacy-a", 5))
        self.assertIsNone(orchestrator._check_api_key(f"Bearer {self.inactive}"))
        self.assertIsNotNone(orchestrator._check_api_key(f"Bearer {self.garbage_rpm}"))

    def test_migration_is_receipted_without_key_material_and_runs_once(self):
        orchestrator.init_db()
        orchestrator.init_db()
        with closing(sqlite3.connect(self.db_path)) as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM api_key_digests").fetchone()[0], 3)
            bodies = [r[0] for r in c.execute(
                "SELECT body FROM receipts WHERE action='apikey.migrate'")]
        self.assertEqual(len(bodies), 1)
        payload = json.loads(bodies[0])["payload"]
        self.assertEqual(payload["migrated"], 3)
        self.assertFalse(payload["plaintext_retained"])
        for key in (self.active, self.inactive, self.garbage_rpm):
            self.assertNotIn(key, bodies[0])

    def test_failed_migration_keeps_legacy_keys_refused_and_retries(self):
        real_store = orchestrator._store_api_key
        with patch.object(orchestrator, "_store_api_key",
                          side_effect=sqlite3.OperationalError("disk I/O error")):
            orchestrator.init_db()
        with closing(sqlite3.connect(self.db_path)) as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM api_keys").fetchone()[0], 3,
                             "a failed move must roll back, not drop rows")
            self.assertEqual(c.execute("SELECT COUNT(*) FROM api_key_digests").fetchone()[0], 0)
        self.assertIsNone(orchestrator._check_api_key(f"Bearer {self.active}"))
        self.assertIs(orchestrator._store_api_key, real_store)
        orchestrator.init_db()
        self.assertIsNotNone(orchestrator._check_api_key(f"Bearer {self.active}"))
        self.assertNotIn(self.active.encode(), _db_bytes(self.db_path))

    def test_fresh_database_has_no_plaintext_table(self):
        fresh = self.tmp / "fresh.db"
        with patch.object(orchestrator, "DB_PATH", str(fresh)):
            orchestrator.init_db()
        with closing(sqlite3.connect(fresh)) as c:
            names = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertIn("api_key_digests", names)
        self.assertIn("api_key_usage", names)
        self.assertNotIn("api_keys", names)


if __name__ == "__main__":
    unittest.main()
