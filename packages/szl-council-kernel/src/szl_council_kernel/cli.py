from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Mapping

from .benchmark import run_benchmark
from .canary import build_deterministic_council, run_canary
from .canonical import canonical_json_text, digest_object, isoformat_utc, utc_now
from .enums import ActionKind, AutonomyLevel, BlastRadius, CouncilRole, CouncilVote, RiskClass
from .foundry import ResearchFoundry
from .models import (
    ActionRequest,
    AutonomyEnvelope,
    BudgetLimits,
    CapabilityGrant,
    ConditionSpec,
    CouncilPolicy,
    EpochBinding,
    GateInput,
    RetryPolicy,
    RollbackPlan,
)
from .proof import Ed25519Signer
from .schema_registry import load_schema, schema_names
from .state_bus import StateBus
from .workflow import CouncilKernel


def _write(value: Any, output: str | None) -> None:
    text = canonical_json_text(value, pretty=True)
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    print(text, end="")


def _load(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _local_spec(spec: Mapping[str, Any], *, db: str, sandbox: str, key_path: str) -> dict[str, Any]:
    now = utc_now().replace(microsecond=0)
    expiry = now + timedelta(hours=int(spec.get("expiry_hours", 1)))
    now_text = isoformat_utc(now)
    expiry_text = isoformat_utc(expiry)
    risk = RiskClass(str(spec.get("risk_class", "LOW")))
    target = str(spec["target"])
    content = str(spec["content"])
    expected_text = str(spec.get("expected_text", content))
    policy = CouncilPolicy.from_dict(spec.get("policy"))
    case_id = str(spec.get("case_id", "case-local-" + hashlib.sha256((target + content).encode()).hexdigest()[:16]))
    epochs = EpochBinding(
        model="model:local-test-fourfold@1",
        tool="tool:sandbox_fs@1",
        policy=policy.digest,
        evidence="evidence:local-spec@1",
        state="state:szl-state-bus@1",
        retrieval="retrieval:local-isolated@1",
    )
    envelope = AutonomyEnvelope(
        case_id=case_id,
        principal=str(spec.get("principal", "spiffe://local.szl.test/owner")),
        subject=str(spec.get("subject", "Execute one reversible local file mutation")),
        exact_targets=(target,),
        capabilities=("file:write", "file:rollback"),
        tools=("sandbox_fs",),
        risk_class=risk,
        blast_radius=BlastRadius.SANDBOX,
        autonomy_level=AutonomyLevel.A2_REVERSIBLE,
        budgets=BudgetLimits(max_cost_usd=0, max_duration_seconds=60, max_tool_calls=1, max_mutations=1, max_branches=1, max_recursion=0),
        preconditions=(ConditionSpec("FILE_ABSENT", target, True),),
        postconditions=(ConditionSpec("TEXT_CONTAINS", target, expected_text),),
        idempotency_key=str(spec.get("idempotency_key", "idem-" + hashlib.sha256((case_id + target).encode()).hexdigest()[:20])),
        retry_policy=RetryPolicy(max_attempts=1),
        rollback_plan=RollbackPlan(),
        epochs=epochs,
        required_roles=tuple(CouncilRole),
        required_council_state="QUORUM_VERIFIED",
        receipt_required=True,
        transparency_required=risk in {RiskClass.HIGH, RiskClass.CRITICAL},
        issued_at=now_text,
        expires_at=expiry_text,
    )
    grant = CapabilityGrant(
        grant_id="grant-" + hashlib.sha256(case_id.encode()).hexdigest()[:20],
        principal=envelope.principal,
        capabilities=envelope.capabilities,
        target_patterns=(target,),
        tools=envelope.tools,
        budgets=envelope.budgets,
        issued_at=now_text,
        expires_at=expiry_text,
    )
    votes_value = spec.get("votes", {})
    votes = {role: CouncilVote(str(votes_value.get(role.value, "SUPPORT"))) for role in CouncilRole}
    case, settlement = build_deterministic_council(
        envelope=envelope,
        policy=policy,
        risk_class=risk,
        value_claimed=bool(spec.get("value_claimed", False)),
        votes=votes,
        correlated=bool(spec.get("correlated_test_council", False)),
        session_time=now_text,
        expiry=expiry_text,
    )
    diversity = float(settlement["result"]["diversity"]["joint_effective_size"])
    gate_input = GateInput(
        council_state=settlement["result"]["state"],
        risk_class=risk,
        effective_diversity=diversity,
        evidence_completeness=float(spec.get("evidence_completeness", 0.95)),
        proof_completeness=float(spec.get("proof_completeness", 0.95)),
        novelty_score=float(spec.get("novelty_score", 0.05)),
        ambiguity_score=float(spec.get("ambiguity_score", 0.05)),
        irreversibility_score=float(spec.get("irreversibility_score", 0.02)),
        drift_score=float(spec.get("drift_score", 0.0)),
        expected_blast_radius=float(spec.get("expected_blast_radius", 0.02)),
        historical_false_green_rate=float(spec.get("historical_false_green_rate", 0.0)),
        calibration_sample_size=int(spec.get("calibration_sample_size", 200)),
    )
    action = ActionRequest(
        action_id="action-" + hashlib.sha256((case_id + target).encode()).hexdigest()[:20],
        case_id=case_id,
        grant_id=grant.grant_id,
        kind=ActionKind.FILE_WRITE,
        tool="sandbox_fs",
        target=target,
        content=content,
        expected_before_digest=None,
        idempotency_key=envelope.idempotency_key,
        postconditions=envelope.postconditions,
        metadata={"task_class": str(spec.get("task_class", "file_mutation")), "domain": str(spec.get("domain", "local"))},
    )
    signer = Ed25519Signer.load_or_create(key_path)
    kernel = CouncilKernel(db_path=db, sandbox_root=sandbox, receipt_signer=signer)
    run = kernel.run_case(case=case, envelope=envelope, grant=grant, settlement=settlement, gate_input=gate_input, action=action, now=now_text)
    return {
        **run,
        "local_test_council": True,
        "local_test_council_boundary": "FOUR DETERMINISTIC TEST IDENTITIES; NOT PRODUCTION INDEPENDENCE",
        "persistent_receipt_signer": signer.signer_state == "SIGNED_PERSISTENT",
    }


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="alloy-council", description="Proof-carrying autonomy kernel")
    ap.add_argument("--version", action="version", version="0.5.0rc1")
    sub = ap.add_subparsers(dest="command", required=True)

    cmd = sub.add_parser("canary", help="run deterministic full local canary")
    cmd.add_argument("--workdir", default="./run/canary")
    cmd.add_argument("--output")

    cmd = sub.add_parser("bench", help="run adversarial CouncilBench")
    cmd.add_argument("--output")

    cmd = sub.add_parser("verify-ledger", help="verify State Bus object and event chains")
    cmd.add_argument("--db", required=True)
    cmd.add_argument("--output")

    cmd = sub.add_parser("export-evidence", help="export portable State Bus evidence")
    cmd.add_argument("--db", required=True)
    cmd.add_argument("--output", required=True)

    cmd = sub.add_parser("schema", help="print a packaged JSON schema")
    cmd.add_argument("--name", choices=schema_names(), required=True)
    cmd.add_argument("--output")

    cmd = sub.add_parser("keygen", help="create or inspect a persistent Ed25519 receipt key")
    cmd.add_argument("--path", required=True)
    cmd.add_argument("--output")

    cmd = sub.add_parser("run-local", help="execute one bounded sandbox action using an explicit local test council")
    cmd.add_argument("--input", required=True)
    cmd.add_argument("--db", required=True)
    cmd.add_argument("--sandbox", required=True)
    cmd.add_argument("--signing-key", required=True)
    cmd.add_argument("--allow-local-test-council", action="store_true", required=True)
    cmd.add_argument("--output")

    cmd = sub.add_parser("foundry-register", help="register a discovered research artifact without promoting it")
    cmd.add_argument("--manifest", required=True)
    cmd.add_argument("--id", required=True)
    cmd.add_argument("--title", required=True)
    cmd.add_argument("--url", required=True)
    cmd.add_argument("--type", choices=["GITHUB", "GITLAB", "ARXIV", "PUBLICATION", "STANDARD", "LOCAL"], required=True)
    cmd.add_argument("--output")

    cmd = sub.add_parser("foundry-inventory", help="print the Research Foundry inventory")
    cmd.add_argument("--manifest", required=True)
    cmd.add_argument("--output")

    cmd = sub.add_parser("serve", help="serve read-mostly API and operator console")
    cmd.add_argument("--db", required=True)
    cmd.add_argument("--runtime-root", default="./run/api")
    cmd.add_argument("--host", default="127.0.0.1")
    cmd.add_argument("--port", type=int, default=8765)

    return ap


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "canary":
        value = run_canary(args.workdir)
        _write(value, args.output)
        return 0 if value["status"] == "PASS" else 1
    if args.command == "bench":
        value = run_benchmark()
        _write(value, args.output)
        return 0 if value["status"] == "PASS" else 1
    if args.command == "verify-ledger":
        value = StateBus(args.db).verify_chain()
        _write(value, args.output)
        return 0 if value["status"] == "PASS" else 1
    if args.command == "export-evidence":
        value = StateBus(args.db).export_evidence()
        _write(value, args.output)
        return 0 if value["verification"]["status"] == "PASS" else 1
    if args.command == "schema":
        _write(load_schema(args.name), args.output)
        return 0
    if args.command == "keygen":
        signer = Ed25519Signer.load_or_create(args.path)
        _write({"schema": "szl.signer-public-metadata/v1", **signer.verifier().to_dict(), "signer_state": signer.signer_state}, args.output)
        return 0
    if args.command == "run-local":
        value = _local_spec(_load(args.input), db=args.db, sandbox=args.sandbox, key_path=args.signing_key)
        _write(value, args.output)
        return 0 if value["status"] in {"VERIFIED", "ROLLED_BACK", "BLOCKED"} else 1
    if args.command == "foundry-register":
        foundry = ResearchFoundry(args.manifest)
        artifact = foundry.register(artifact_id=args.id, title=args.title, source_url=args.url, source_type=args.type)
        _write(artifact.to_dict(), args.output)
        return 0
    if args.command == "foundry-inventory":
        _write(ResearchFoundry(args.manifest).inventory(), args.output)
        return 0
    if args.command == "serve":
        try:
            import uvicorn
        except ImportError:
            print("uvicorn is not installed; install szl-council-kernel[api]", file=sys.stderr)
            return 2
        from .service import create_app
        uvicorn.run(create_app(db_path=args.db, runtime_root=args.runtime_root), host=args.host, port=args.port)
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
