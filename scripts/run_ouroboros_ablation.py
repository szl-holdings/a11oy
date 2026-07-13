#!/usr/bin/env python3
"""Run the preregistered Ouroboros governance ablation.

The runner exercises the real in-process A11oy routes for production variants.
Security-stage removals are proposal-only or evidence-removal negative controls;
they never disable the production gate or execute an external action.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import platform
import subprocess
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROTOCOL = ROOT / "benchmarks" / "ouroboros_ablation" / "protocol-v0.1.0.json"
DEFAULT_RECEIPT = ROOT / "benchmarks" / "ouroboros_ablation" / "receipt-v0.1.0.json"


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha(value: Any) -> str:
    return _sha256_bytes(_canonical_bytes(value))


def _git(*args: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return completed.stdout.strip() or None
    except (FileNotFoundError, subprocess.SubprocessError):
        return None


@contextmanager
def _environment(**updates: str | None) -> Iterator[None]:
    before = {key: os.environ.get(key) for key in updates}
    try:
        for key, value in updates.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        yield
    finally:
        for key, value in before.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def verify_cycle_chain(chain: list[dict[str, Any]]) -> bool:
    """Independently replay the cycle-level hash chain."""
    previous = "GENESIS"
    for expected_seq, entry in enumerate(chain):
        if entry.get("seq") != expected_seq or entry.get("prev_hash") != previous:
            return False
        expected_hash = _sha(
            {
                "seq": entry.get("seq"),
                "kind": entry.get("kind"),
                "body": entry.get("body"),
                "prev_hash": entry.get("prev_hash"),
            }
        )
        if entry.get("hash") != expected_hash:
            return False
        previous = expected_hash
    return bool(chain)


def self_feed_coverage(trace: list[dict[str, Any]]) -> float:
    """Fraction of post-first iterations bound to the prior final hash."""
    if len(trace) <= 1:
        return 1.0
    bound = sum(
        trace[index].get("precondition_hash") == trace[index - 1].get("chain_final_hash")
        for index in range(1, len(trace))
    )
    return bound / (len(trace) - 1)


def _mutate_first_body(chain: list[dict[str, Any]]) -> list[dict[str, Any]]:
    mutated = copy.deepcopy(chain)
    if mutated:
        body = dict(mutated[0].get("body") or {})
        body["ablation_mutation"] = "one-byte-equivalent-change"
        mutated[0]["body"] = body
    return mutated


def _post_json(client: Any, path: str, body: dict[str, Any]) -> dict[str, Any]:
    response = client.post(path, json=body)
    if response.status_code != 200:
        raise RuntimeError(f"{path} returned HTTP {response.status_code}: {response.text[:240]}")
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError(f"{path} returned a non-object JSON payload")
    return payload


def run_protocol(protocol: dict[str, Any], client: Any) -> dict[str, Any]:
    scenarios = protocol["scenarios"]
    rows: list[dict[str, Any]] = []
    with _environment(
        A11OY_OUROBOROS="1",
        A11OY_SGH=None,
        A11OY_DRIFT_GUARD=None,
        A11OY_COUNTERFACTUAL=None,
        A11OY_APPROVAL_INTERRUPT=None,
        A11OY_MULTIWITNESS=None,
    ):
        for scenario in scenarios:
            base = dict(scenario["body"])
            expected = scenario["expected_decision"]
            single = _post_json(client, "/api/a11oy/v1/agent/run", base)
            full = _post_json(
                client,
                "/api/a11oy/v1/agent/cycle",
                {**base, "budget": 5, "eps": 0.01},
            )
            budget_only = _post_json(
                client,
                "/api/a11oy/v1/agent/cycle",
                {**base, "budget": 5, "eps": -1.0},
            )
            chain = list(full.get("cycle_receipt_chain") or [])
            trace = list(full.get("trust_trace") or [])
            mutated_chain = _mutate_first_body(chain)
            rows.append(
                {
                    "scenario_id": scenario["id"],
                    "expected_decision": expected,
                    "production": {
                        "single_pass": {
                            "decision": single.get("decision"),
                            "matches_expected": single.get("decision") == expected,
                            "chain_final_hash": single.get("chain_final_hash"),
                        },
                        "full_loop": {
                            "decision": (full.get("iterations") or [{}])[-1].get("decision"),
                            "matches_expected": (full.get("iterations") or [{}])[-1].get("decision") == expected,
                            "final_status": full.get("final_status"),
                            "iterations_run": full.get("iterations_run"),
                            "budget": full.get("budget"),
                            "chain_integrity": verify_cycle_chain(chain),
                            "self_feed_coverage": self_feed_coverage(trace),
                            "signed_cycle_receipt_present": full.get("signed_cycle_receipt") is not None,
                        },
                        "budget_only": {
                            "decision": (budget_only.get("iterations") or [{}])[-1].get("decision"),
                            "matches_expected": (budget_only.get("iterations") or [{}])[-1].get("decision") == expected,
                            "final_status": budget_only.get("final_status"),
                            "iterations_run": budget_only.get("iterations_run"),
                            "budget": budget_only.get("budget"),
                        },
                    },
                    "negative_controls": {
                        "gate_removed_proposal_only": {
                            "decision": "SIMULATED_ALLOW",
                            "would_be_unsafe_approval": expected == "DENY",
                            "executed": False,
                        },
                        "self_feed_removed_trace": {
                            "coverage": 0.0,
                            "executed": False,
                        },
                        "verifier_present": {
                            "clean_chain_accepted": verify_cycle_chain(chain),
                            "mutated_chain_rejected": not verify_cycle_chain(mutated_chain),
                        },
                        "verifier_removed_trace": {
                            "mutated_chain_verdict": "NOT_EVALUATED",
                            "executed": False,
                        },
                    },
                }
            )

    deny_rows = [row for row in rows if row["expected_decision"] == "DENY"]
    allow_rows = [row for row in rows if row["expected_decision"] == "ALLOW"]
    total = len(rows)
    metrics = {
        "scenario_count": total,
        "deny_scenario_count": len(deny_rows),
        "decision_agreement": {
            variant: sum(row["production"][variant]["matches_expected"] for row in rows) / total
            for variant in ("single_pass", "full_loop", "budget_only")
        },
        "unsafe_production_approval_rate": sum(
            row["production"]["full_loop"]["decision"] == "ALLOW" for row in deny_rows
        ) / len(deny_rows),
        "unsafe_proposal_only_negative_control_rate": sum(
            row["negative_controls"]["gate_removed_proposal_only"]["would_be_unsafe_approval"]
            for row in deny_rows
        ) / len(deny_rows),
        "full_loop_chain_integrity": sum(
            row["production"]["full_loop"]["chain_integrity"] for row in rows
        ) / total,
        "full_loop_self_feed_coverage": sum(
            row["production"]["full_loop"]["self_feed_coverage"] for row in rows
        ) / total,
        "mutation_detection_rate": sum(
            row["negative_controls"]["verifier_present"]["mutated_chain_rejected"] for row in rows
        ) / total,
        "full_loop_budget_violations": sum(
            int(row["production"]["full_loop"]["iterations_run"] or 0)
            > int(row["production"]["full_loop"]["budget"] or 0)
            for row in rows
        ),
        "stable_allow_adaptive_iterations": [
            row["production"]["full_loop"]["iterations_run"] for row in allow_rows
        ],
        "stable_allow_budget_only_iterations": [
            row["production"]["budget_only"]["iterations_run"] for row in allow_rows
        ],
        "task_accuracy_measured": False,
        "operational_outcomes_measured": False,
        "mathematical_convergence_claimed": False,
    }
    metrics["stable_allow_adaptive_iterations_less_than_budget_only"] = all(
        int(adaptive) < int(budget_only)
        for adaptive, budget_only in zip(
            metrics["stable_allow_adaptive_iterations"],
            metrics["stable_allow_budget_only_iterations"],
        )
    )
    return {"rows": rows, "metrics": metrics}


def evaluate_acceptance(protocol: dict[str, Any], metrics: dict[str, Any]) -> dict[str, Any]:
    expected = protocol["acceptance"]
    checks = {
        "decision_agreement": all(value == expected["decision_agreement"] for value in metrics["decision_agreement"].values()),
        "full_loop_chain_integrity": metrics["full_loop_chain_integrity"] == expected["full_loop_chain_integrity"],
        "full_loop_self_feed_coverage": metrics["full_loop_self_feed_coverage"] == expected["full_loop_self_feed_coverage"],
        "mutation_detection_rate": metrics["mutation_detection_rate"] == expected["mutation_detection_rate"],
        "unsafe_production_approval_rate": metrics["unsafe_production_approval_rate"] == expected["unsafe_production_approval_rate"],
        "full_loop_budget_violations": metrics["full_loop_budget_violations"] == expected["full_loop_budget_violations"],
        "stable_allow_adaptive_iterations_less_than_budget_only": metrics["stable_allow_adaptive_iterations_less_than_budget_only"] is expected["stable_allow_adaptive_iterations_less_than_budget_only"],
    }
    return {"checks": checks, "passed": all(checks.values())}


def build_receipt(protocol_path: Path = DEFAULT_PROTOCOL) -> dict[str, Any]:
    protocol_bytes = protocol_path.read_bytes()
    protocol = json.loads(protocol_bytes)
    from starlette.testclient import TestClient
    import serve

    with TestClient(serve.app) as client:
        result = run_protocol(protocol, client)
    acceptance = evaluate_acceptance(protocol, result["metrics"])
    receipt = {
        "schema": "szl.ouroboros-governance-ablation-receipt/v1",
        "protocol_id": protocol["protocol_id"],
        "protocol_sha256": _sha256_bytes(protocol_bytes),
        "protocol_status": protocol["status"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "preregistration_commit": _git("log", "-1", "--format=%H", "--", str(protocol_path.relative_to(ROOT))),
        "run_commit": _git("rev-parse", "HEAD"),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "execution": "local in-process TestClient",
            "external_action_execution": False,
        },
        "result": result,
        "acceptance": acceptance,
        "claim_boundary": {
            "status": "LOCAL_MEASURED_GOVERNANCE_EVIDENCE",
            "does_not_establish": protocol["scope"]["not_measured"],
            "note": "Production security stages were not disabled. Removal variants are offline negative controls only.",
        },
    }
    receipt["receipt_sha256"] = _sha(receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--out", type=Path, default=DEFAULT_RECEIPT)
    args = parser.parse_args()
    receipt = build_receipt(args.protocol.resolve())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "out": str(args.out),
        "receipt_sha256": receipt["receipt_sha256"],
        "acceptance_passed": receipt["acceptance"]["passed"],
        "claim_status": receipt["claim_boundary"]["status"],
    }, sort_keys=True))
    return 0 if receipt["acceptance"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
