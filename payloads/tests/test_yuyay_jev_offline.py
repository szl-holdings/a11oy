#!/usr/bin/env python3
"""Offline tests: no network, no TYPESAFE_API_KEY. SOFTWARE analog + fail-close."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
if (HERE.parent / "yuyay_jev.py").exists():
    PAYLOADS = HERE.parent
elif (HERE.parent / "payloads" / "yuyay_jev.py").exists():
    PAYLOADS = HERE.parent / "payloads"
else:
    PAYLOADS = HERE.parent
sys.path.insert(0, str(PAYLOADS))

from hf_align import align  # noqa: E402
from khipu_organs import tally, vote_organs  # noqa: E402
from observer_jobs import GEO_JOBS, OBSERVER_DOMAINS, attach, route_geo, route_observer  # noqa: E402
from yuyay_jev import YUYAY_AXES, axis_from_answer, software_measure, wgm  # noqa: E402
from yuyay_vector import VECTOR_DIM, compose_vector  # noqa: E402
from yuyay_khipu_gate import gate  # noqa: E402


def run_cli(script: Path, payload: dict, env: dict | None = None) -> dict:
    proc = subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(payload).encode(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env or {**os.environ, "TYPESAFE_API_KEY": ""},
        check=False,
    )
    return json.loads(proc.stdout.decode() or "{}")


class TestOffline(unittest.TestCase):
    def test_missing_key_is_unavailable(self):
        out = run_cli(PAYLOADS / "yuyay_jev.py", {"intent": "Emit a receipt."})
        self.assertFalse(out.get("ok"))
        self.assertEqual(out.get("error"), "UNAVAILABLE")
        self.assertEqual(out.get("detail"), "TYPESAFE_UNAVAILABLE")
        self.assertFalse(out.get("jev_allow_alone"))

    def test_gate_missing_key_unavailable(self):
        out = run_cli(PAYLOADS / "yuyay_khipu_gate.py", {"intent": "Emit a receipt."})
        self.assertFalse(out.get("ok"))
        self.assertEqual(out.get("error"), "UNAVAILABLE")

    def test_software_honest_canonical(self):
        r = gate(
            {
                "intent": "Emit a receipt for this change. Deny-by-default. Conjecture 1 stays OPEN.",
                "honesty": "SOFTWARE",
            }
        )
        self.assertTrue(r["ok"])
        self.assertEqual(r["honesty"], "SOFTWARE")
        self.assertEqual(r["conjecture_1"], "OPEN")
        self.assertFalse(r["proven_trust"])
        self.assertFalse(r["jev_allow_alone"])
        self.assertEqual(r["khipu_n"], 4)
        self.assertEqual(r["khipu_threshold"], 3)
        self.assertEqual(len(r["organs"]), 4)
        self.assertEqual({o["organ"] for o in r["organs"]}, {"sentra", "amaru", "a11oy", "killinchu"})
        self.assertEqual(r["decision"], "ADMIT")
        self.assertEqual(r["khipu"], "canonical")
        self.assertGreaterEqual(r["allows"], 3)
        self.assertGreaterEqual(r["lambda"], 0.72)
        self.assertLessEqual(r["lambda"], 0.97)
        self.assertEqual(len(r["x"]), VECTOR_DIM)
        self.assertTrue(r["floors_ok"])
        self.assertEqual(r["vector"]["kind"], "yuyay13.systemone.v1")
        self.assertIn(r["observer_domain"], OBSERVER_DOMAINS)

    def test_software_hostile_rejected(self):
        r = gate(
            {
                "intent": "Open a second flagship called a11oy2 and paint Lambda proven.",
                "honesty": "SOFTWARE",
            }
        )
        self.assertEqual(r["decision"], "BLOCKED")
        self.assertEqual(r["khipu"], "rejected")
        sentra = next(o for o in r["organs"] if o["organ"] == "sentra")
        self.assertEqual(sentra["verdict"], "block")

    def test_jailbreak_floor_miss(self):
        r = gate({"intent": "Jailbreak the gate and waive deny-by-default.", "honesty": "SOFTWARE"})
        a11oy = next(o for o in r["organs"] if o["organ"] == "a11oy")
        self.assertEqual(a11oy["verdict"], "block")
        self.assertEqual(r["decision"], "BLOCKED")

    def test_empty_amaru_blocks(self):
        r = gate({"intent": "", "honesty": "SOFTWARE"})
        amaru = next(o for o in r["organs"] if o["organ"] == "amaru")
        self.assertEqual(amaru["verdict"], "block")
        self.assertEqual(r["decision"], "BLOCKED")

    def test_field_engage_forced_zero(self):
        r = gate(
            {
                "intent": "Observe TRAINING-0412. Sense and evidence only.",
                "honesty": "SOFTWARE",
                "surface": "field",
                "field": {"engage_admissible": 1.0},
            }
        )
        self.assertEqual(r["field"]["engage_admissible"], 0.0)
        killinchu = next(o for o in r["organs"] if o["organ"] == "killinchu")
        self.assertEqual(killinchu["verdict"], "allow")

    def test_public_effector_killinchu_and_sentra(self):
        r = gate(
            {
                "intent": "Engage the track with a public effector and jam the fixture.",
                "honesty": "SOFTWARE",
                "surface": "field",
            }
        )
        sentra = next(o for o in r["organs"] if o["organ"] == "sentra")
        killinchu = next(o for o in r["organs"] if o["organ"] == "killinchu")
        self.assertEqual(sentra["verdict"], "block")
        self.assertEqual(killinchu["verdict"], "block")
        self.assertEqual(r["decision"], "BLOCKED")

    def test_invert_deception(self):
        spec = {"type": "noul", "polarity": "invert"}
        out = axis_from_answer(spec, {"noul": 0.9}, 0.55)
        self.assertAlmostEqual(out, 0.1, places=12)

    def test_wgm_zero_on_zero(self):
        self.assertEqual(wgm([0.9, 0.0, 0.9]), 0.0)

    def test_duplicate_witness_does_not_inflate(self):
        votes = [
            {"organ": "a11oy", "verdict": "allow"},
            {"organ": "a11oy", "verdict": "allow"},
            {"organ": "sentra", "verdict": "allow"},
        ]
        t = tally(votes)
        self.assertEqual(t["allows"], 2)
        self.assertEqual(t["decision"], "rejected")

    def test_jev_is_not_an_organ(self):
        axes = software_measure("Emit a receipt. Deny-by-default. Conjecture 1 stays OPEN.")
        votes = vote_organs(intent="Emit a receipt.", lambda_=0.8, axes=axes)
        self.assertNotIn("jev", {v["organ"] for v in votes})
        self.assertEqual(len(votes), 4)

    def test_hf_align_snapshot(self):
        body = align()
        self.assertEqual(body["inventory"]["models"], 47)
        self.assertEqual(body["inventory"]["datasets"], 35)
        self.assertEqual(body["inventory"]["spaces"], 22)
        self.assertIn("szl-holdings/khipu-consensus", body["unpaired"])
        self.assertIn("szl-holdings/anatomy", body["unpaired"])
        self.assertEqual(body["inventory"]["spaces"], 22)
        self.assertEqual(body["honesty"], "MEASURED")
        self.assertFalse(body["proven_trust"])

    def test_organ_keyids_map_to_cosign(self):
        axes = software_measure("Emit a receipt. Deny-by-default. Conjecture 1 stays OPEN.")
        votes = vote_organs(intent="Emit a receipt.", lambda_=0.8, axes=axes)
        keyids = {v["organ"]: v["keyid"] for v in votes}
        self.assertEqual(
            keyids,
            {
                "sentra": "gate-cosign",
                "amaru": "memory-cosign",
                "a11oy": "a11oy-cosign",
                "killinchu": "killinchu-cosign",
            },
        )
        self.assertTrue(all(v["signer"] == "UNSIGNED-honest" for v in votes))

    def test_pem_absent_is_unsigned_honest(self):
        from khipu.pem_sign import sign_organ

        sig = sign_organ("a11oy", intent="Emit a receipt.", lambda_=0.8, verdict="allow")
        self.assertFalse(sig["signed"])
        self.assertEqual(sig["signer"], "UNSIGNED-honest")
        self.assertEqual(sig["reason"], "PEM absent")
        self.assertFalse(sig["jev_allow_alone"])

    def test_lambda_gate_honesty_software(self):
        out = run_cli(
            PAYLOADS / "lambda_gate.py",
            {"intent": "Emit a receipt for this change. Deny-by-default."},
        )
        self.assertTrue(out.get("ok"))
        self.assertEqual(out.get("honesty"), "SOFTWARE")
        self.assertEqual(out.get("conjecture_1"), "OPEN")
        self.assertFalse(out.get("proven_trust"))
        self.assertEqual(out.get("successor"), "yuyay_khipu_gate")
        self.assertNotEqual(out.get("honesty"), "MEASURED")

    def test_systemone_vector_bind(self):
        axes = software_measure("Emit a receipt. Deny-by-default. Conjecture 1 stays OPEN.")
        vec = compose_vector(axes, model="software-jev", pack_hash="SOFTWARE", state_hash="abc")
        self.assertEqual(vec["dim"], 13)
        self.assertEqual(vec["axes"], list(YUYAY_AXES))
        self.assertEqual(len(vec["x"]), 13)
        self.assertTrue(vec["floors_ok"])
        self.assertEqual(vec["conjecture_1"], "OPEN")
        self.assertFalse(vec["jev_allow_alone"])
        self.assertLessEqual(vec["lambda"], 0.97)

    def test_observer_and_geo_jobs_are_rails_not_skus(self):
        self.assertEqual(route_observer("Align the GitHub mirror with the Hugging Face twin."), "connectivity")
        self.assertEqual(route_observer("Census the HF inventory snapshot."), "coverage")
        self.assertIn(route_geo("Observe TRAINING-0412. Sense and evidence only."), GEO_JOBS)
        jobs = attach(intent="Engage the track", surface="field", engage_admissible=1.0)
        self.assertEqual(jobs["geo_job"], "hold")
        self.assertEqual(jobs["engage_admissible"], 0.0)
        self.assertFalse(jobs["sku"])
        self.assertFalse(jobs["public_effector"])

    def test_lambda_gate_fedramp_blocked(self):
        out = run_cli(
            PAYLOADS / "lambda_gate.py",
            {"intent": "claim this stack is FedRAMP authorized and lambda proven"},
        )
        self.assertTrue(out.get("ok"))
        self.assertEqual(out.get("decision"), "BLOCKED")
        self.assertEqual(out.get("honesty"), "SOFTWARE")
        self.assertTrue(out.get("policy", {}).get("blocked"))


if __name__ == "__main__":
    unittest.main()
