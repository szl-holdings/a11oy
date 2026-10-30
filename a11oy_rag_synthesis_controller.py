#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Controller capability factory for admitted RAG answer synthesis (R6).

This module wires the existing ``AuthorizedRagSynthesis`` adapter to the three
Code agent call sites. It does not create identity, rights or provider
authority. Those decisions come from an injected ``SynthesisGrantSource``,
which is owned by the rights-registry work (R2/R3). With no grant source and no
fixed destination installed (the default), ``build_answer_synthesizer`` returns
``None`` and every call site keeps its existing ``CONTENT_ADMISSION_UNAVAILABLE``
behaviour and response shape.

Grant source protocol (the only interface this module consumes)
---------------------------------------------------------------
``resolve_subject(request, operator) -> SynthesisSubject | None``
    Map the verified caller of this request to an authenticated named
    principal, explicit tenant and immutable policy revision. ``operator`` is the
    ``szl_operator_auth.principal`` dict; it is necessary, never sufficient.
    Request bodies, planner output and document metadata are not identity.
``source_grant(subject, handle) -> SynthesisSourceGrant``
    Current source-access verdict for that exact subject and full handle. It is
    called on every check (initial, hydration, pre-egress); never cache it.
``admit_transfer(decision: TransferDecision) -> bool``
    Strict ``True`` admits moving exactly these source revisions to exactly
    this destination for exactly this purpose and task digest. Any other value,
    including truthy non-bool values, is a refusal.

Fixed destination
-----------------
``FixedDestination`` names one provider, one model and one trust domain plus a
transport that reaches only that destination. The transport is called at most
once per capability, with ``allow_fallback=False``. Its response must echo the
same provider and model and must not report a fallback. Generic routing helpers
that walk provider/model fallbacks (``agent_model_complete`` and its resilient
caller) are refused as transports by the orchestrator.

No environment variable, request field or model output can install either
object. ``configure`` is a process-composition call for the controller.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Iterable, Mapping, Optional, Protocol, runtime_checkable

import a11oy_agent_loop as _agent

PURPOSE = "ANSWER_SYNTHESIS"
_FALLBACK_KEYS = ("fallback_used", "fallbacks_attempted", "fallback_model", "fallback_provider")


@dataclass(frozen=True)
class FixedDestination:
    """One admitted destination; the transport must not route elsewhere."""
    provider_id: str
    model_id: str
    trust_domain: str
    transport: Callable[..., Awaitable[dict]] = field(repr=False, compare=False)


@dataclass(frozen=True)
class TransferDecision:
    """Exact binding for one source-to-destination admission decision."""
    subject: Any
    source_revisions: tuple  # ((generation_id, chunk_id, source_sha256, source_revision), ...)
    provider_id: str
    model_id: str
    trust_domain: str
    purpose: str
    task_sha256: str
    history_forwarded: bool
    expression_authority: str


@runtime_checkable
class SynthesisGrantSource(Protocol):
    def resolve_subject(self, request: Any, operator: Mapping[str, Any]) -> Optional[Any]: ...

    def source_grant(self, subject: Any, handle: Any) -> Any: ...

    def admit_transfer(self, decision: TransferDecision) -> bool: ...


_STATE: dict[str, Any] = {"grant_source": None, "destination": None}


def configure(*, grant_source: Optional[SynthesisGrantSource] = None,
              destination: Optional[FixedDestination] = None) -> None:
    """Install (or clear, with no arguments) the controller capabilities."""
    _STATE["grant_source"] = grant_source
    _STATE["destination"] = destination


def configured() -> tuple[Optional[SynthesisGrantSource], Optional[FixedDestination]]:
    return _STATE["grant_source"], _STATE["destination"]


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise _agent.SynthesisAdmissionError(reason)


def _fixed_backend(destination: FixedDestination) -> Any:
    """Wrap the one transport; one egress, no retry, exact response identity."""
    calls = {"n": 0}

    async def complete(messages: list, **kw: Any) -> dict:
        _require(calls["n"] == 0, "SYNTHESIS_BACKEND_UNAVAILABLE")
        calls["n"] += 1
        result = await destination.transport(
            messages, provider_id=destination.provider_id, model_id=destination.model_id,
            trust_domain=destination.trust_domain, allow_fallback=False,
            max_tokens=kw.get("max_tokens", 1200), temperature=kw.get("temperature", 0.0))
        if not (isinstance(result, dict)
                and result.get("provider_id") == destination.provider_id
                and result.get("model") == destination.model_id
                and all(result.get(key) in (None, False) for key in _FALLBACK_KEYS)):
            # A different provider/model or any reported fallback is a refused
            # response, never a relabelled success. No response field is relayed.
            return {"ok": False, "error": "SYNTHESIS_RESPONSE_UNAVAILABLE",
                    "text": None, "model": None, "stub": True}
        # Project only the fields the adapter validates; nothing else is relayed.
        projected = {"text": result.get("text"), "model": result.get("model"),
                     "stub": result.get("stub")}
        if "ok" in result:
            projected["ok"] = result["ok"]
        if result.get("error"):
            projected["error"] = "SYNTHESIS_BACKEND_FAILED"
        return projected

    return _agent.SynthesisBackend(destination.provider_id, destination.model_id,
                                   destination.trust_domain, complete)


def build_answer_synthesizer(request: Any, operator: Mapping[str, Any], *,
                             hydrate: Optional[Callable] = None,
                             forbidden_transports: Iterable[Any] = ()) -> Optional[Callable[..., Awaitable[dict]]]:
    """Return a single-use admitted synthesizer for this request, or ``None``.

    ``None`` means content admission is unavailable; the agent then halts with
    ``CONTENT_ADMISSION_UNAVAILABLE`` exactly as it does without this module.
    """
    grant_source, destination = configured()
    if grant_source is None or destination is None or hydrate is None or not callable(hydrate):
        return None
    if not isinstance(grant_source, SynthesisGrantSource) or type(destination) is not FixedDestination:
        return None
    if not callable(destination.transport):
        return None
    if any(destination.transport is forbidden for forbidden in forbidden_transports):
        return None
    if not isinstance(operator, Mapping) or operator.get("operator") is not True:
        return None
    try:
        subject = grant_source.resolve_subject(request, operator)
    except Exception:
        return None
    if type(subject) is not _agent.SynthesisSubject:
        return None

    def authorize(s: Any, handle: Any) -> Any:
        return grant_source.source_grant(s, handle)

    def strict_source_allowed(s: Any, handle: Any) -> bool:
        grant = grant_source.source_grant(s, handle)
        return (type(grant) is _agent.SynthesisSourceGrant and grant.allowed is True
                and grant.subject == s and grant.handle == handle)

    def hydrator(s: Any, handles: tuple) -> list:
        return hydrate(s, handles, authorizer=strict_source_allowed)

    def provider_admitter(s: Any, grants: tuple, binding: dict) -> bool:
        decision = TransferDecision(
            subject=s,
            source_revisions=tuple((g.handle.generation_id, g.handle.chunk_id, g.handle.sha256,
                                    g.source_revision) for g in grants),
            provider_id=binding.get("provider_id"), model_id=binding.get("model_id"),
            trust_domain=binding.get("trust_domain"), purpose=binding.get("purpose"),
            task_sha256=binding.get("task_sha256"),
            history_forwarded=binding.get("history_forwarded"),
            expression_authority=binding.get("expression_authority"))
        if (decision.purpose != PURPOSE or decision.provider_id != destination.provider_id
                or decision.model_id != destination.model_id
                or decision.trust_domain != destination.trust_domain
                or decision.history_forwarded is not False
                or decision.expression_authority != "NONE"):
            return False
        allowed = grant_source.admit_transfer(decision)
        return allowed is True

    adapter = _agent.AuthorizedRagSynthesis(
        subject=subject, authorizer=authorize, hydrator=hydrator,
        backend=_fixed_backend(destination), provider_admitter=provider_admitter)
    used = {"n": 0}

    async def answer_synthesizer(*, task: str, retrievals: tuple, **_kw: Any) -> dict:
        # One capability per request and task; a second invocation is refused.
        _require(used["n"] == 0, "SYNTHESIS_BACKEND_UNAVAILABLE")
        used["n"] += 1
        return await adapter(task=task, retrievals=retrievals)

    return answer_synthesizer


def task_sha256(task: str) -> str:
    return hashlib.sha256(task.encode("utf-8")).hexdigest()
