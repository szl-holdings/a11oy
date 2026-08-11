from __future__ import annotations

from typing import Any, Mapping

from ..canonical import digest_object
from ..capability import authorize_action
from ..errors import AuthorizationError, ValidationError
from ..models import ActionRequest, AutonomyEnvelope, BudgetUsage, CapabilityGrant


class MCPGovernor:
    """Treat MCP tool messages as untrusted proposals, never as authority.

    The reference binding requires the MCP ``arguments`` object to equal the
    complete canonical ``ActionRequest``. A tool name alone is not enough:
    target, content, preimage, postconditions, grant, and idempotency context
    must all be digest-bound before capability evaluation.
    """

    ALLOWED_METHODS = {"tools/call"}

    def validate_tool_call(
        self,
        message: Mapping[str, Any],
        *,
        action: ActionRequest,
        grant: CapabilityGrant,
        envelope: AutonomyEnvelope,
        usage: BudgetUsage,
        now: str,
    ) -> dict[str, Any]:
        if set(message) - {"jsonrpc", "id", "method", "params"}:
            raise ValidationError("MCP message contains unsupported top-level fields")
        if message.get("jsonrpc") != "2.0" or message.get("method") not in self.ALLOWED_METHODS:
            raise ValidationError("unsupported MCP message")
        request_id = message.get("id")
        if request_id is None or isinstance(request_id, bool) or not isinstance(request_id, (str, int)):
            raise ValidationError("MCP mutating tool call requires a bounded request id")
        if isinstance(request_id, str) and (not request_id or len(request_id) > 256):
            raise ValidationError("MCP request id must be bounded")
        params = message.get("params")
        if not isinstance(params, Mapping) or set(params) != {"name", "arguments"}:
            raise AuthorizationError("MCP params must contain exactly name and arguments")
        if params.get("name") != action.tool:
            raise AuthorizationError("MCP tool name is not bound to ActionRequest")
        arguments = params.get("arguments")
        if not isinstance(arguments, Mapping) or dict(arguments) != action.to_dict():
            raise AuthorizationError("MCP tool arguments are not exactly bound to ActionRequest")
        authorize_action(grant, envelope, action, usage, now=now)
        return {
            "schema": "szl.mcp-governor-decision/v2",
            "allow": True,
            "request_id": request_id,
            "message_digest": digest_object(message),
            "action_digest": action.digest,
            "authority_source": "AUTONOMY_ENVELOPE_AND_CAPABILITY_GRANT",
        }
