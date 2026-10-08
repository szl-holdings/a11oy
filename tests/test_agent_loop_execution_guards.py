#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Offline FSM regressions with explicitly SIMULATED callback boundaries.

The production plan sorter, budget accounting and gate decisions run locally.
Retrieval, tools, inference and receipt delivery are synthetic unit-test inputs;
these cases establish no deployment, signed receipt or integration readiness.
"""
import asyncio
import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import a11oy_agent_loop as agent


def _grounding(count=6):
    return {"ok": True, "chunks": [
        {"path": f"SIMULATED/source-{index}.txt",
         "sha256": hashlib.sha256(f"SIMULATED-{index}".encode()).hexdigest()}
        for index in range(count)
    ]}


class _Callbacks:
    def __init__(self, *, grounding=None, tool_ok=True, allow=True):
        self.grounding = grounding if grounding is not None else _grounding()
        self.tool_ok = tool_ok
        self.allow = allow
        self.calls = []
        self.receipts = []

    def retrieve(self, query):
        self.calls.append("retrieve")
        return self.grounding

    def gate(self, action, context):
        return {"allow": self.allow, "lambda": 0.97,
                "reason": "SIMULATED unit-test tool verdict"}

    async def tool(self, name, args, **kwargs):
        self.calls.append(name)
        return {"ok": self.tool_ok, "result": {
            "ok": self.tool_ok, "exit": 0 if self.tool_ok else 1,
            "stdout": "SIMULATED tool output"}}

    async def complete(self, messages, **kwargs):
        self.calls.append("model")
        return {"text": "SIMULATED answer", "model": "unit-test", "stub": True}

    async def synthesize(self, **kwargs):
        # This suite isolates FSM gates. Source/provider admission is explicitly
        # simulated here; test_authorized_rag_synthesis exercises the real adapter.
        return {**await self.complete([]), "stub": False, "_expression_authorized": False,
                "synthesis_admission": {"state": "AUTHORIZED_CONTENT_SUPPLIED", "source_count": 6,
                    "context_sha256": hashlib.sha256(b"SIMULATED unit boundary").hexdigest(),
                    "semantic_support_verified": False, "provider_id": "SIMULATED",
                    "model_id": "unit-test", "trust_domain": "LOCAL"}}

    def receipt(self, action, payload):
        self.receipts.append({"action": action, "payload": payload})
        digest = hashlib.sha256(json.dumps(self.receipts[-1], sort_keys=True).encode()).hexdigest()
        return {"hash": digest, "signed": False, "chain_verified": False,
                "evidence_class": "SIMULATED"}

    def loop(self, **kwargs):
        return agent.AgentLoop(
            khipu_emit=self.receipt, puriq_decide=self.gate,
            execute_tool=self.tool, model_complete=self.complete,
            rag_query=self.retrieve, answer_synthesizer=self.synthesize, **kwargs)


class PlanDependencyTests(unittest.TestCase):
    def test_unknown_dependency_is_rejected(self):
        plan = [agent.PlanNode("consumer", "consume", deps=["missing-producer"])]
        with self.assertRaisesRegex(ValueError, "unknown dependency"):
            agent._topo_order(plan)

    def test_duplicate_node_identity_is_rejected(self):
        plan = [agent.PlanNode("same", "first"), agent.PlanNode("same", "second")]
        with self.assertRaisesRegex(ValueError, "duplicate node"):
            agent._topo_order(plan)

    def test_cycle_is_rejected_and_diamond_orders_producers_first(self):
        with self.assertRaisesRegex(ValueError, "cycle"):
            agent._topo_order([agent.PlanNode("a", "a", deps=["b"]),
                               agent.PlanNode("b", "b", deps=["a"])])
        plan = [agent.PlanNode("end", "end", deps=["left", "right"]),
                agent.PlanNode("right", "right", deps=["start"]),
                agent.PlanNode("start", "start"),
                agent.PlanNode("left", "left", deps=["start"])]
        self.assertEqual(agent._topo_order(plan), ["start", "left", "right", "end"])


class ExecutionGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="agent-guards-")
        self.addCleanup(self.temp.cleanup)
        for context in (
            patch.object(agent, "REFLECT_DB", str(Path(self.temp.name) / "reflect.sqlite3")),
            patch.object(agent, "_active_flux_tier_hint", return_value=None),
            patch.object(agent, "_span", side_effect=lambda name: agent._SpanShim(name)),
            patch.dict(os.environ, {"A11OY_WALLPA_FINALIZE": "0"}),
        ):
            context.start()
            self.addCleanup(context.stop)

    def test_all_transitions_including_halt_fit_budget(self):
        for maximum in range(1, 15):
            with self.subTest(maximum=maximum):
                calls = _Callbacks()
                result = asyncio.run(calls.loop(max_steps=maximum).run("read repo and verify"))
                self.assertLessEqual(result["step_count"], maximum)
                self.assertEqual(result["step_count"], len(result["steps"]))
                self.assertEqual([row["step"] for row in result["steps"]],
                                 list(range(1, result["step_count"] + 1)))

    def test_tool_does_not_start_without_observation_and_verification_budget(self):
        calls = _Callbacks()
        result = asyncio.run(calls.loop(max_steps=5).run("read repo"))
        self.assertFalse(result["ok"])
        self.assertEqual(calls.calls, ["retrieve"])
        self.assertEqual(result["final_state"], agent.S_HALT)

    def test_retrieval_denial_prevents_tools_and_synthesis(self):
        calls = _Callbacks(grounding={"ok": False, "i_dont_know": True})
        result = asyncio.run(calls.loop().run("read repo and verify"))
        self.assertFalse(result["ok"])
        self.assertEqual(calls.calls, ["retrieve"])
        self.assertEqual(result["final_state"], agent.S_HALT)
        self.assertNotIn("answer", result)

    def test_tool_policy_denial_is_terminal(self):
        calls = _Callbacks(allow=False)
        result = asyncio.run(calls.loop().run("read repo and verify"))
        self.assertFalse(result["ok"])
        self.assertEqual(calls.calls, ["retrieve"])
        self.assertEqual(result["final_state"], agent.S_HALT)

    def test_failed_observation_prevents_dependent_work(self):
        calls = _Callbacks(tool_ok=False)
        result = asyncio.run(calls.loop().run("read repo and verify"))
        self.assertFalse(result["ok"])
        self.assertEqual(calls.calls, ["retrieve", "repo_map"])
        self.assertNotIn("answer", result)

    def test_final_gate_denial_precedes_inference(self):
        calls = _Callbacks()
        result = asyncio.run(calls.loop(lambda_floor=0.93).run("summarize"))
        self.assertFalse(result["ok"])
        self.assertEqual(calls.calls, ["retrieve"])
        self.assertEqual(result["final_state"], agent.S_HALT)
        self.assertIn("FINALIZE", result["halt_reason"])
        self.assertNotIn("answer", result)

    def test_failed_verification_halts_after_bounded_reflection(self):
        calls = _Callbacks()
        result = asyncio.run(calls.loop(lambda_floor=0.93).run("read repo and verify"))
        self.assertFalse(result["ok"])
        self.assertEqual(calls.calls, ["retrieve", "repo_map"])
        self.assertIn("VERIFY", result["halt_reason"])
        self.assertEqual([row["state"] for row in result["steps"]][-2:],
                         [agent.S_REFLECT, agent.S_HALT])
        self.assertLessEqual(result["step_count"], result["guards"]["max_steps"])

    def test_failed_verification_does_not_overrun_budget_to_reflect(self):
        calls = _Callbacks()
        result = asyncio.run(calls.loop(lambda_floor=0.93, max_steps=7).run("read repo"))
        self.assertFalse(result["ok"])
        self.assertEqual(calls.calls, ["retrieve", "repo_map"])
        self.assertEqual(result["step_count"], 7)
        self.assertEqual([row["state"] for row in result["steps"]][-2:],
                         [agent.S_VERIFY, agent.S_HALT])

    def test_voice_switch_cannot_release_a_below_floor_answer(self):
        calls = _Callbacks(grounding=_grounding(3))
        with patch.dict(os.environ, {"A11OY_WALLPA_FINALIZE": "1"}), \
             patch.object(agent, "_wallpa_speak_final", return_value={
                 "wallpa_factor": 1.0, "voice": "SIMULATED"}) as voice:
            result = asyncio.run(calls.loop().run("summarize"))
        self.assertFalse(result["ok"])
        self.assertEqual(result["final_state"], agent.S_HALT)
        self.assertNotIn("answer", result)
        self.assertNotIn("agent.finalize", [receipt["action"] for receipt in calls.receipts])
        voice.assert_not_called()

    def test_admitted_synthetic_path_retains_real_fsm_result(self):
        calls = _Callbacks()
        result = asyncio.run(calls.loop().run("read repo and verify"))
        self.assertTrue(result["ok"])
        self.assertEqual(result["final_state"], agent.S_FINALIZE)
        self.assertEqual(calls.calls, ["retrieve", "repo_map", "run_tests", "model"])
        self.assertTrue(all(row["gate_allow"] for row in result["steps"]))
        self.assertFalse(result["chain_verified"])


if __name__ == "__main__":
    unittest.main()
