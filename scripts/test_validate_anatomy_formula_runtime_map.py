#!/usr/bin/env python3
"""Negative-fixture self-test for validate_anatomy_formula_runtime_map.py.

The anatomy/formula/runtime map validator enforces the autonomous-learning
doctrine: the canonical hub is a11oy, promotion REQUIRES a human
(promotionModel=human_promotion_required), and the agent's forbiddenModes must
include self_approve / self_promote / deploy / publish. It also rejects
unsupported claimStatus values. Nothing proved those guard rules keep working —
a future edit could silently let the doctrine flip to self-promotion with nobody
noticing.

This test feeds the REAL validator tampered maps and asserts it FAILS on each
(exit 1), plus an honest fixture (the committed map) that PASSES (exit 0) so the
guard is real, not merely always-failing.

Pure stdlib (unittest), network-free, touches no live manifest. Run by file path
(the scripts dir is not an importable package):
    python3 scripts/test_validate_anatomy_formula_runtime_map.py
"""
from __future__ import annotations

import copy
import importlib.util
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
_VALIDATOR = os.path.join(_HERE, "validate_anatomy_formula_runtime_map.py")

_spec = importlib.util.spec_from_file_location("validate_anatomy_formula_runtime_map", _VALIDATOR)
validator = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(validator)

_REAL = json.loads(Path(validator.MAP_PATH).read_text(encoding="utf-8"))


def honest() -> dict:
    return copy.deepcopy(_REAL)


def run_validator(manifest: dict) -> int:
    """Redirect MAP_PATH at a temp copy; THEOREM_MANIFEST_PATH stays real so the
    theoremRuntimeManifestId cross-check resolves against the committed manifest."""
    fd, path = tempfile.mkstemp(suffix=".json", dir=str(validator.REPO_ROOT))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh)
        orig = validator.MAP_PATH
        validator.MAP_PATH = Path(path)
        try:
            with redirect_stdout(io.StringIO()):
                return validator.main()
        finally:
            validator.MAP_PATH = orig
    finally:
        os.unlink(path)


class AnatomyMapGuardSelfTest(unittest.TestCase):
    def test_honest_map_passes(self):
        """Sanity floor: the committed map must PASS so the guard is not merely
        always-failing."""
        self.assertEqual(run_validator(honest()), 0)

    def test_promotion_model_not_human_fails(self):
        """The core anti-self-promotion rule: promotion must require a human."""
        m = honest()
        m["autonomousLearningDoctrine"]["promotionModel"] = "autonomous"
        self.assertEqual(run_validator(m), 1)

    def test_missing_forbidden_mode_fails(self):
        for mode in ("self_approve", "self_promote", "deploy", "publish"):
            with self.subTest(mode=mode):
                m = honest()
                m["autonomousLearningDoctrine"]["forbiddenModes"] = [
                    x for x in m["autonomousLearningDoctrine"]["forbiddenModes"] if x != mode
                ]
                self.assertEqual(run_validator(m), 1)

    def test_canonical_hub_changed_fails(self):
        m = honest()
        m["canonicalHub"] = "huggingface"
        self.assertEqual(run_validator(m), 1)

    def test_bad_organ_claim_status_fails(self):
        m = honest()
        m["organs"][0]["claimStatus"] = "totally-proven"
        self.assertEqual(run_validator(m), 1)

    def test_missing_required_repo_fails(self):
        m = honest()
        # Drop the canonical a11oy organ -> required-repo check must fire.
        m["organs"] = [o for o in m["organs"] if o.get("repo") != "a11oy"]
        self.assertEqual(run_validator(m), 1)


def _minimal_valid_map() -> dict:
    """A map that passes every check EXCEPT whatever a test deliberately breaks,
    so a single failure isolates the rule under test."""
    def organ(repo: str, formulas: list | None = None) -> dict:
        return {
            "repo": repo,
            "anatomyRole": f"{repo} role",
            "formulaRuntime": formulas or [],
            "theoremAnchors": [],
            # a receipt surface + live_route so a verified-runtime organ clears
            # RULE 2 (field presence; route grep is skipped when the temp repo
            # has no router files) and RULE 3 (receipt advisory).
            "receiptSurface": ["szl-receipt"],
            "testEvidence": [],
            "udsStage": "component-supporting",
            "hfStage": "referenced-from-a11oy-mirror",
            "claimStatus": "verified-runtime",
            "live_route": "/api/a11oy/v1/agent/cycle",
            "autonomousLearningRole": "observer",
            "gaps": [],
        }

    return {
        "schemaVersion": 1,
        "generatedBy": "test",
        "observedAt": "2026-07-03",
        "canonicalHub": "a11oy",
        "canonicalRule": "test",
        "autonomousLearningDoctrine": {
            "promotionModel": "human_promotion_required",
            "forbiddenModes": ["self_approve", "self_promote", "deploy", "publish"],
        },
        "organs": [
            organ("a11oy"),
            organ("lutar-lean"),
            organ("ouroboros-thesis"),
            organ("agi-forecast"),
        ],
    }


class StubDetectionSelfTest(unittest.TestCase):
    """Prove the validator catches the amaru-fake pattern: a verified-runtime
    organ whose runtimeFile resolves (via a vite alias) to a look-alike stub
    with a home-grown non-crypto `simpleHash` and no proof ledger."""

    def _run_in_temp_repo(self, layout: dict[str, str], mp: dict) -> int:
        with tempfile.TemporaryDirectory() as root:
            root_path = Path(root)
            for rel, content in layout.items():
                dst = root_path / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_text(content, encoding="utf-8")
            (root_path / "docs").mkdir(parents=True, exist_ok=True)
            (root_path / "docs" / "anatomy-formula-runtime-map.json").write_text(
                json.dumps(mp), encoding="utf-8"
            )
            (root_path / "docs" / "theorem-runtime-manifest.json").write_text(
                json.dumps({"entries": []}), encoding="utf-8"
            )
            orig = (validator.REPO_ROOT, validator.MAP_PATH, validator.THEOREM_MANIFEST_PATH)
            validator.REPO_ROOT = root_path
            validator.MAP_PATH = root_path / "docs" / "anatomy-formula-runtime-map.json"
            validator.THEOREM_MANIFEST_PATH = root_path / "docs" / "theorem-runtime-manifest.json"
            try:
                with redirect_stdout(io.StringIO()):
                    return validator.main()
            finally:
                validator.REPO_ROOT, validator.MAP_PATH, validator.THEOREM_MANIFEST_PATH = orig

    # The exact amaru-fake vite alias -> _stubs look-alike.
    _FAKE_VITE = (
        "export default {\n"
        "  resolve: {\n"
        "    alias: {\n"
        "      '@workspace/codex-kernel': path.resolve(import.meta.dirname, "
        "'src/_stubs/codex-kernel/index.ts'),\n"
        "    },\n"
        "  },\n"
        "};\n"
    )
    _FAKE_STUB = (
        "export function simpleHash(s) { let h = 0; for (const c of s) "
        "h = (h * 31 + c.charCodeAt(0)) | 0; return h; }\n"
        "export function runLoop() { return { stop_reason: 'hard_fail_limit' }; }\n"
    )
    _REAL_KERNEL = (
        "export { hashString, chainHash, hashJson } from './hash.js';\n"
        "export { ProofLedger } from './ledger.js';\n"
        "export { runLoop } from './kernel.js';\n"
    )

    def test_alias_resolving_to_simplehash_stub_fails(self):
        mp = _minimal_valid_map()
        mp["organs"][0]["formulaRuntime"] = [
            {
                "formula": "CodexKernelReplay",
                "runtimeFile": "@workspace/codex-kernel",
                "theoremRuntimeManifestId": None,
                "claimStatus": "verified-runtime",
            }
        ]
        layout = {
            "organs/amaru/web/vite.config.ts": self._FAKE_VITE,
            "organs/amaru/web/src/_stubs/codex-kernel/index.ts": self._FAKE_STUB,
        }
        self.assertEqual(self._run_in_temp_repo(layout, mp), 1)

    def test_empty_export_stub_direct_path_fails(self):
        mp = _minimal_valid_map()
        mp["organs"][0]["formulaRuntime"] = [
            {
                "formula": "DeadStub",
                "runtimeFile": "organs/sentra/stubs/codex-kernel/index.ts",
                "theoremRuntimeManifestId": None,
                "claimStatus": "verified-runtime",
            }
        ]
        layout = {"organs/sentra/stubs/codex-kernel/index.ts": "export {};\n"}
        self.assertEqual(self._run_in_temp_repo(layout, mp), 1)

    def test_alias_resolving_to_real_kernel_passes(self):
        """Positive control: the SAME alias pointing at the real (vendored)
        kernel must NOT trip stub detection."""
        mp = _minimal_valid_map()
        mp["organs"][0]["formulaRuntime"] = [
            {
                "formula": "CodexKernelReplay",
                "runtimeFile": "@workspace/codex-kernel",
                "theoremRuntimeManifestId": None,
                "claimStatus": "verified-runtime",
            }
        ]
        real_vite = self._FAKE_VITE.replace(
            "src/_stubs/codex-kernel/index.ts", "src/vendor/codex-kernel/index.ts"
        )
        layout = {
            "organs/amaru/web/vite.config.ts": real_vite,
            "organs/amaru/web/src/vendor/codex-kernel/index.ts": self._REAL_KERNEL,
        }
        self.assertEqual(self._run_in_temp_repo(layout, mp), 0)

    def test_is_stub_module_unit(self):
        with tempfile.TemporaryDirectory() as d:
            empty = Path(d) / "empty.ts"
            empty.write_text("export {};\n", encoding="utf-8")
            self.assertIsNotNone(validator.is_stub_module(empty))

            fake = Path(d) / "fake.ts"
            fake.write_text("export function simpleHash(){return 0}\n", encoding="utf-8")
            self.assertIsNotNone(validator.is_stub_module(fake))

            real = Path(d) / "real.ts"
            real.write_text(
                "export function chainHash(a,b,c){return hashString(`${a}|${b}|${c}`)}\n"
                "export class ProofLedger { append(){} digest(){return 'x'} }\n",
                encoding="utf-8",
            )
            self.assertIsNone(validator.is_stub_module(real))


class OwnRepoRule1SelfTest(unittest.TestCase):
    """RULE 1 (own-repo / no-borrowing): a cross-repo organ that claims
    verified-runtime while pointing its runtimeFile at a11oy's shared hub gate
    tree (packages/*) is BORROWING a hub file to look wired — must fail. The
    same organ pointing at its OWN subtree, or downgraded to wired-shared, must
    pass."""

    def _run_in_temp_repo(self, layout: dict[str, str], mp: dict) -> int:
        with tempfile.TemporaryDirectory() as root:
            root_path = Path(root)
            for rel, content in layout.items():
                dst = root_path / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_text(content, encoding="utf-8")
            (root_path / "docs").mkdir(parents=True, exist_ok=True)
            (root_path / "docs" / "anatomy-formula-runtime-map.json").write_text(
                json.dumps(mp), encoding="utf-8"
            )
            (root_path / "docs" / "theorem-runtime-manifest.json").write_text(
                json.dumps({"entries": []}), encoding="utf-8"
            )
            orig = (validator.REPO_ROOT, validator.MAP_PATH, validator.THEOREM_MANIFEST_PATH)
            validator.REPO_ROOT = root_path
            validator.MAP_PATH = root_path / "docs" / "anatomy-formula-runtime-map.json"
            validator.THEOREM_MANIFEST_PATH = root_path / "docs" / "theorem-runtime-manifest.json"
            try:
                with redirect_stdout(io.StringIO()):
                    return validator.main()
            finally:
                validator.REPO_ROOT, validator.MAP_PATH, validator.THEOREM_MANIFEST_PATH = orig

    _REAL_GATE = (
        "export function evaluateGate(input) {\n"
        "  return { ok: hashString(JSON.stringify(input)) !== '' };\n"
        "}\n"
        "export { hashString } from './hash.js';\n"
    )

    def _map_with_rosie(self, runtime_file: str, status: str) -> dict:
        mp = _minimal_valid_map()
        rosie = {
            "repo": "rosie",
            "anatomyRole": "rosie role",
            "formulaRuntime": [
                {
                    "formula": "PolicyGate",
                    "runtimeFile": runtime_file,
                    "theoremRuntimeManifestId": None,
                    "claimStatus": status,
                }
            ],
            "theoremAnchors": [],
            "receiptSurface": ["szl-receipt"],
            "testEvidence": [],
            "udsStage": "component-supporting",
            "hfStage": "referenced-from-a11oy-mirror",
            "claimStatus": status,
            "autonomousLearningRole": "observer",
            "gaps": [],
        }
        if status == "verified-runtime":
            rosie["live_route"] = "/api/a11oy/v1/agent/cycle"
        mp["organs"].append(rosie)
        return mp

    def test_borrowed_hub_file_verified_fails(self):
        """rosie claims verified-runtime but its runtimeFile lands in a11oy's
        shared packages/ gate tree -> borrowed -> FAIL."""
        mp = self._map_with_rosie(
            "packages/policy/decision_gate.ts", "verified-runtime"
        )
        layout = {"packages/policy/decision_gate.ts": self._REAL_GATE}
        self.assertEqual(self._run_in_temp_repo(layout, mp), 1)

    def test_borrowed_hub_file_downgraded_passes(self):
        """The SAME borrowed reference, honestly labelled wired-shared, passes:
        a non-verified status may reference the shared gate."""
        mp = self._map_with_rosie(
            "packages/policy/decision_gate.ts", "wired-shared"
        )
        layout = {"packages/policy/decision_gate.ts": self._REAL_GATE}
        self.assertEqual(self._run_in_temp_repo(layout, mp), 0)

    def test_own_subtree_verified_passes(self):
        """rosie pointing verified-runtime at its OWN organs/rosie subtree (not
        a borrowed hub file) passes RULE 1."""
        mp = self._map_with_rosie(
            "organs/rosie/policy/decision_gate.ts", "verified-runtime"
        )
        layout = {"organs/rosie/policy/decision_gate.ts": self._REAL_GATE}
        self.assertEqual(self._run_in_temp_repo(layout, mp), 0)

    def test_a11oy_own_hub_gate_verified_passes(self):
        """The hub itself OWNS packages/*, so an a11oy organ pointing there is
        not borrowing -> verified-runtime is legitimate."""
        mp = _minimal_valid_map()
        mp["organs"][0]["formulaRuntime"] = [
            {
                "formula": "PolicyGate",
                "runtimeFile": "packages/policy/decision_gate.ts",
                "theoremRuntimeManifestId": None,
                "claimStatus": "verified-runtime",
            }
        ]
        layout = {"packages/policy/decision_gate.ts": self._REAL_GATE}
        self.assertEqual(self._run_in_temp_repo(layout, mp), 0)


class LiveRouteRule2SelfTest(unittest.TestCase):
    """RULE 2 (earned status needs a live route): a verified-runtime organ must
    declare a `live_route`, and — when router code is present — that route must
    be registered there."""

    def _run_in_temp_repo(self, layout: dict[str, str], mp: dict) -> int:
        with tempfile.TemporaryDirectory() as root:
            root_path = Path(root)
            for rel, content in layout.items():
                dst = root_path / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_text(content, encoding="utf-8")
            (root_path / "docs").mkdir(parents=True, exist_ok=True)
            (root_path / "docs" / "anatomy-formula-runtime-map.json").write_text(
                json.dumps(mp), encoding="utf-8"
            )
            (root_path / "docs" / "theorem-runtime-manifest.json").write_text(
                json.dumps({"entries": []}), encoding="utf-8"
            )
            orig = (validator.REPO_ROOT, validator.MAP_PATH, validator.THEOREM_MANIFEST_PATH)
            validator.REPO_ROOT = root_path
            validator.MAP_PATH = root_path / "docs" / "anatomy-formula-runtime-map.json"
            validator.THEOREM_MANIFEST_PATH = root_path / "docs" / "theorem-runtime-manifest.json"
            try:
                with redirect_stdout(io.StringIO()):
                    return validator.main()
            finally:
                validator.REPO_ROOT, validator.MAP_PATH, validator.THEOREM_MANIFEST_PATH = orig

    def test_missing_live_route_fails(self):
        """A verified-runtime organ with no live_route field must fail."""
        mp = _minimal_valid_map()
        del mp["organs"][0]["live_route"]
        self.assertEqual(run_validator(mp), 1)

    def test_live_route_not_in_router_fails(self):
        """When router code IS present but does not register the declared route,
        the claim is not earned -> fail."""
        mp = _minimal_valid_map()
        mp["organs"][0]["live_route"] = "/api/a11oy/v1/ghost/endpoint"
        layout = {
            "serve.py": (
                "app.add_api_route('/api/a11oy/v1/gates', gates_handler)\n"
            )
        }
        self.assertEqual(self._run_in_temp_repo(layout, mp), 1)

    def test_live_route_served_passes(self):
        """A verified-runtime organ whose declared route IS registered in the
        served router passes RULE 2. Route hub segment is templated in code."""
        mp = _minimal_valid_map()
        mp["organs"][0]["live_route"] = "/api/a11oy/v1/agent/cycle"
        layout = {
            "szl_agentic_loop.py": (
                "routes = [Route('/api/%s/v1/agent/cycle' % ns, cycle_handler)]\n"
            )
        }
        self.assertEqual(self._run_in_temp_repo(layout, mp), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
