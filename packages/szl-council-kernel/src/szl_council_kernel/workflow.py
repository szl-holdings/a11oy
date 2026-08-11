from __future__ import annotations

"""Deterministic Council Kernel workflow: deliberate, gate, execute, verify, settle."""

from datetime import datetime
from typing import Any, Mapping, Sequence

from .canonical import digest_object, isoformat_utc, utc_now
from .capability import BudgetAccount, authorize_action
from .enums import ReleaseDecision, WorkflowState
from .errors import AuthorizationError, IdempotencyConflict, IntegrityError, ValidationError
from .executor import SandboxExecutor
from .fourfold import verify_settlement
from .gate import EmpiricalReleaseGate
from .models import (
    ActionReceipt,
    ActionRequest,
    AutonomyEnvelope,
    CapabilityGrant,
    CouncilCase,
    GateInput,
    GateResult,
)
from .negative_capability import NegativeCapabilityGuard
from .proof import Ed25519Signer, verify_signed_object
from .projections import a11oy_read_only_projection, council_otel_projection
from .state_bus import IdempotencyReservation, StateBus

ACTION_RECEIPT_CONTENT_TYPE = "application/vnd.szl.action.receipt+json"


class CouncilKernel:
    def __init__(
        self,
        *,
        db_path: str,
        sandbox_root: str,
        receipt_signer: Ed25519Signer,
        gate: EmpiricalReleaseGate | None = None,
    ) -> None:
        self.bus = StateBus(db_path)
        self.executor = SandboxExecutor(sandbox_root)
        self.receipt_signer = receipt_signer
        self.gate = gate or EmpiricalReleaseGate()
        self.negative_guard = NegativeCapabilityGuard(self.bus)

    def _record_receipt(
        self,
        *,
        idempotency_key: str,
        governed_attempt_digest: str,
        case_id: str,
        action: ActionRequest,
        status: str,
        before_digest: str | None,
        after_digest: str | None,
        postconditions_passed: bool,
        rolled_back: bool,
        rollback_digest: str | None,
        council_result_digest: str,
        gate_result_digest: str,
        event_hash: str,
        issued_at: str,
    ) -> dict[str, Any]:
        prior = self.bus.previous_receipt_digest(case_id)
        receipt_id = "receipt-" + action.digest.split(":", 1)[1][:24]
        receipt = ActionReceipt(
            receipt_id=receipt_id,
            case_id=case_id,
            action_id=action.action_id,
            action_digest=action.digest,
            status=status,
            target=action.target,
            before_digest=before_digest,
            after_digest=after_digest,
            postconditions_passed=postconditions_passed,
            rolled_back=rolled_back,
            rollback_digest=rollback_digest,
            council_result_digest=council_result_digest,
            gate_result_digest=gate_result_digest,
            event_hash=event_hash,
            previous_receipt_digest=prior,
            issued_at=issued_at,
            signer_state=self.receipt_signer.signer_state,
        )
        signed = self.receipt_signer.sign_object(
            receipt.to_dict(), payload_type=ACTION_RECEIPT_CONTENT_TYPE
        )
        payload = verify_signed_object(
            signed,
            self.receipt_signer.verifier(),
            expected_payload_type=ACTION_RECEIPT_CONTENT_TYPE,
        )
        if payload != receipt.to_dict():
            raise IntegrityError("self-verification of action receipt failed")
        recorded = self.bus.settle_attempt_receipt(
            idempotency_key=idempotency_key,
            action_digest=governed_attempt_digest,
            receipt=receipt.to_dict(),
            case_id=case_id,
            action_id=action.action_id,
            signed_envelope=signed,
            created_at=issued_at,
        )
        if recorded["receipt_digest"] != receipt.digest:
            raise IntegrityError("State Bus receipt digest mismatch")
        return {
            "receipt": receipt.to_dict(),
            "receipt_digest": receipt.digest,
            "signed_receipt": signed,
            "receipt_verifier": self.receipt_signer.verifier().to_dict(),
            "transparency": recorded["transparency"],
        }

    def _replay(
        self,
        *,
        case: CouncilCase,
        reservation: IdempotencyReservation,
    ) -> dict[str, Any]:
        if not reservation.replay or reservation.receipt_digest is None:
            raise IdempotencyConflict(
                f"idempotency key is in non-replayable state: {reservation.state}"
            )
        replayed = self.bus.get_receipt(reservation.receipt_digest)
        value = {
            "schema": "szl.council-kernel-run/v1",
            "status": "REPLAYED",
            "original_status": replayed["receipt"]["status"],
            "case_id": case.case_id,
            **replayed,
            "ledger": self.bus.verify_chain(),
            "production_independence_verified": False,
            "assurance_scope": "LOCAL_KERNEL_AND_SANDBOX_EXECUTION_ONLY",
        }
        return {**value, "run_digest": digest_object(value)}

    def _settle_blocked(
        self,
        *,
        case: CouncilCase,
        action: ActionRequest,
        settlement: Mapping[str, Any],
        gate_result: GateResult,
        governed_attempt_digest: str,
        reason_codes: Sequence[str],
        event_suffix: str,
        event_payload: Mapping[str, Any],
        timestamp: str,
    ) -> dict[str, Any]:
        block_event = self.bus.append_event(
            event_id=f"{case.case_id}:action-blocked:{event_suffix}",
            case_id=case.case_id,
            event_type="ACTION_BLOCKED",
            payload={
                "reason_codes": list(reason_codes),
                **dict(event_payload),
            },
            created_at=timestamp,
        )
        self.bus.transition_case(
            case.case_id,
            WorkflowState.BLOCKED,
            reason_codes=tuple(reason_codes),
            created_at=timestamp,
        )
        receipt = self._record_receipt(
            idempotency_key=action.idempotency_key,
            governed_attempt_digest=governed_attempt_digest,
            case_id=case.case_id,
            action=action,
            status="BLOCKED",
            before_digest=None,
            after_digest=None,
            postconditions_passed=False,
            rolled_back=False,
            rollback_digest=None,
            council_result_digest=settlement["result_digest"],
            gate_result_digest=gate_result.digest,
            event_hash=block_event["event_hash"],
            issued_at=timestamp,
        )
        return self._result(
            case, settlement, gate_result.to_dict(), receipt, execution=None
        )

    def _settle_executor_failure(
        self,
        *,
        case: CouncilCase,
        action: ActionRequest,
        settlement: Mapping[str, Any],
        gate_result: GateResult,
        governed_attempt_digest: str,
        reason_code: str,
        exception_type: str,
        timestamp: str,
    ) -> dict[str, Any]:
        failure_event = self.bus.append_event(
            event_id=f"{case.case_id}:action:{action.action_id}:failed",
            case_id=case.case_id,
            event_type="ACTION_FAILED",
            payload={
                "reason_code": reason_code,
                "exception_type": exception_type,
                "raw_exception_message_included": False,
            },
            created_at=timestamp,
        )
        self.bus.transition_case(
            case.case_id,
            WorkflowState.FAILED,
            reason_codes=(reason_code,),
            created_at=timestamp,
        )
        receipt = self._record_receipt(
            idempotency_key=action.idempotency_key,
            governed_attempt_digest=governed_attempt_digest,
            case_id=case.case_id,
            action=action,
            status="FAILED",
            before_digest=None,
            after_digest=None,
            postconditions_passed=False,
            rolled_back=False,
            rollback_digest=None,
            council_result_digest=settlement["result_digest"],
            gate_result_digest=gate_result.digest,
            event_hash=failure_event["event_hash"],
            issued_at=timestamp,
        )
        return self._result(
            case, settlement, gate_result.to_dict(), receipt, execution=None
        )

    def run_case(
        self,
        *,
        case: CouncilCase,
        envelope: AutonomyEnvelope,
        grant: CapabilityGrant,
        settlement: Mapping[str, Any],
        gate_input: GateInput,
        action: ActionRequest,
        now: str | datetime | None = None,
    ) -> dict[str, Any]:
        timestamp = isoformat_utc(now or utc_now())
        if case.case_id != envelope.case_id or action.case_id != case.case_id:
            raise IntegrityError("case, envelope, and action identifiers must match")
        if case.envelope_digest != envelope.digest:
            raise IntegrityError("case is not bound to the supplied Autonomy Envelope")
        if case.epochs_digest != envelope.epochs.digest:
            raise IntegrityError("case is not bound to the supplied cognitive epochs")
        if case.risk_class != envelope.risk_class or gate_input.risk_class != case.risk_class:
            raise IntegrityError("case, envelope, and release-gate risk classes must match")
        settlement_verification = verify_settlement(settlement)
        if settlement_verification["status"] != "PASS":
            raise IntegrityError("Fourfold settlement transcript, signature, or binding failed")
        council_result = settlement["result"]
        if council_result["case_id"] != case.case_id or council_result["subject_digest"] != case.digest:
            raise IntegrityError("Fourfold result is not bound to this case")
        if council_result["policy_digest"] != case.policy_digest:
            raise IntegrityError("Fourfold result policy binding mismatch")
        if gate_input.council_state.value != council_result["state"]:
            raise IntegrityError("release gate input does not match Council terminal state")
        observed_diversity = float(council_result["diversity"]["joint_effective_size"])
        if abs(gate_input.effective_diversity - observed_diversity) > 1e-9:
            raise IntegrityError("release gate diversity must match the verified Council transcript")
        if action.postconditions != envelope.postconditions:
            raise IntegrityError("ActionRequest postconditions must exactly match the Autonomy Envelope")

        # The idempotency key binds the complete governed attempt, not merely a
        # tool payload. Any changed envelope, grant, council result, or release
        # gate input is a different attempt and cannot reuse an older receipt.
        attempt_digest = digest_object(
            {
                "schema": "szl.governed-attempt-binding/v1",
                "action_digest": action.digest,
                "envelope_digest": envelope.digest,
                "grant_digest": grant.digest,
                "council_result_digest": settlement["result_digest"],
                "gate_input": gate_input.to_dict(),
            }
        )
        existing = self.bus.lookup_idempotency(action.idempotency_key)
        if existing is not None:
            if existing.action_digest != attempt_digest:
                raise IdempotencyConflict(
                    "idempotency key is bound to a different governed attempt"
                )
            return self._replay(case=case, reservation=existing)

        started = self.bus.begin_attempt_and_case(
            case_id=case.case_id,
            case_value=case.to_dict(),
            envelope_value=envelope.to_dict(),
            idempotency_key=action.idempotency_key,
            action_digest=attempt_digest,
            created_at=timestamp,
        )
        reservation = started["reservation"]
        if reservation.state != "NEW":
            if reservation.action_digest != attempt_digest:
                raise IdempotencyConflict(
                    "idempotency key raced with a different governed attempt"
                )
            return self._replay(case=case, reservation=reservation)

        self.bus.transition_case(
            case.case_id,
            WorkflowState.DELIBERATING,
            reason_codes=("FOURFOLD_SETTLEMENT_RECEIVED",),
            evidence={"council_result_digest": settlement["result_digest"]},
            created_at=timestamp,
        )
        settlement_digest = self.bus.store_object(
            "council-settlement", settlement, created_at=timestamp
        )
        self.bus.append_event(
            event_id=f"{case.case_id}:council-settled",
            case_id=case.case_id,
            event_type="COUNCIL_SETTLED",
            payload={
                "settlement_digest": settlement_digest,
                "result_digest": settlement["result_digest"],
                "state": council_result["state"],
                "portable_transcript_verification": "PASS",
            },
            created_at=timestamp,
        )

        gate_result = self.gate.evaluate(gate_input, issued_at=timestamp)
        gate_result_digest = self.bus.store_object(
            "act-escalate-gate-result", gate_result.to_dict(), created_at=timestamp
        )
        self.bus.append_event(
            event_id=f"{case.case_id}:release-gated",
            case_id=case.case_id,
            event_type="RELEASE_GATED",
            payload={
                "gate_result_digest": gate_result_digest,
                "gate_input_digest": digest_object(gate_input.to_dict()),
                "decision": gate_result.decision.value,
            },
            created_at=timestamp,
        )
        self.bus.transition_case(
            case.case_id,
            WorkflowState.GATED,
            reason_codes=gate_result.reason_codes,
            evidence={"gate_result_digest": gate_result_digest},
            created_at=timestamp,
        )

        if council_result["state"] != envelope.required_council_state.value:
            return self._settle_blocked(
                case=case,
                action=action,
                settlement=settlement,
                gate_result=gate_result,
                governed_attempt_digest=attempt_digest,
                reason_codes=("REQUIRED_COUNCIL_STATE_NOT_MET",),
                event_suffix="council-state",
                event_payload={"observed": council_result["state"]},
                timestamp=timestamp,
            )

        if gate_result.decision != ReleaseDecision.ACT:
            return self._settle_blocked(
                case=case,
                action=action,
                settlement=settlement,
                gate_result=gate_result,
                governed_attempt_digest=attempt_digest,
                reason_codes=gate_result.reason_codes,
                event_suffix="release-gate",
                event_payload={"decision": gate_result.decision.value},
                timestamp=timestamp,
            )

        account = BudgetAccount(envelope.budgets)
        try:
            usage = account.consume(tool_calls=1, mutations=1)
            authorize_action(grant, envelope, action, usage, now=timestamp)
        except (AuthorizationError, ValidationError) as exc:
            return self._settle_blocked(
                case=case,
                action=action,
                settlement=settlement,
                gate_result=gate_result,
                governed_attempt_digest=attempt_digest,
                reason_codes=("CAPABILITY_OR_BUDGET_DENIED",),
                event_suffix="authorization",
                event_payload={
                    "denial_type": type(exc).__name__,
                    "raw_denial_message_included": False,
                },
                timestamp=timestamp,
            )

        task_class = str(action.metadata.get("task_class", "file_mutation"))
        domain = action.metadata.get("domain")
        negative = self.negative_guard.evaluate(
            task_class=task_class,
            tool=action.tool,
            domain=str(domain) if domain else None,
            now=timestamp,
        )
        if not negative.allowed:
            return self._settle_blocked(
                case=case,
                action=action,
                settlement=settlement,
                gate_result=gate_result,
                governed_attempt_digest=attempt_digest,
                reason_codes=("NEGATIVE_CAPABILITY_ACTIVE",),
                event_suffix="negative-capability",
                event_payload={
                    "task_class": task_class,
                    "tool": action.tool,
                    "domain": str(domain) if domain else None,
                    "condition_codes": sorted(
                        {str(item["condition_code"]) for item in negative.blockers}
                    ),
                },
                timestamp=timestamp,
            )

        try:
            preconditions = self.executor.check_conditions(envelope.preconditions)
        except (ValidationError, IntegrityError) as exc:
            return self._settle_blocked(
                case=case,
                action=action,
                settlement=settlement,
                gate_result=gate_result,
                governed_attempt_digest=attempt_digest,
                reason_codes=("PRECONDITION_EVALUATION_REJECTED",),
                event_suffix="precondition-evaluation",
                event_payload={
                    "rejection_type": type(exc).__name__,
                    "raw_rejection_message_included": False,
                },
                timestamp=timestamp,
            )
        if not all(item.passed for item in preconditions):
            return self._settle_blocked(
                case=case,
                action=action,
                settlement=settlement,
                gate_result=gate_result,
                governed_attempt_digest=attempt_digest,
                reason_codes=("PRECONDITION_FAILED",),
                event_suffix="preconditions",
                event_payload={"results": [item.to_dict() for item in preconditions]},
                timestamp=timestamp,
            )

        self.bus.transition_case(
            case.case_id,
            WorkflowState.EXECUTING,
            reason_codes=("CAPABILITY_AND_BUDGET_AUTHORIZED",),
            evidence={"grant_digest": grant.digest, "budget": account.snapshot()},
            created_at=timestamp,
        )
        try:
            execution = self.executor.execute(action)
        except (ValidationError, IntegrityError) as exc:
            return self._settle_executor_failure(
                case=case,
                action=action,
                settlement=settlement,
                gate_result=gate_result,
                governed_attempt_digest=attempt_digest,
                reason_code="EXECUTOR_REJECTED",
                exception_type=type(exc).__name__,
                timestamp=timestamp,
            )
        except Exception as exc:  # fail closed with a signed terminal record
            return self._settle_executor_failure(
                case=case,
                action=action,
                settlement=settlement,
                gate_result=gate_result,
                governed_attempt_digest=attempt_digest,
                reason_code="EXECUTOR_INTERNAL_FAILURE",
                exception_type=type(exc).__name__,
                timestamp=timestamp,
            )

        execution_event = self.bus.append_event(
            event_id=f"{case.case_id}:action:{action.action_id}:executed",
            case_id=case.case_id,
            event_type="ACTION_EXECUTED",
            payload=execution.to_dict(),
            created_at=timestamp,
        )
        if execution.postconditions_passed:
            self.bus.transition_case(
                case.case_id,
                WorkflowState.VERIFYING,
                reason_codes=("MUTATION_APPLIED",),
                evidence={"execution_event_hash": execution_event["event_hash"]},
                created_at=timestamp,
            )
            self.bus.transition_case(
                case.case_id,
                WorkflowState.SETTLED,
                reason_codes=("POSTCONDITIONS_VERIFIED",),
                evidence={"after_digest": execution.after_digest},
                created_at=timestamp,
            )
            status = "VERIFIED"
        elif execution.rolled_back:
            self.bus.transition_case(
                case.case_id,
                WorkflowState.ROLLED_BACK,
                reason_codes=("POSTCONDITION_FAILED_COMPENSATED",),
                evidence={"rollback_digest": execution.rollback_digest},
                created_at=timestamp,
            )
            status = "ROLLED_BACK"
        else:
            self.bus.transition_case(
                case.case_id,
                WorkflowState.FAILED,
                reason_codes=("POSTCONDITION_FAILED_ROLLBACK_UNVERIFIED",),
                created_at=timestamp,
            )
            status = "FAILED"

        receipt = self._record_receipt(
            idempotency_key=action.idempotency_key,
            governed_attempt_digest=attempt_digest,
            case_id=case.case_id,
            action=action,
            status=status,
            before_digest=execution.before_digest,
            after_digest=execution.after_digest,
            postconditions_passed=execution.postconditions_passed,
            rolled_back=execution.rolled_back,
            rollback_digest=execution.rollback_digest,
            council_result_digest=settlement["result_digest"],
            gate_result_digest=gate_result.digest,
            event_hash=execution_event["event_hash"],
            issued_at=timestamp,
        )
        return self._result(
            case,
            settlement,
            gate_result.to_dict(),
            receipt,
            execution=execution.to_dict(),
        )

    def _result(
        self,
        case: CouncilCase,
        settlement: Mapping[str, Any],
        gate_result: Mapping[str, Any],
        receipt: Mapping[str, Any],
        *,
        execution: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        ledger = self.bus.verify_chain()
        value = {
            "schema": "szl.council-kernel-run/v1",
            "status": receipt["receipt"]["status"],
            "case_id": case.case_id,
            "council": settlement,
            "gate": dict(gate_result),
            "execution": dict(execution) if execution is not None else None,
            **dict(receipt),
            "ledger": ledger,
            "otel": council_otel_projection(
                settlement, gate_result=gate_result, receipt=receipt["receipt"]
            ),
            "a11oy": a11oy_read_only_projection(
                settlement, gate_result=gate_result, receipt=receipt["receipt"]
            ),
            "production_independence_verified": False,
            "assurance_scope": "LOCAL_KERNEL_AND_SANDBOX_EXECUTION_ONLY",
        }
        return {**value, "run_digest": digest_object(value)}
