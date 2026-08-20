# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Secret-safe OpenTelemetry GenAI attribute and sampling contract.

Message content is never accepted into model span attributes. Callers may retain
structured, redacted governance events through their configured exporter.
"""
from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from typing import Any

CONTENT_CAPTURE_ENABLED = False
SEMCONV_SCHEMA_URL = "https://opentelemetry.io/schemas/1.42.0"
_SENSITIVE_KEY = re.compile(
    r"(authorization|api[-_]?key|secret|password|passwd|token|cookie|private[-_]?key|"
    r"prompt|completion|system[-_]?prompt|tool[-_]?arguments?|tool[-_]?results?|document)",
    re.IGNORECASE,
)
_MANDATORY_EVENTS = frozenset(
    {
        "policy.rejected",
        "authorization_receipt.invalid",
        "deployment.production",
        "provenance.verification_failed",
        "admission.rejected",
        "security.alert",
        "benchmark.run",
        "incident.trace",
    }
)


def redact(value: Any, *, key: str = "") -> Any:
    """Recursively remove secret-bearing values before telemetry export."""
    if _SENSITIVE_KEY.search(key):
        raw = repr(value).encode("utf-8", errors="replace")
        return f"[REDACTED sha256:{hashlib.sha256(raw).hexdigest()[:16]}]"
    if isinstance(value, Mapping):
        return {str(k): redact(v, key=str(k)) for k, v in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [redact(item, key=key) for item in value]
    if isinstance(value, str):
        # Catch common inline credentials even when a producer mislabeled the key.
        scrubbed = re.sub(
            r"(?i)\b(bearer|token|api[_-]?key|password)\s*[:=]\s*[^\s,;]+",
            r"\1=[REDACTED]",
            value,
        )
        return scrubbed[:1024]
    return value


def model_attributes(
    *,
    operation: str,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    max_tokens: int | None = None,
    temperature: float | None = None,
    output_type: str | None = None,
    correlation: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return only semconv-safe model-call attributes; no message content."""
    if operation not in {
        "chat",
        "text_completion",
        "embeddings",
        "execute_tool",
        "invoke_agent",
        "create_agent",
        "generate_content",
    }:
        raise ValueError("unsupported gen_ai operation")
    if input_tokens < 0 or output_tokens < 0:
        raise ValueError("token counts cannot be negative")
    attrs: dict[str, Any] = {
        "gen_ai.operation.name": operation,
        "gen_ai.provider.name": provider,
        "gen_ai.request.model": model,
        "gen_ai.usage.input_tokens": input_tokens,
        "gen_ai.usage.output_tokens": output_tokens,
    }
    optional = {
        "gen_ai.request.max_tokens": max_tokens,
        "gen_ai.request.temperature": temperature,
        "gen_ai.output.type": output_type,
    }
    attrs.update({key: value for key, value in optional.items() if value is not None})
    for key, value in (correlation or {}).items():
        if key.startswith(("run.", "agent.", "action.", "policy.", "formal.", "artifact.", "attestation.", "model.", "serving.", "benchmark.", "deployment.")):
            attrs[key] = redact(value, key=key)
    return attrs


def sampling_decision(event_name: str, *, initial_production_validation: bool = False) -> str:
    """Preserve mandatory events; ordinary success may use tail sampling later."""
    if initial_production_validation or event_name in _MANDATORY_EVENTS:
        return "RECORD_AND_SAMPLE"
    return "TAIL_POLICY_ELIGIBLE"


def security_event(event_name: str, fields: Mapping[str, Any]) -> dict[str, Any]:
    """Build a structured redacted event that cannot carry authorization."""
    return {
        "event.name": event_name,
        "sampling.decision": sampling_decision(event_name),
        "authorization.effect": "NONE",
        "fields": redact(fields),
    }
