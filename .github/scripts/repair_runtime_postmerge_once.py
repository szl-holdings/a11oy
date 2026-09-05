#!/usr/bin/env python3
"""One-shot forward repair for the four Codex findings left after PR #1986."""
from __future__ import annotations

from pathlib import Path


IMMUNE = Path("szl_immune.py")
LOOP = Path("szl_agentic_loop.py")
OUROBOROS_UI = Path("src/pages/Ouroboros.tsx")
WORKCELL = Path("audit/POST_MERGE_1986_REVIEW_REPAIR_2026-09-05.md")
TEST = Path("tests/test_post_merge_1986_review_repairs.py")


def replace_once(text: str, old: str, new: str, *, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one target, found {count}")
    return text.replace(old, new, 1)


def patch_immune() -> None:
    text = IMMUNE.read_text(encoding="utf-8")

    marker = "\n\ndef _verify_nexus_receipt(receipt: dict, verify=None) -> dict:\n"
    helper = r"""

def _verified_receipt_keyid(verdict: dict) -> str | None:
    \"\"\"Return the key that actually verified the receipt, including rotation.\"\"\"
    signatures = verdict.get("signatures")
    if isinstance(signatures, list):
        for signature in signatures:
            if not isinstance(signature, dict) or signature.get("verified") is not True:
                continue
            verified_by = signature.get("verified_by_keyid")
            if isinstance(verified_by, str) and verified_by.strip():
                return verified_by.strip()
        # A real verifier that returned signature results must identify the
        # successful key. Do not misattribute it to the current active key.
        if signatures:
            return None
    # Compatibility for narrow injected verifiers used by existing tests and
    # older peers that predate per-signature rotation attribution.
    expected = verdict.get("keyid_expected")
    if isinstance(expected, str) and expected.strip():
        return expected.strip()
    return None
"""
    text = replace_once(
        text,
        marker,
        helper + marker,
        label="verified key helper insertion",
    )

    old_verify = r"""    payload = verdict.get("payload_decoded")
    if verdict.get("verified") is not True or not isinstance(payload, dict):
        return {
            "verified": False,
            "reason": str(verdict.get("reason") or "receipt signature not verified"),
            "payload": None,
        }
    return {
        "verified": True,
        "reason": None,
        "payload": payload,
        "keyid": verdict.get("keyid_expected"),
    }
"""
    new_verify = r"""    payload = verdict.get("payload_decoded")
    if verdict.get("verified") is not True or not isinstance(payload, dict):
        return {
            "verified": False,
            "reason": str(verdict.get("reason") or "receipt signature not verified"),
            "payload": None,
        }
    verified_keyid = _verified_receipt_keyid(verdict)
    if verified_keyid is None:
        return {
            "verified": False,
            "reason": "receipt verifier did not identify the successful key",
            "payload": None,
        }
    return {
        "verified": True,
        "reason": None,
        "payload": payload,
        "keyid": verified_keyid,
    }
"""
    text = replace_once(
        text,
        old_verify,
        new_verify,
        label="verified key attribution",
    )

    old_binding = r"""    signed_request_id = signed_payload.get("requestId") or nexus.get("requestId")
    signed_program = signed_payload.get("program") or nexus.get("program")
    signed_mode = signed_payload.get("mode") or nexus.get("mode")
    signed_steps = signed_payload.get("steps") or nexus.get("steps")
    signed_coefficients = nexus.get("coefficients")
"""
    new_binding = r"""    duplicate_fields = ("requestId", "program", "mode", "steps")
    duplicates_agree = all(
        field not in signed_payload
        or signed_payload.get(field) == nexus.get(field)
        for field in duplicate_fields
    )
    # Execution hashes and final state come from agent.nexus, so the binding
    # metadata must come from that same signed object. Top-level duplicates are
    # accepted only when they agree exactly; a substituted nested execution can
    # never inherit a trusted outer request identity.
    signed_request_id = nexus.get("requestId")
    signed_program = nexus.get("program")
    signed_mode = nexus.get("mode")
    signed_steps = nexus.get("steps")
    signed_coefficients = nexus.get("coefficients")
"""
    text = replace_once(
        text,
        old_binding,
        new_binding,
        label="nested nexus binding source",
    )

    old_binding_gate = r"""    binding_ok = (
        body.get("requestId") == request_id
        and signed_request_id == request_id
"""
    new_binding_gate = r"""    binding_ok = (
        body.get("requestId") == request_id
        and duplicates_agree
        and signed_request_id == request_id
"""
    text = replace_once(
        text,
        old_binding_gate,
        new_binding_gate,
        label="duplicate binding gate",
    )

    IMMUNE.write_text(text, encoding="utf-8")


def patch_loop() -> None:
    text = LOOP.read_text(encoding="utf-8")

    marker = r"""

# ----------------------------------------------------------------------------
# Registration.  sign_fn(payload_dict) MUST return a DSSE-style envelope dict
"""
    helper = r"""

def _append_run_record(run_chain, lock, record):
    \"\"\"Atomically append one run-of-runs record without lineage forks.\"\"\"
    with lock:
        stored = dict(record)
        stored["prev_run_hash"] = (
            run_chain[-1]["final_hash"] if run_chain else "GENESIS"
        )
        run_chain.append(stored)
        return stored


# ----------------------------------------------------------------------------
# Registration.  sign_fn(payload_dict) MUST return a DSSE-style envelope dict
"""
    text = replace_once(
        text,
        marker,
        helper,
        label="run-chain helper insertion",
    )

    old_chain = r"""    # In-memory chain of full runs (each run is itself a chained sub-ledger).
    _RUN_CHAIN = []  # list of {run_id, final_hash, prev_run_hash}

    # Bounded read model derived only from receipts created by _do_run. This is
"""
    new_chain = r"""    # In-memory chain of full runs (each run is itself a chained sub-ledger).
    _RUN_CHAIN = []  # list of {run_id, final_hash, prev_run_hash}
    _RUN_CHAIN_LOCK = threading.Lock()

    # Bounded read model derived only from receipts created by _do_run. This is
"""
    text = replace_once(
        text,
        old_chain,
        new_chain,
        label="run-chain lock declaration",
    )

    old_append = r"""        # record this whole run into the run-of-runs chain
        run_record = {"run_id": tr.trace_id, "final_hash": prev_hash,
                      "prev_run_hash": (_RUN_CHAIN[-1]["final_hash"] if _RUN_CHAIN else "GENESIS"),
                      "decision": decision}
        _RUN_CHAIN.append(run_record)

        result = {
"""
    new_append = r"""        # Record this whole run into the run-of-runs chain. Every caller of
        # _do_run (single-pass and governed-cycle paths) reaches this same atomic
        # append, so concurrent requests cannot observe one predecessor twice.
        run_record = _append_run_record(
            _RUN_CHAIN,
            _RUN_CHAIN_LOCK,
            {
                "run_id": tr.trace_id,
                "final_hash": prev_hash,
                "decision": decision,
            },
        )

        result = {
"""
    text = replace_once(
        text,
        old_append,
        new_append,
        label="atomic run-chain append",
    )

    LOOP.write_text(text, encoding="utf-8")


def patch_ui() -> None:
    text = OUROBOROS_UI.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "// Fetches from /api/a11oy/v1/ouroboros/run-all (POST {})\n",
        "// Authenticated POST to /api/a11oy/v1/ouroboros/run-all\n",
        label="UI header contract",
    )

    old_state = r"""  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);

  const runTests = useCallback(async () => {
    setRunState('running');
"""
    new_state = r"""  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [operatorToken, setOperatorToken] = useState('');

  const runTests = useCallback(async () => {
    const bearer = operatorToken.trim();
    if (!bearer) {
      setResult(null);
      setProgress(0);
      setErrorMsg('Operator bearer credential is required for this protected execution.');
      setRunState('error');
      return;
    }

    setRunState('running');
"""
    text = replace_once(
        text,
        old_state,
        new_state,
        label="session-only operator state",
    )

    old_fetch = r"""      const resp = await fetch('/api/a11oy/v1/ouroboros/run-all', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });
"""
    new_fetch = r"""      const resp = await fetch('/api/a11oy/v1/ouroboros/run-all', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${bearer}`,
        },
        body: JSON.stringify({}),
      });
"""
    text = replace_once(
        text,
        old_fetch,
        new_fetch,
        label="operator authorization header",
    )

    old_end = r"""    } catch (e: unknown) {
      clearInterval(interval);
      setProgress(0);
      setErrorMsg(e instanceof Error ? e.message : String(e));
      setRunState('error');
    }
  }, []);
"""
    new_end = r"""    } catch (e: unknown) {
      clearInterval(interval);
      setProgress(0);
      setErrorMsg(e instanceof Error ? e.message : String(e));
      setRunState('error');
    } finally {
      // Never retain operator authority after the request completes.
      setOperatorToken('');
    }
  }, [operatorToken]);
"""
    text = replace_once(
        text,
        old_end,
        new_end,
        label="operator credential clearing",
    )

    old_button = r"""        {/* Run button */}
        <div style={{ marginBottom: '2rem' }}>
          <button
"""
    new_button = r"""        {/* Run button */}
        <div style={{ marginBottom: '2rem' }}>
          <label style={{ display: 'block', maxWidth: 520, marginBottom: '0.85rem' }}>
            <span
              style={{
                display: 'block',
                marginBottom: '0.4rem',
                color: '#c9b787',
                fontSize: '0.78rem',
                fontWeight: 700,
              }}
            >
              Operator bearer credential
            </span>
            <input
              aria-label="Operator bearer credential"
              type="password"
              autoComplete="off"
              spellCheck={false}
              value={operatorToken}
              onChange={(event) => setOperatorToken(event.target.value)}
              disabled={runState === 'running'}
              style={{
                boxSizing: 'border-box',
                width: '100%',
                border: '1px solid rgba(201,183,135,0.35)',
                borderRadius: 8,
                background: 'rgba(255,255,255,0.04)',
                color: '#e8e0f0',
                padding: '0.65rem 0.75rem',
                fontFamily: 'JetBrains Mono, monospace',
              }}
            />
            <span
              style={{
                display: 'block',
                marginTop: '0.4rem',
                color: '#6a5a8a',
                fontSize: '0.72rem',
              }}
            >
              Used for this request only, never written to storage, and cleared when the request ends.
            </span>
          </label>
          <button
"""
    text = replace_once(
        text,
        old_button,
        new_button,
        label="operator credential input",
    )

    OUROBOROS_UI.write_text(text, encoding="utf-8")


TEST_CONTENT = r"""# SPDX-License-Identifier: Apache-2.0
\"\"\"Adversarial regressions for the Codex findings left after PR #1986.\"\"\"
from __future__ import annotations

import threading
import time
from pathlib import Path

import szl_agentic_loop as loop
import szl_immune as immune


ROOT = Path(__file__).resolve().parents[1]


def _signed_payload(request_id: str) -> dict:
    return {
        "requestId": request_id,
        "program": "lorenz",
        "mode": "OP",
        "steps": 320,
        "agent": {
            "nexus": {
                "requestId": request_id,
                "program": "lorenz",
                "mode": "OP",
                "steps": 320,
                "inputHash": "a" * 64,
                "outputHash": "b" * 64,
                "invariantsHold": True,
                "final": {"x": 1.0, "y": 2.0, "z": 3.0},
            }
        },
    }


def _run_lorenz(payload_mutator) -> dict:
    seen: dict[str, str] = {}

    def post(_url: str, body: dict):
        seen["request_id"] = body["requestId"]
        return 201, {
            "requestId": body["requestId"],
            "governed": {
                "pass": True,
                "receipt": {"payloadType": "application/vnd.in-toto+json"},
            },
        }, None

    def verify(_receipt: dict):
        payload = _signed_payload(seen["request_id"])
        payload_mutator(payload, seen["request_id"])
        return {
            "verified": True,
            "keyid_expected": "active-key",
            "payload_decoded": payload,
        }

    return immune._nexus_lorenz(post=post, verify=verify)


def test_nested_nexus_identity_cannot_inherit_a_trusted_outer_request() -> None:
    def substitute_nested(payload: dict, _request_id: str) -> None:
        payload["agent"]["nexus"]["requestId"] = "substituted-execution"

    result = _run_lorenz(substitute_nested)
    assert result["sealed"] is False
    assert result["receipt_verification"]["verified"] is True
    assert result["receipt_verification"]["request_binding"] is False


def test_conflicting_outer_and_nested_duplicates_fail_closed() -> None:
    def conflict_outer(payload: dict, _request_id: str) -> None:
        payload["requestId"] = "conflicting-outer-request"

    result = _run_lorenz(conflict_outer)
    assert result["sealed"] is False
    assert result["receipt_verification"]["request_binding"] is False


def test_receipt_verification_reports_the_key_that_actually_verified() -> None:
    verdict = immune._verify_nexus_receipt(
        {"payloadType": "application/vnd.in-toto+json"},
        verify=lambda _receipt: {
            "verified": True,
            "keyid_expected": "current-active-key",
            "signatures": [
                {
                    "keyid": "retained-rotation-key",
                    "verified": True,
                    "verified_by_keyid": "retained-rotation-key",
                }
            ],
            "payload_decoded": {"agent": {"nexus": {}}},
        },
    )
    assert verdict["verified"] is True
    assert verdict["keyid"] == "retained-rotation-key"


class _SlowChain(list):
    def __getitem__(self, index):
        time.sleep(0.002)
        return super().__getitem__(index)


def test_run_chain_atomic_append_prevents_concurrent_lineage_forks() -> None:
    chain = _SlowChain()
    lock = threading.Lock()
    workers = 24
    barrier = threading.Barrier(workers)

    def append(index: int) -> None:
        barrier.wait()
        loop._append_run_record(
            chain,
            lock,
            {
                "run_id": f"run-{index}",
                "final_hash": f"hash-{index}",
                "decision": "ALLOW",
            },
        )

    threads = [threading.Thread(target=append, args=(index,)) for index in range(workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)
        assert not thread.is_alive()

    assert len(chain) == workers
    assert chain[0]["prev_run_hash"] == "GENESIS"
    for previous, current in zip(chain, chain[1:]):
        assert current["prev_run_hash"] == previous["final_hash"]


def test_ouroboros_ui_sends_session_only_operator_authority() -> None:
    source = (ROOT / "src/pages/Ouroboros.tsx").read_text(encoding="utf-8")
    assert 'type="password"' in source
    assert "Authorization: `Bearer ${bearer}`" in source
    assert "setOperatorToken('')" in source
    assert "localStorage" not in source
    assert "sessionStorage" not in source
"""


def write_tests() -> None:
    TEST.write_text(TEST_CONTENT, encoding="utf-8")


def patch_workcell() -> None:
    text = WORKCELL.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "- `state`: `OPEN_REPAIR`",
        "- `state`: `IMPLEMENTED_PENDING_EXACT_HEAD_CI`",
        label="workcell state",
    )
    appendix = r"""

## Forward implementation

The current-main successor now carries the four forward fixes:

- nested `agent.nexus` binding is authoritative and conflicting duplicates fail closed;
- every shared run-ledger append is serialized through one lock-protected primitive;
- the registered Ouroboros UI sends a session-only bearer credential and clears it after the request;
- rotated-key verification records the successful `verified_by_keyid`.

Focused adversarial regressions are in
`tests/test_post_merge_1986_review_repairs.py`. This state is not a merge or
deployment claim; exact-head CI and independent review remain required.
"""
    if "## Forward implementation" in text:
        raise SystemExit("workcell implementation appendix already present")
    WORKCELL.write_text(text.rstrip() + appendix + "\n", encoding="utf-8")


def main() -> int:
    patch_immune()
    patch_loop()
    patch_ui()
    write_tests()
    patch_workcell()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
