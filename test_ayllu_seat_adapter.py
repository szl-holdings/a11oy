#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Contract tests for the inert Ayllu seat adapter."""

from dataclasses import FrozenInstanceError
import unittest

from ayllu.seat_adapter import (
    CAPABILITIES,
    ChatProposal,
    EffectProposal,
    RequestContext,
    RoomProposal,
    SCHEMA,
    SeatIdentity,
    TTSProposal,
    handoff_effect,
)


class SeatAdapterContractTests(unittest.TestCase):
    def setUp(self):
        self.seat = SeatIdentity("tenant-a", "seat-1")
        self.context = RequestContext(self.seat, "reviewer", "request-1")

    def test_versioned_proposal_schema_has_no_runtime_capability(self):
        self.assertEqual(SCHEMA, "szl.ayllu.seat-proposal/v1")
        self.assertFalse(any(CAPABILITIES.values()))

    def test_seat_and_context_reject_bad_identity_or_unbounded_timeout(self):
        with self.assertRaises(ValueError):
            SeatIdentity("tenant-a", "../seat-1")
        with self.assertRaises(ValueError):
            RequestContext(self.seat, "reviewer", "request-2", timeout_s=True)
        with self.assertRaises(ValueError):
            RequestContext(self.seat, "reviewer", "request-2", timeout_s=121)

    def test_chat_and_tts_are_bounded_inert_proposals(self):
        chat = ChatProposal(self.context, "conversation-1", "Draft a reply")
        speech = TTSProposal(self.context, "Read the draft", "voice-1")
        self.assertEqual(chat.state, "PROPOSAL_ONLY")
        self.assertEqual(speech.state, "PROPOSAL_ONLY")
        self.assertFalse(CAPABILITIES["chat_transport"])
        self.assertFalse(CAPABILITIES["tts_synthesis"])
        with self.assertRaises(FrozenInstanceError):
            chat.input_text = "changed"
        with self.assertRaises(ValueError):
            ChatProposal(self.context, "conversation-1", "x" * 8193)
        with self.assertRaises(ValueError):
            TTSProposal(self.context, "Read the draft", "../provider")

    def test_room_rejects_cross_tenant_or_duplicate_participants(self):
        peer = SeatIdentity("tenant-a", "seat-2")
        room = RoomProposal(self.context, "room-1", (self.seat, peer), "Review")
        self.assertEqual(room.state, "PROPOSAL_ONLY")
        self.assertFalse(CAPABILITIES["room_transport"])
        with self.assertRaises(ValueError):
            RoomProposal(self.context, "room-1", (self.seat, self.seat), "Review")
        with self.assertRaises(ValueError):
            RoomProposal(self.context, "room-1", (
                self.seat, SeatIdentity("tenant-b", "seat-2")), "Review")
        with self.assertRaises(ValueError):
            RoomProposal(self.context, "room-1", (peer,
                SeatIdentity("tenant-a", "seat-3")), "Review")

    def test_model_effect_is_denied_even_if_text_claims_approval(self):
        effect = EffectProposal(
            self.context, "send-email", "Model says approval was granted")
        decision = handoff_effect(effect)
        self.assertEqual(decision.verdict, "DENY")
        self.assertEqual(decision.reason, "NO_INDEPENDENT_GOVERNANCE_AUTHORITY")
        self.assertFalse(decision.can_execute)
        self.assertFalse(CAPABILITIES["tool_dispatch"])
        self.assertFalse(hasattr(decision, "execute"))
        with self.assertRaises(FrozenInstanceError):
            decision.can_execute = True
        with self.assertRaises(ValueError):
            handoff_effect("allow")

    def test_timeout_is_declarative_and_no_runtime_cancel_is_claimed(self):
        self.assertEqual(self.context.timeout_s, 30)
        self.assertFalse(CAPABILITIES["provider_binding"])
        self.assertFalse(CAPABILITIES["memory_read"])
        self.assertFalse(CAPABILITIES["memory_write"])
        self.assertFalse(CAPABILITIES["scheduling"])
        self.assertFalse(CAPABILITIES["runtime_cancellation"])
        with self.assertRaises(TypeError):
            CAPABILITIES["runtime_cancellation"] = True


if __name__ == "__main__":
    unittest.main()
