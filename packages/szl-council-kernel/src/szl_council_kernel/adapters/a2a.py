from __future__ import annotations

from typing import Any, Mapping

from ..canonical import digest_object, require_digest, require_identifier
from ..errors import AuthorizationError, ValidationError


class A2AGovernor:
    """Validate agent-to-agent task bindings without trusting remote claims."""

    def validate_task(
        self,
        task: Mapping[str, Any],
        *,
        expected_case_id: str,
        expected_policy_digest: str,
    ) -> dict[str, Any]:
        allowed = {
            "task_id",
            "case_id",
            "policy_digest",
            "evidence_manifest_digest",
            "authority_claimed",
            "sender",
            "payload_digest",
        }
        if set(task) - allowed:
            raise ValidationError("A2A task contains unsupported authority-bearing fields")
        task_id = require_identifier(str(task.get("task_id", "")), field="task_id")
        if task.get("case_id") != expected_case_id:
            raise AuthorizationError("A2A task case binding mismatch")
        if task.get("policy_digest") != expected_policy_digest:
            raise AuthorizationError("A2A task policy binding mismatch")
        require_digest(
            str(task.get("evidence_manifest_digest", "")),
            field="evidence_manifest_digest",
        )
        if task.get("payload_digest") is not None:
            require_digest(str(task["payload_digest"]), field="payload_digest")
        if task.get("authority_claimed") is not False:
            raise AuthorizationError(
                "remote A2A peer must explicitly disclaim kernel authority"
            )
        sender = task.get("sender")
        if sender is not None:
            require_identifier(str(sender), field="sender")
        return {
            "schema": "szl.a2a-governor-decision/v2",
            "allow": True,
            "task_id": task_id,
            "task_digest": digest_object(task),
            "authority_claimed": False,
        }
