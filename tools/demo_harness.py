#!/usr/bin/env python3
"""demo_harness.py — the 12-step acceptance demo (CANON section 4).

The demo IS the product. It runs the canonical sequence end to end against
the v1 slice and prints PASS/FAIL per step:

  1  default DENY on an unmatched action
  2  signed receipt on an explicitly allowed action
  3  tamper one byte of the signed artifact
  4  offline verification of the tampered artifact fails
  5  remove evidence; claim checks report INCOMPLETE, never PASS
  6  simulate outage; append is ACKed LOCAL-only and stays PENDING_SYNC
  7  PENDING_SYNC survives re-read; a sync marker clears it exactly
  8  replay is non-mutating and never double-executes (idempotency keys)
  9  Article 12 conformance report: all 11 entries MAPPED against a receipt
  10 flight recorder chain integrity: no gaps, no corruptions
  11 redaction commitment: salted-hash commitment verifies and rejects
  12 closure receipt: weak time proof recorded truthfully, never hidden

Usage: python3 tools/demo_harness.py [--root .] [--conformance PATH]
Exit 0 only when all 12 steps pass. Exit 1 if any step fails. Exit 2 on
harness error. Expected runtime: seconds; the 90-second budget in CANON
section 4 is for the recorded human walkthrough of this same sequence.

--conformance selects the Article 12 logging conformance profile used by
step 9, relative to --root (default:
evidence/conformance/eu-ai-act-article-12.v1.yaml, the round-10 payload
profile carried by the merged szl-holdings/a11oy tree). The unversioned
evidence/conformance/eu-ai-act-article-12.yaml is an older, structurally
different artifact (no entries list) with its own consumers
(release_gate.py, the bootstraps, the claims ledger); it is preserved
untouched and is not a valid step-9 profile.
"""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import importlib.util
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

EXIT_ALL_PASS = 0
EXIT_STEP_FAILED = 1
EXIT_ERROR = 2


def _load_miniyaml(root: Path):
    module_path = root / "tools" / "szl_miniyaml.py"
    spec = importlib.util.spec_from_file_location("szl_miniyaml", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _jsonpath(data: dict, path: str):
    """Resolve a simple $.a.b.c path against a mapping tree."""
    if not path.startswith("$."):
        raise ValueError(f"unsupported path {path!r}")
    node = data
    for part in path[2:].split("."):
        if not isinstance(node, dict) or part not in node:
            raise KeyError(path)
        node = node[part]
    return node


DEFAULT_CONFORMANCE = Path("evidence/conformance/eu-ai-act-article-12.v1.yaml")


def run_demo(
    root: Path, conformance_rel: Path | None = None
) -> list[tuple[str, bool, str]]:
    conformance_path = root / (conformance_rel or DEFAULT_CONFORMANCE)
    sys.path.insert(0, str(root / "src"))
    from a11oy.flight_recorder import SegmentedFlightRecorder
    from a11oy.policy import Effect, Rule, TypedPolicyEngine
    from a11oy.schemas import (
        Actor,
        Completeness,
        EvidenceItem,
        GovernedActionPredicate,
        GovernedActionReceipt,
        HumanApproval,
        ObservationWindow,
        PolicyDecisionRecord,
        RedactionCommitment,
        SideEffectClass,
    )
    from a11oy.signing import DemoEd25519Backend
    from a11oy.verifier import ClaimState, OfflineVerifier, TimeStrength

    miniyaml = _load_miniyaml(root)

    results: list[tuple[str, bool, str]] = []

    def step(title: str, fn) -> None:
        try:
            detail = fn()
            results.append((title, True, detail))
        except Exception as exc:  # a crashed step is a failed step
            results.append((title, False, f"{type(exc).__name__}: {exc}"))

    # ---- shared fixtures --------------------------------------------------
    engine = TypedPolicyEngine(
        [
            Rule(
                "allow-deploy",
                Effect.ALLOW,
                ("deploy.patch",),
                side_effect_classes=(SideEffectClass.REVERSIBLE,),
                evidence_obligations=("git-diff-hash", "test-output-hash"),
                requires_human_approval=True,
            ),
            Rule(
                "irrev-guard",
                Effect.ALLOW,
                ("deploy.*",),
                side_effect_classes=(
                    SideEffectClass.REVERSIBLE,
                    SideEffectClass.IRREVERSIBLE,
                ),
                evidence_obligations=("rollback-plan",),
            ),
        ]
    )
    allowed = engine.evaluate(
        action_type="deploy.patch", side_effect_class=SideEffectClass.REVERSIBLE
    )
    founder = Actor(actor_id="u-stephen-lutar", display_name="Stephen Lutar")
    backend = DemoEd25519Backend()
    handler = OfflineVerifier({backend.keyid: backend.public_key_raw})
    salt = os.urandom(16)
    preimage = b"act-prod-0042"  # the plaintext the commitment commits to

    def build_receipt(action_id: str, evidence_kinds: tuple[str, ...]) -> GovernedActionReceipt:
        evidence = [
            EvidenceItem(
                evidence_id=f"ev-{kind}",
                kind=kind,
                sha256=hashlib.sha256(f"{action_id}:{kind}".encode()).hexdigest(),
            )
            for kind in evidence_kinds
        ]
        predicate = GovernedActionPredicate(
            action_id=action_id,
            actor=founder,
            action_type="deploy.patch",
            side_effect_class=SideEffectClass.REVERSIBLE,
            evidence=evidence,
            completeness=(
                Completeness.COMPLETE if evidence else Completeness.INCOMPLETE
            ),
            redaction_commitments=[
                RedactionCommitment.create(
                    "rc-action-id",
                    "$.predicate.action_id",
                    preimage,
                    salt,
                )
            ],
            rfc3161_token="UNAVAILABLE",  # recorded, not blank (Zero-Bandaid)
            ntp_synced=False,
        )
        now = datetime.now(timezone.utc)
        return GovernedActionReceipt(
            receipt_id=f"rcpt-{action_id}",
            predicate=predicate,
            decision=PolicyDecisionRecord(
                decision="ALLOW",
                reason=allowed.reason,
                first_match_rule=allowed.first_match_rule,
                matched_rules=list(allowed.matched_rules),
                evidence_obligations=list(allowed.evidence_obligations),
                effective_side_effect_class=allowed.effective_side_effect_class,
                requires_human_approval=allowed.requires_human_approval,
            ),
            human_approval=HumanApproval(
                approver=founder,
                approved_at=now,
                rationale="diff reviewed, tests passed, rollback plan attached",
            ),
            observation_window=ObservationWindow(
                start=now, end=now + timedelta(minutes=30)
            ),
            retention_days=180,
            issued_at=now,
            generator="a11oy-demo/0.1.0",
        )

    full_receipt = build_receipt(
        "act-prod-0042", ("git-diff-hash", "test-output-hash", "rollback-plan")
    )
    strip_receipt = build_receipt("act-prod-0043", ())
    envelope = backend.sign(full_receipt.model_dump(mode="json"))

    # ---- steps ------------------------------------------------------------

    def step1() -> str:
        decision = engine.evaluate(
            action_type="read.metrics",
            side_effect_class=SideEffectClass.READ_ONLY,
        )
        assert not decision.allowed and decision.first_match_rule is None
        return f"unmatched action denied ({decision.reason})"

    def step2() -> str:
        result = handler.verify_envelope(
            envelope, required_obligations=tuple(allowed.evidence_obligations)
        )
        assert result.verdict == "VALID" and result.signature_valid, result.problems
        return "VALID receipt issued and verified (backend: a11oy-demo-ed25519)"

    def step3() -> str:
        raw = bytearray(base64.b64decode(envelope["payload"]))
        raw[40] ^= 0x01  # one byte
        tampered = copy.deepcopy(envelope)
        tampered["payload"] = base64.b64encode(bytes(raw)).decode("ascii")
        run_demo.tampered = tampered  # passed to step 4
        return f"byte 40 of {len(raw)} flipped in the signed payload"

    def step4() -> str:
        tampered = run_demo.tampered
        result = handler.verify_envelope(
            tampered, required_obligations=tuple(allowed.evidence_obligations)
        )
        assert result.verdict == "INVALID" and not result.signature_valid
        return "offline verification fails on the tampered artifact (INVALID)"

    def step5() -> str:
        env = backend.sign(strip_receipt.model_dump(mode="json"))
        result = handler.verify_envelope(
            env, required_obligations=tuple(allowed.evidence_obligations)
        )
        assert result.signature_valid
        assert result.claim_state is ClaimState.INCOMPLETE and result.verdict == "INCOMPLETE"
        assert result.verdict != "VALID"
        return "evidence removed: claim INCOMPLETE (never PASS); signature stays valid — signature is not truth"

    def step6() -> str:
        tmpdir = tempfile.mkdtemp(prefix="a11oy-demo-")
        run_demo.log_path = Path(tmpdir) / "flight.a11yfr"
        recorder = SegmentedFlightRecorder(run_demo.log_path)
        ack_rcpt = recorder.append(
            {"receipt": full_receipt.receipt_id}, idempotency_key="idem-rcpt-0042"  # gitleaks:allow — demo idempotency token, not a credential
        )
        ack_patch = recorder.append(
            {"patch": "applied-by-bot"}, idempotency_key="idem-patch-0042"  # gitleaks:allow — demo idempotency token, not a credential
        )
        assert ack_rcpt.durability == "LOCAL" and ack_rcpt.sync_state == "PENDING_SYNC"
        assert ack_patch.seq == ack_rcpt.seq + 1
        run_demo.recorder = recorder
        return "outage simulated: appends ACKed LOCAL, seqs pending remote sync"

    def step7() -> str:
        reread = SegmentedFlightRecorder(run_demo.log_path)  # fresh reader, "after" the outage
        pending = reread.pending_sync()
        assert pending == [1, 2], pending
        reread.mark_synced([1, 2])
        assert reread.pending_sync() == []
        return "PENDING_SYNC survived re-read; sync marker cleared exactly seqs 1-2"

    def step8() -> str:
        executed = {"idem-rcpt-0042"}
        todo = [p["idempotency_key"] for p in run_demo.recorder.replay(executed)]
        assert todo == ["idem-patch-0042"], todo
        executed.add("idem-patch-0042")  # recovery applies the patch once
        again = list(run_demo.recorder.replay(executed))
        assert again == []
        return "replay yielded only the unexecuted action; second replay yields nothing — no double-execute"

    def step9() -> str:
        profile = miniyaml.load(
            conformance_path.read_text(encoding="utf-8")
        )
        validators = {
            "nonempty_string": lambda v: isinstance(v, str) and len(v) > 0,
            "const_false": lambda v: v is False,
            "boolean": lambda v: isinstance(v, bool),
            "gte_180": lambda v: isinstance(v, int) and v >= 180,
            "enum_side_effect_class": lambda v: v
            in {c.value for c in SideEffectClass},
            "enum_allow_deny": lambda v: v in {"ALLOW", "DENY"},
            "rfc3339_timestamp": lambda v: isinstance(v, str)
            and datetime.fromisoformat(v.replace("Z", "+00:00")) is not None,
        }
        receipt_dict = full_receipt.model_dump(mode="json")
        entries = profile["entries"]
        for entry in entries:
            value = _jsonpath(receipt_dict, entry["jsonpath"])
            ok = validators[entry["validator"]](value)
            assert ok, f"conformance entry {entry['provision']} failed"
            assert entry["status"] == "MAPPED"
        assert len(entries) == 11, len(entries)
        assert profile["retention_minimum_days"] == 180
        return "11 of 11 Article 12 entries MAPPED and satisfied; retention floor 180 days"

    def step10() -> str:
        report = run_demo.recorder.verify_integrity()
        assert report.header_ok and report.chain_ok
        assert report.gaps == [] and report.corruptions == []
        assert report.first_seq == 1 and report.last_seq == 3 and report.segments == 3
        return "chain integrity clean: seqs 1-3, no gaps, no corruptions"

    def step11() -> str:
        commitment = full_receipt.predicate.redaction_commitments[0]
        assert commitment.verify(preimage)
        assert not commitment.verify(b"act-prod-9999")
        return "redaction commitment verifies the true plaintext and rejects a forged one"

    def step12() -> str:
        state, strength, problems = handler.check_claims(
            full_receipt.model_dump(mode="json"),
            required_obligations=tuple(allowed.evidence_obligations),
            require_strong_time=True,
        )
        assert strength is TimeStrength.WEAK
        assert state is ClaimState.INCOMPLETE and problems
        # Without the strong-time profile, the same receipt passes claims.
        state2, strength2, _ = handler.check_claims(
            full_receipt.model_dump(mode="json"),
            required_obligations=tuple(allowed.evidence_obligations),
        )
        assert state2 is ClaimState.PASS and strength2 is TimeStrength.WEAK
        return "closure receipt: weak time proof (TSA unavailable, clock unsynced) recorded and disclosed, never hidden"

    steps = [
        ("01 default DENY", step1),
        ("02 signed receipt on allow", step2),
        ("03 tamper one byte", step3),
        ("04 offline verify fails", step4),
        ("05 remove evidence = INCOMPLETE", step5),
        ("06 outage: LOCAL ack, PENDING_SYNC", step6),
        ("07 PENDING_SYNC survives, then syncs", step7),
        ("08 replay without double-execution", step8),
        ("09 Article 12 conformance report", step9),
        ("10 chain integrity", step10),
        ("11 redaction commitment check", step11),
        ("12 closure receipt, honest time", step12),
    ]
    for title, fn in steps:
        step(title, fn)
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=".", help="repo root (contains tools/ and src/)")
    parser.add_argument(
        "--conformance",
        default=None,
        help="Article 12 profile path, relative to --root "
        "(default: evidence/conformance/eu-ai-act-article-12.v1.yaml)",
    )
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    conformance_rel = Path(args.conformance) if args.conformance else None
    try:
        results = run_demo(root, conformance_rel)
    except ImportError as exc:
        print(
            f"demo_harness ERROR: cannot import a11oy from {root / 'src'}: {exc}",
            file=sys.stderr,
        )
        return EXIT_ERROR
    except Exception as exc:
        print(f"demo_harness ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_ERROR

    failed = 0
    for title, passed, detail in results:
        print(f"{'PASS' if passed else 'FAIL'}  {title} — {detail}")
        if not passed:
            failed += 1
    print(f"{len(results) - failed}/{len(results)} steps passing")
    if failed:
        return EXIT_STEP_FAILED
    return EXIT_ALL_PASS


if __name__ == "__main__":
    sys.exit(main())
