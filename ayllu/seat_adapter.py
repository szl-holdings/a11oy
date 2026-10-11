#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Original, proposal-only seat interface for Ayllu.

This module makes local, validated values only: importing it cannot contact a
provider, join a room, synthesize audio, schedule work, or dispatch a tool.
A model-originated effect request always receives a DENY decision here. Tenant,
actor, and seat labels are syntactic metadata, not authenticated authority.
Source mappings belong in separately controlled evidence, not in this module.
"""

from dataclasses import dataclass, field
import re
from types import MappingProxyType


SCHEMA = "szl.ayllu.seat-proposal/v1"

# Declaring a timeout or request ID below does not activate any of these organs.
CAPABILITIES = MappingProxyType({
    "chat_transport": False,
    "room_transport": False,
    "tts_synthesis": False,
    "provider_binding": False,
    "memory_read": False,
    "memory_write": False,
    "tool_dispatch": False,
    "scheduling": False,
    "runtime_cancellation": False,
})

_ID = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}\Z")


def _identifier(value: str, name: str) -> None:
    if type(value) is not str or _ID.fullmatch(value) is None:
        raise ValueError(f"{name} must be a lowercase identifier of at most 64 characters")


def _text(value: str, name: str, maximum: int) -> None:
    if (type(value) is not str or not value.strip() or len(value) > maximum
            or any(ord(ch) < 32 and ch not in "\n\r\t" for ch in value)):
        raise ValueError(f"{name} must be nonempty text of at most {maximum} characters")


@dataclass(frozen=True, slots=True)
class SeatIdentity:
    """Untrusted tenant and seat labels; no identity claim is verified here."""

    tenant_id: str
    seat_id: str

    def __post_init__(self) -> None:
        _identifier(self.tenant_id, "tenant_id")
        _identifier(self.seat_id, "seat_id")


@dataclass(frozen=True, slots=True)
class RequestContext:
    """Correlation metadata; timeout_s does not start or cancel a runtime turn."""

    seat: SeatIdentity
    actor_id: str
    request_id: str
    timeout_s: int = 30

    def __post_init__(self) -> None:
        if not isinstance(self.seat, SeatIdentity):
            raise ValueError("seat must be a SeatIdentity")
        _identifier(self.actor_id, "actor_id")
        _identifier(self.request_id, "request_id")
        if type(self.timeout_s) is not int or not 1 <= self.timeout_s <= 120:
            raise ValueError("timeout_s must be an integer from 1 to 120")


@dataclass(frozen=True, slots=True)
class ChatProposal:
    context: RequestContext
    conversation_id: str
    input_text: str
    state: str = field(default="PROPOSAL_ONLY", init=False)

    def __post_init__(self) -> None:
        _context(self.context)
        _identifier(self.conversation_id, "conversation_id")
        _text(self.input_text, "input_text", 8192)


@dataclass(frozen=True, slots=True)
class RoomProposal:
    context: RequestContext
    room_id: str
    participants: tuple[SeatIdentity, ...]
    topic: str
    state: str = field(default="PROPOSAL_ONLY", init=False)

    def __post_init__(self) -> None:
        _context(self.context)
        _identifier(self.room_id, "room_id")
        _text(self.topic, "topic", 1024)
        if type(self.participants) is not tuple or not 2 <= len(self.participants) <= 8:
            raise ValueError("participants must be a tuple of 2 to 8 seats")
        if any(not isinstance(seat, SeatIdentity) for seat in self.participants):
            raise ValueError("each participant must be a SeatIdentity")
        if any(seat.tenant_id != self.context.seat.tenant_id
               for seat in self.participants):
            raise ValueError("room participants must share one tenant")
        ids = [seat.seat_id for seat in self.participants]
        if len(ids) != len(set(ids)) or self.context.seat.seat_id not in ids:
            raise ValueError("participants must be unique and include the requesting seat")


@dataclass(frozen=True, slots=True)
class TTSProposal:
    context: RequestContext
    text: str
    voice_id: str | None = None
    state: str = field(default="PROPOSAL_ONLY", init=False)

    def __post_init__(self) -> None:
        _context(self.context)
        _text(self.text, "text", 2048)
        if self.voice_id is not None:
            _identifier(self.voice_id, "voice_id")


@dataclass(frozen=True, slots=True)
class EffectProposal:
    """An inert description; no arguments, credentials, or executor are accepted."""

    context: RequestContext
    tool_id: str
    summary: str
    state: str = field(default="PROPOSAL_ONLY", init=False)

    def __post_init__(self) -> None:
        _context(self.context)
        _identifier(self.tool_id, "tool_id")
        _text(self.summary, "summary", 1024)


@dataclass(frozen=True, slots=True)
class EffectDecision:
    proposal: EffectProposal
    verdict: str = field(default="DENY", init=False)
    reason: str = field(default="NO_INDEPENDENT_GOVERNANCE_AUTHORITY", init=False)
    can_execute: bool = field(default=False, init=False)


def handoff_effect(proposal: EffectProposal) -> EffectDecision:
    """Return a denial for independent review; never grant or perform an effect."""
    if not isinstance(proposal, EffectProposal):
        raise ValueError("proposal must be an EffectProposal")
    return EffectDecision(proposal)


def _context(value: RequestContext) -> None:
    if not isinstance(value, RequestContext):
        raise ValueError("context must be a RequestContext")


__all__ = [
    "SCHEMA", "CAPABILITIES",
    "SeatIdentity", "RequestContext", "ChatProposal", "RoomProposal",
    "TTSProposal", "EffectProposal", "EffectDecision", "handoff_effect",
]
