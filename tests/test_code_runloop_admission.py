#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Admission and restart check for the code run-loop only.

The signer double is unsigned and the receipt evidence class is SIMULATED.
SZL_SECOND_BRAIN_RAG stays unset. This file does not import serve.py.
"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

if not os.environ.get("A11OY_CODE_DB"):
    _TMP = tempfile.mkdtemp(prefix="a11oy-runloop-admission-")
    os.environ["A11OY_CODE_DB"] = str(Path(_TMP) / "code.db")
    os.environ["A11OY_CODE_SANDBOX"] = str(Path(_TMP) / "sandbox")
    os.environ["A11OY_REACT_DB"] = str(Path(_TMP) / "react.sqlite3")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from starlette.applications import Starlette  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import a11oy_code_engine as engine  # noqa: E402
import a11oy_code_runloop as runloop  # noqa: E402
import a11oy_code_runloop_journey as journey  # noqa: E402
import a11oy_org_rag  # noqa: E402
import szl_agentic_loop as loop  # noqa: E402
import szl_operator_auth as opauth  # noqa: E402

OPERATOR = "op-test-secret-not-real"
APPROVER = "approver-test-secret-not-real"
TENANT = "synthetic-tenant"
PLAN = "/api/a11oy/v1/code/plan"
RUNSTEP = "/api/a11oy/v1/code/runstep"
_VERIFIER = (
    "import json, sys\n"
    "sys.path.insert(0, sys.argv[1])\n"
    "import a11oy_code_runloop as runloop\n"
    "print(json.dumps(runloop.verify_receipt_log(sys.argv[2])))\n"
)


def _unsigned(payload):
    return {"signed": False, "signatures": [], "payloadType": "application/test+json"}


def _forbid_turn(*_args, **_kwargs):
    raise AssertionError("governed_turn must not run before admission")


class CodeRunloopAdmission(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="a11oy-runloop-receipt-")
        self.log = Path(self.tmp.name) / "ledger"
        self.saved_rag = os.environ.pop("SZL_SECOND_BRAIN_RAG", None)
        self.saved_log = os.environ.pop(runloop.RECEIPT_LOG_ENV, None)
        os.environ[runloop.RECEIPT_LOG_ENV] = str(self.log)
        self.env = patch.dict(os.environ, {
            opauth.OPERATOR_KEY_ENV: OPERATOR,
            opauth.SECOND_APPROVER_KEY_ENV: APPROVER,
            "A11OY_CODE_TENANT": TENANT,
        })
        self.env.start()
        self.model = patch.object(engine, "_model_configured", return_value=False)
        self.model.start()
        app = Starlette()
        runloop.register(app, "a11oy", _unsigned)
        self.client = TestClient(app)

    def tearDown(self):
        self.model.stop()
        self.env.stop()
        if self.saved_rag is None:
            os.environ.pop("SZL_SECOND_BRAIN_RAG", None)
        else:
            os.environ["SZL_SECOND_BRAIN_RAG"] = self.saved_rag
        if self.saved_log is None:
            os.environ.pop(runloop.RECEIPT_LOG_ENV, None)
        else:
            os.environ[runloop.RECEIPT_LOG_ENV] = self.saved_log
        self.tmp.cleanup()

    def _admitted(self):
        return {"Authorization": f"Bearer {OPERATOR}", "X-A11oy-Tenant": TENANT}

    def test_second_brain_flag_stays_off(self):
        self.assertNotIn((os.environ.get("SZL_SECOND_BRAIN_RAG") or "").strip().lower(),
                         {"1", "true", "yes"})

    def test_anonymous_is_refused_before_tenant_and_parse(self):
        with patch.object(runloop._engine, "governed_turn", _forbid_turn):
            response = self.client.post(RUNSTEP, content=b"{")
        self.assertEqual(response.status_code, 401, response.text[:400])
        self.assertEqual(response.json()["status"], "BLOCKED")
        self.assertFalse(self.log.exists())

    def test_wrong_tenant_refuses_before_parse(self):
        cases = (
            {"Authorization": f"Bearer {OPERATOR}", "X-A11oy-Tenant": "other-tenant"},
            {"Authorization": f"Bearer {OPERATOR}", "X-A11oy-Tenant": "synthetic-tenant-extra"},
            {"Authorization": f"Bearer {OPERATOR}"},
        )
        for headers in cases:
            with self.subTest(headers=sorted(headers)), \
                    patch.object(runloop._engine, "governed_turn", _forbid_turn):
                response = self.client.post(RUNSTEP, headers=headers, content=b"{")
            self.assertEqual(response.status_code, 403, response.text[:400])
            self.assertEqual(response.json()["status"], "BLOCKED")
            self.assertTrue(response.json()["tenant_configured"])
            self.assertFalse(self.log.exists())

    def test_unset_tenant_is_unavailable_before_parse(self):
        headers = {"Authorization": f"Bearer {OPERATOR}", "X-A11oy-Tenant": TENANT}
        with patch.dict(os.environ, {"A11OY_CODE_TENANT": ""}), \
                patch.object(runloop._engine, "governed_turn", _forbid_turn):
            response = self.client.post(RUNSTEP, headers=headers, content=b"{")
        self.assertEqual(response.status_code, 503, response.text[:400])
        self.assertFalse(response.json()["tenant_configured"])
        self.assertFalse(self.log.exists())

    def test_purpose_and_limits_refuse_before_the_engine(self):
        cases = (
            {"prompt": "synthetic fixture: deny-by-default gate"},
            {"prompt": "hello", "purpose": "chat", "mode": "code"},
            {"prompt": "x" * 2001, "purpose": "research"},
            {"prompt": 1, "purpose": "chat"},
            {"prompt": "   ", "purpose": "research"},
        )
        for body in cases:
            with self.subTest(body=body), \
                    patch.object(runloop._engine, "governed_turn", _forbid_turn):
                response = self.client.post(RUNSTEP, headers=self._admitted(), json=body)
            self.assertEqual(response.status_code, 400, response.text[:400])
            self.assertEqual(response.json()["status"], "BLOCKED")
            self.assertFalse(self.log.exists())

    def test_lone_surrogate_is_refused_before_the_engine(self):
        with patch.object(runloop._engine, "governed_turn", _forbid_turn):
            query, purpose, refusal = runloop._admit_query(
                {"prompt": "\ud800", "purpose": "research"}, "prompt")
        self.assertIsNone(query)
        self.assertIsNone(purpose)
        self.assertEqual(refusal.status_code, 400)
        self.assertFalse(self.log.exists())

    def test_chat_purpose_is_not_reclassified_as_code(self):
        response = self.client.post(PLAN, headers=self._admitted(), json={
            "task": "def f():\n    return 1",
            "purpose": "chat",
            "mode": "",
        })
        self.assertEqual(response.status_code, 200, response.text[:400])
        payload = response.json()
        self.assertEqual(payload["mode"], "chat")
        self.assertEqual(payload["purpose"], "chat")
        self.assertTrue(payload["plan"])
        self.assertTrue(all(step["mode"] == "chat" for step in payload["plan"]))

    def test_missing_engine_writes_no_receipt(self):
        os.environ[runloop.RECEIPT_LOG_ENV] = str(self.log)
        with patch.object(runloop, "_ENGINE_OK", False), \
                patch.object(runloop, "_ENGINE_ERR", "hidden", create=True):
            response = self.client.post(RUNSTEP, headers=self._admitted(), json={
                "purpose": "research",
                "mode": "research",
                "prompt": runloop.FIXED_SYNTHETIC_QUERY,
                "sandbox": False,
            })
        self.assertEqual(response.status_code, 200, response.text[:400])
        self.assertFalse(response.json()["ok"])
        self.assertNotIn("restart_receipt", response.json())
        self.assertFalse(self.log.exists())

    def test_invalid_json_is_refused_before_the_engine(self):
        with patch.object(runloop._engine, "governed_turn", _forbid_turn):
            response = self.client.post(RUNSTEP, headers=self._admitted(), content=b"{")
        self.assertEqual(response.status_code, 400, response.text[:400])
        self.assertEqual(response.json()["error"], "JSON object required")
        self.assertFalse(self.log.exists())

    def test_unset_log_does_not_claim_restart_verification(self):
        os.environ.pop(runloop.RECEIPT_LOG_ENV, None)
        response = self.client.post(RUNSTEP, headers=self._admitted(), json={
            "purpose": "research",
            "mode": "research",
            "prompt": runloop.FIXED_SYNTHETIC_QUERY,
            "sandbox": False,
            "state_changing": False,
        })
        self.assertEqual(response.status_code, 200, response.text[:500])
        receipt = response.json()["restart_receipt"]
        self.assertEqual(receipt["evidence_class"], "SIMULATED")
        self.assertFalse(receipt["persisted"])
        self.assertFalse(receipt["restart_verifiable"])
        self.assertFalse(self.log.exists())

    def test_fixed_query_receipt_checks_in_a_new_process(self):
        os.environ[runloop.RECEIPT_LOG_ENV] = str(self.log)
        with patch.object(a11oy_org_rag, "query", return_value={
            "ok": False, "i_dont_know": True, "chunks": [],
        }):
            response = self.client.post(RUNSTEP, headers=self._admitted(), json={
            "purpose": "research",
            "mode": "research",
            "prompt": runloop.FIXED_SYNTHETIC_QUERY,
            "sandbox": False,
            "state_changing": False,
        })
        self.assertEqual(response.status_code, 200, response.text[:500])
        receipt = response.json()["restart_receipt"]
        self.assertEqual(receipt["evidence_class"], "SIMULATED")
        self.assertEqual(receipt["signer"], "SIMULATED")
        self.assertTrue(receipt["persisted"])
        self.assertTrue(receipt["restart_verifiable"])
        raw = b"".join(path.read_bytes() for path in self.log.rglob("*") if path.is_file())
        self.assertNotIn(TENANT.encode("utf-8"), raw)
        self.assertNotIn(OPERATOR.encode("utf-8"), raw)
        self.assertNotIn(b'"khipu"', raw)
        journey_body = response.json()["journey"]
        self.assertEqual(journey_body["retrieval"]["backend"], "in-image-governance-corpus")
        self.assertEqual(journey_body["retrieval"]["corpus_generation"], "UNKNOWN")
        self.assertEqual(journey_body["retrieval"]["fallback"], "org-rag-unavailable")
        self.assertEqual(journey_body["retrieval"]["abstention"], "i_dont_know")
        self.assertEqual(journey_body["planning"]["execution_mode"], "PLAN_ONLY")
        self.assertEqual(journey_body["planning"]["decision"], "READY_TO_ORCHESTRATE")
        self.assertEqual(journey_body["planning"]["effectors"], 0)
        self.assertFalse(journey_body["planning"]["authorized"])
        self.assertEqual(journey_body["execution"]["status"], "NOT_REQUESTED")
        self.assertEqual(journey_body["execution"]["provider_calls"], 0)
        self.assertEqual(journey_body["signature"]["evidence_class"], "SIMULATED")
        self.assertFalse(journey_body["signature"]["signed"])
        self.assertFalse(journey_body["signature"]["signature_valid"])
        self.assertEqual(journey_body["durability"]["store"], "szl_lake_store.ReceiptLedger")
        roles = {row["name"]: row["role"] for row in journey_body["guards"]}
        self.assertEqual(roles["F4"], "NOT_APPLICABLE")
        self.assertEqual(roles["F7"], "NOT_APPLICABLE")
        self.assertEqual(roles["F22"], "NOT_APPLICABLE")
        self.assertTrue(all(row["loaded_package"] == "NOT_ATTRIBUTED"
                            for row in journey_body["guards"] if row["name"] in {"F4", "F7", "F22"}))
        script = Path(self.tmp.name) / "check_receipt_log.py"
        script.write_text(_VERIFIER, encoding="utf-8")
        child_env = os.environ.copy()
        child_env.pop("SZL_SECOND_BRAIN_RAG", None)
        for key in (opauth.OPERATOR_KEY_ENV, opauth.SECOND_APPROVER_KEY_ENV,
                    "A11OY_CODE_TENANT", runloop.RECEIPT_LOG_ENV):
            child_env.pop(key, None)
        proc = subprocess.run(
            [sys.executable, str(script), str(ROOT), str(self.log)],
            capture_output=True, text=True, env=child_env, check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr[-2000:])
        verdict = json.loads(proc.stdout.strip().splitlines()[-1])
        self.assertTrue(verdict["ok"])
        self.assertEqual(verdict["status"], "CHECKED")
        checked = verdict["receipts"][0]
        self.assertEqual(checked["evidence_class"], "SIMULATED")
        self.assertEqual(checked["signer"], "SIMULATED")
        self.assertTrue(checked["chain_intact"])
        self.assertFalse(checked["signature_valid"])
        self.assertEqual(checked["purpose"], "research")
        self.assertEqual(
            checked["query_sha256"],
            hashlib.sha256(runloop.FIXED_SYNTHETIC_QUERY.encode("utf-8")).hexdigest(),
        )

    def _post_fixed(self, **extra):
        body = {
            "purpose": "research",
            "mode": "research",
            "prompt": runloop.FIXED_SYNTHETIC_QUERY,
            "sandbox": False,
            "state_changing": False,
        }
        body.update(extra)
        with patch.object(a11oy_org_rag, "query", return_value={
            "ok": False, "i_dont_know": True, "chunks": [],
        }):
            return self.client.post(RUNSTEP, headers=self._admitted(), json=body)

    def test_anonymous_does_not_retrieve_or_write(self):
        def forbid_retrieve(*_args, **_kwargs):
            raise AssertionError("retrieval must not run")
        with patch.object(runloop._engine, "governed_turn", _forbid_turn), \
                patch.object(loop, "_retrieve_with_identity", forbid_retrieve):
            response = self.client.post(RUNSTEP, content=b"{}")
        self.assertEqual(response.status_code, 401, response.text[:400])
        self.assertFalse(self.log.exists())

    def test_lease_is_rejected_before_the_engine(self):
        with patch.object(runloop._engine, "governed_turn", _forbid_turn), \
                patch.object(loop, "_retrieve_with_identity", _forbid_turn):
            response = self.client.post(RUNSTEP, headers=self._admitted(), json={
                "purpose": "research",
                "prompt": runloop.FIXED_SYNTHETIC_QUERY,
                "lease": "stale",
            })
        self.assertEqual(response.status_code, 400, response.text[:400])
        self.assertEqual(response.json()["error"], "lease is not used")
        self.assertFalse(self.log.exists())

    def test_measure_domain_rejects_nonfinite_overflow_and_units(self):
        self.assertEqual(journey.admit_measure(None)["result"], "NOT_APPLICABLE")
        for measure in (float("nan"), float("inf"), float("-inf")):
            guard = journey.admit_measure(measure)
            self.assertEqual(guard["result"], "REJECTED")
            self.assertEqual(guard["reason"], "measure is not finite")
        samples = (
            {"value": 1, "unit": "joules"},
            2 ** 40,
            {"value": 1, "extra": True},
        )
        for measure in samples:
            with self.subTest(measure=measure), \
                    patch.object(runloop._engine, "governed_turn", _forbid_turn):
                response = self.client.post(RUNSTEP, headers=self._admitted(), json={
                    "purpose": "research",
                    "prompt": runloop.FIXED_SYNTHETIC_QUERY,
                    "measure": measure,
                })
                self.assertEqual(response.status_code, 400, response.text[:400])
                self.assertEqual(response.json()["error"], "measure is outside the domain")
                self.assertFalse(self.log.exists())
        headers = self._admitted()
        headers["Content-Type"] = "application/json"
        raw = (
            '{"purpose":"research","prompt":"%s","measure":NaN}'
            % runloop.FIXED_SYNTHETIC_QUERY
        )
        with patch.object(runloop._engine, "governed_turn", _forbid_turn):
            response = self.client.post(RUNSTEP, headers=headers, content=raw.encode("utf-8"))
        self.assertEqual(response.status_code, 400, response.text[:400])
        self.assertEqual(response.json()["error"], "measure is outside the domain")
        self.assertFalse(self.log.exists())

    def test_repeated_delivery_does_not_call_the_engine_again(self):
        calls = {"n": 0}
        real = runloop._engine.governed_turn

        def counting(*args, **kwargs):
            calls["n"] += 1
            return real(*args, **kwargs)

        with patch.object(runloop._engine, "governed_turn", counting):
            first = self._post_fixed()
            second = self._post_fixed()
        self.assertEqual(first.status_code, 200, first.text[:400])
        self.assertEqual(second.status_code, 200, second.text[:400])
        self.assertEqual(calls["n"], 1)
        self.assertTrue(second.json()["duplicate"])
        self.assertIsNone(second.json()["run"])
        lines = []
        for path in self.log.rglob("*.ndjson"):
            lines.extend(line for line in path.read_bytes().splitlines() if line.strip())
        self.assertEqual(len(lines), 1)

    def test_omitted_request_ids_keep_distinct_queries(self):
        first = self._post_fixed()
        second = self._post_fixed(prompt="another synthetic research request")
        self.assertEqual(first.status_code, 200, first.text[:400])
        self.assertEqual(second.status_code, 200, second.text[:400])
        self.assertTrue(first.json()["restart_receipt"]["persisted"])
        self.assertTrue(second.json()["restart_receipt"]["persisted"])
        self.assertFalse(second.json().get("duplicate"))
        lines = []
        for path in self.log.rglob("*.ndjson"):
            lines.extend(line for line in path.read_bytes().splitlines() if line.strip())
        self.assertEqual(len(lines), 2)
        self.assertNotIn(b'"request_id":"derived"', b"".join(lines))

    def test_reused_request_id_conflicts_before_the_engine(self):
        seeded = self._post_fixed(request_id="same-request")
        self.assertTrue(seeded.json()["restart_receipt"]["persisted"])
        before = b"".join(path.read_bytes() for path in self.log.rglob("*") if path.is_file())
        with patch.object(runloop._engine, "governed_turn", _forbid_turn), \
                patch.object(loop, "_retrieve_with_identity", _forbid_turn):
            response = self._post_fixed(
                request_id="same-request",
                prompt="a different admitted research request",
            )
        self.assertEqual(response.status_code, 409, response.text[:400])
        self.assertEqual(response.json()["error"], "request_id conflict")
        after = b"".join(path.read_bytes() for path in self.log.rglob("*") if path.is_file())
        self.assertEqual(after, before)

    def test_crash_before_commit_leaves_no_ledger(self):
        script = self.tmp.name + "/crash_before.py"
        Path(script).write_text("import os\nos._exit(98)\n", encoding="utf-8")
        proc = subprocess.run([sys.executable, script], check=False)
        self.assertEqual(proc.returncode, 98)
        self.assertFalse(any(self.log.rglob("*.ndjson")))

    def test_crash_after_commit_verifies_in_a_new_process(self):
        response = self._post_fixed()
        self.assertTrue(response.json()["restart_receipt"]["persisted"])
        script = Path(self.tmp.name) / "crash_after.py"
        script.write_text(
            "import os, sys\n"
            "sys.path.insert(0, sys.argv[1])\n"
            "import a11oy_code_runloop as runloop\n"
            "verdict = runloop.verify_receipt_log(sys.argv[2])\n"
            "os._exit(0 if verdict.get('ok') is True else 97)\n",
            encoding="utf-8",
        )
        proc = subprocess.run(
            [sys.executable, str(script), str(ROOT), str(self.log)],
            check=False,
        )
        self.assertEqual(proc.returncode, 0)

    def test_stale_commit_lock_does_not_append(self):
        self._post_fixed()
        lock = self.log / "code-runloop.commit.lock"
        lock.write_text("held", encoding="utf-8")
        before = list(self.log.rglob("*.ndjson"))
        before_bytes = before[0].read_bytes()
        with patch.object(runloop._engine, "governed_turn", _forbid_turn), \
                patch.object(loop, "_retrieve_with_identity", _forbid_turn):
            response = self.client.post(RUNSTEP, headers=self._admitted(), json={
                "purpose": "research",
                "mode": "research",
                "prompt": "a different admitted research request",
                "request_id": "other-request",
            })
        self.assertEqual(response.status_code, 409, response.text[:400])
        self.assertEqual(response.json()["error"], "commit lock held")
        self.assertEqual(before[0].read_bytes(), before_bytes)

    def test_corrupt_partial_line_fail_closes(self):
        self._post_fixed()
        ndjson = next(self.log.rglob("*.ndjson"))
        with ndjson.open("ab") as handle:
            handle.write(b'{"truncated"\n')
        verdict = journey.verify_ledger(str(self.log))
        self.assertFalse(verdict["ok"])
        self.assertEqual(verdict["reason"], "malformed receipt line")
        before = ndjson.read_bytes()
        with patch.object(runloop._engine, "governed_turn", _forbid_turn), \
                patch.object(loop, "_retrieve_with_identity", _forbid_turn):
            response = self._post_fixed(request_id="after-corrupt")
        self.assertEqual(response.status_code, 409, response.text[:400])
        self.assertEqual(response.json()["error"], "malformed receipt line")
        self.assertEqual(ndjson.read_bytes(), before)

    def test_rejected_graph_does_not_commit(self):
        def revise(_payload):
            return {
                "ok": True,
                "decision": "REVISE",
                "contract_digest": "ab" * 32,
                "plan_id": "ggp-rejected",
                "execution": {
                    "mode": "PLAN_ONLY",
                    "authorized": False,
                    "effectors": 0,
                    "writes": 0,
                    "provider_calls": 0,
                },
                "gates": {
                    "pass": False,
                    "blockers": [{"code": "TERMINAL_NOT_ANCHORED", "nodes": ["plan"]}],
                },
            }

        with patch.object(journey, "analyse_graph", revise):
            response = self._post_fixed()
        self.assertEqual(response.status_code, 200, response.text[:400])
        self.assertFalse(response.json()["restart_receipt"]["persisted"])
        self.assertEqual(response.json()["restart_receipt"]["reason"], "guards did not pass")
        self.assertEqual(response.json()["journey"]["planning"]["decision"], "REVISE")
        self.assertFalse(any(self.log.rglob("*.ndjson")))

    def test_missing_parent_and_reordered_lines_fail_closed(self):
        self._post_fixed()
        self._post_fixed(request_id="second-request")
        ndjson = next(self.log.rglob("*.ndjson"))
        lines = [line for line in ndjson.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertEqual(len(lines), 2)
        ndjson.write_text(lines[1] + "\n" + lines[0] + "\n", encoding="utf-8")
        verdict = journey.verify_ledger(str(self.log))
        self.assertFalse(verdict["ok"])
        self.assertIn(verdict["reason"], {"parent hash mismatch", "missing or unexpected parent",
                                           "chain index is out of order"})

    def test_out_of_order_and_repeated_acknowledgement(self):
        response = self._post_fixed()
        ack = response.json()["restart_receipt"]
        good = {
            "receipt_id": ack["receipt_id"],
            "chain_index": ack["chain_index"],
            "chain_head": ack["chain_head"],
        }
        first = journey.verify_acknowledgement(str(self.log), good)
        second = journey.verify_acknowledgement(str(self.log), good)
        self.assertTrue(first["acknowledged"])
        self.assertTrue(second["acknowledged"])
        late = {"receipt_id": "not-committed", "chain_index": 2, "chain_head": "absent"}
        rejected = journey.verify_acknowledgement(str(self.log), late)
        self.assertFalse(rejected["acknowledged"])
        lines = []
        for path in self.log.rglob("*.ndjson"):
            lines.extend(line for line in path.read_bytes().splitlines() if line.strip())
        self.assertEqual(len(lines), 1)

    def test_concurrent_duplicate_commits_one_line(self):
        self._post_fixed()
        ndjson = next(self.log.rglob("*.ndjson"))
        stored = json.loads(ndjson.read_text(encoding="utf-8").splitlines()[0])["receipt"]
        stored["_planning_ok"] = True
        race = Path(self.tmp.name) / "race"
        barrier = threading.Barrier(2)
        results = []

        def worker():
            barrier.wait()
            results.append(journey.commit_record(str(race), dict(stored)))

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(sorted(item["state"] for item in results), ["COMMITTED", "DUPLICATE"])
        lines = []
        for path in race.rglob("*.ndjson"):
            lines.extend(line for line in path.read_bytes().splitlines() if line.strip())
        self.assertEqual(len(lines), 1)

    def test_frontend_posts_the_fixed_query_through_runstep(self):
        html = (ROOT / "web" / "code.html").read_text(encoding="utf-8")
        self.assertIn(runloop.FIXED_SYNTHETIC_QUERY, html)
        self.assertIn('headers["X-A11oy-Tenant"]', html)
        self.assertIn('id="operatorToken"', html)
        self.assertIn('type="password"', html)
        self.assertIn('if(token) headers["Authorization"] = "Bearer " + token;', html)
        self.assertIn('id="stateRetrieval"', html)
        self.assertIn('id="statePlanning"', html)
        self.assertIn('id="stateExecution"', html)
        self.assertIn('id="stateSignature"', html)
        self.assertIn('id="stateDurability"', html)
        self.assertIn('id="purpose"', html)
        self.assertIn('id="tenant"', html)
        self.assertIn('autocomplete="off"', html)
        self.assertIn('jpost("/runstep"', html)
        self.assertIn("prompt: FIXED_SYNTHETIC_QUERY", html)
        self.assertIn('purpose: "research"', html)
        self.assertIn('mode: "research"', html)
        self.assertIn("sandbox: false", html)
        self.assertIn("state_changing: false", html)
        self.assertNotIn(TENANT, html)
        self.assertNotIn(OPERATOR, html)
        self.assertNotIn("A11OY_CODE_ADMIN_KEY", html)


if __name__ == "__main__":
    unittest.main()
