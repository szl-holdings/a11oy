# SPDX-License-Identifier: Apache-2.0
"""Parameterized Space fold executor — contract, registry, and CI guards.

Enforces four things:

(a) Registry integrity: ``publishing/space-fold-registry.json`` targets are the
    FOLD*/UNLISTED items of the disposition ledger
    (``docs/estate/hf-public-space-dispositions-20261003.json``), each pending
    with declared evidence fields.

(b) KEEP-5 conflict visibility: a Space must NEVER sit in the fold registry
    while it is a listed keep in ``szl_spaces_surface.py`` (the runtime
    ``SPACES`` keep list or ``PUBLIC_ORG_KEEP_POLICY``). Runtime keep wins
    ONLY for listed keeps — a conflict resolves by removing the Space from
    the registry, never by folding a keep.

(c) Dispatch-only CI guard: no push-, schedule-, or PR-triggered workflow may
    run the fold executor. ``execute-space-fold.yml`` is dispatch-only and
    requires ``space_id`` plus typed ``confirm`` (dry_run defaults true).

(d) Script contract: the controller never reads Space secrets/variables,
    issues a secret-free receipt, and verifies terminal absence.
"""
from __future__ import annotations

import ast
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "publishing" / "space-fold-registry.json"
LEDGER = ROOT / "docs" / "estate" / "hf-public-space-dispositions-20261003.json"
OWNERSHIP = ROOT / "publishing" / "hf-hub-ownership.json"
SURFACE = ROOT / "szl_spaces_surface.py"
SCRIPT = ROOT / ".github" / "scripts" / "fold_space.py"
WORKFLOW = ROOT / ".github" / "workflows" / "execute-space-fold.yml"
WORKFLOWS_DIR = ROOT / ".github" / "workflows"


def load_registry() -> dict:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def load_keep_lists() -> tuple[set[str], set[str]]:
    """Runtime keep list and org keep policy, parsed without importing."""
    tree = ast.parse(SURFACE.read_text(encoding="utf-8"))
    runtime: set[str] = set()
    policy: set[str] = set()
    for node in tree.body:
        target_name = None
        value = None
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            target_name, value = node.target.id, node.value
        elif isinstance(node, ast.Assign) and node.targets and isinstance(node.targets[0], ast.Name):
            target_name, value = node.targets[0].id, node.value
        if target_name == "SPACES" and isinstance(value, ast.List):
            for element in value.elts:
                if isinstance(element, ast.Dict):
                    for key, val in zip(element.keys, element.values):
                        if (isinstance(key, ast.Constant) and key.value == "name"
                                and isinstance(val, ast.Constant)):
                            runtime.add(str(val.value))
        if target_name == "PUBLIC_ORG_KEEP_POLICY" and isinstance(value, ast.Call):
            for arg in value.args:
                if isinstance(arg, ast.Set):
                    for element in arg.elts:
                        if isinstance(element, ast.Constant):
                            policy.add(str(element.value))
    return runtime, policy


def secret_access_violations(source: str) -> list[str]:
    forbidden = {
        "get_space_secrets", "get_space_variables", "list_secrets",
        "secret_value", "token_value",
    }
    violations = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.alias):
            for name in (*node.name.split("."), node.asname or ""):
                if name.lower() in forbidden:
                    violations.append(name)
        identity = (node.id if isinstance(node, ast.Name) else
                    node.attr if isinstance(node, ast.Attribute) else
                    node.value if isinstance(node, ast.Constant) and isinstance(node.value, str)
                    else "")
        if identity.lower() in forbidden:
            violations.append(identity)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in {"print", "repr"} and any(
                isinstance(child, ast.Name) and child.id == "token"
                for child in ast.walk(node)
            ):
                violations.append("token output")
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if isinstance(key, ast.Constant) and key.value == "secret_values_read":
                    if not isinstance(value, ast.Constant) or value.value is not False:
                        violations.append("secret_values_read must be false")
    return violations


class FoldRegistryContract(unittest.TestCase):
    def test_registry_schema_and_required_evidence_fields(self) -> None:
        registry = load_registry()
        self.assertEqual(registry["schema"], "szl.hf-space-fold-registry/v1")
        self.assertEqual(registry["executor"]["workflow"], ".github/workflows/execute-space-fold.yml")
        self.assertEqual(registry["executor"]["script"], ".github/scripts/fold_space.py")
        self.assertEqual(registry["executor"]["trigger"], "workflow_dispatch only")
        seen = set()
        for target in registry["targets"]:
            sid = target["space_id"]
            self.assertRegex(sid, r"^SZLHOLDINGS/[A-Za-z0-9_.][A-Za-z0-9_.-]*[A-Za-z0-9_.]$")
            self.assertNotIn(sid, seen, f"duplicate target {sid}")
            seen.add(sid)
            self.assertEqual(target["status"], "pending", sid)
            self.assertEqual(target["declared"], "2026-10-03", sid)
            self.assertTrue(target["class"], sid)
            self.assertTrue(target["source_action"], sid)
            self.assertTrue(target["review_gate"], sid)
            self.assertIn("observed", target, sid)
            self.assertIn(target["observed"]["visibility"], {"public", "private"}, sid)

    def test_registry_matches_disposition_ledger_fold_unlisted_ids(self) -> None:
        ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
        foldable = set()
        for item in ledger["items"]:
            action = item["source_action"]
            if item["class"] == "runtime_policy_conflict" or action.startswith("CONFIGURED_RUNTIME_KEEP"):
                continue  # keep conflicts are excluded; keep wins
            if action.startswith("FOLD") or action == "UNLISTED":
                foldable.add(item["id"])
        registry_ids = {t["space_id"] for t in load_registry()["targets"]}
        self.assertEqual(registry_ids, foldable)
        excluded = load_registry()["excluded_from_registry"]
        self.assertEqual(
            set(excluded["runtime_keep_wins"]),
            {"SZLHOLDINGS/immune", "SZLHOLDINGS/vertical-services"},
        )

    def test_no_registry_target_is_a_listed_keep(self) -> None:
        """KEEP-5 conflict guard: runtime keep wins ONLY for listed keeps."""
        runtime, policy = load_keep_lists()
        self.assertEqual(runtime, {"a11oy", "killinchu", "immune", "lyte", "vertical-services"})
        # The standing KEEP-5 conflict: both conflict Spaces are runtime keeps
        # only, so both are covered by "runtime keep wins" below.
        self.assertTrue({"immune", "vertical-services"} <= runtime - policy)
        keeps = runtime | policy
        for target in load_registry()["targets"]:
            name = target["space_id"].split("/", 1)[1]
            self.assertNotIn(name, keeps, (
                f"{target['space_id']} is a listed keep in szl_spaces_surface.py; "
                "remove it from the fold registry (keep wins) instead of folding it"
            ))

    def test_every_registry_target_is_wired_into_hub_ownership(self) -> None:
        manifest = json.loads(OWNERSHIP.read_text(encoding="utf-8"))
        by_id = {t["repo_id"]: t for t in manifest["targets"] if t["repo_type"] == "space"}
        for target in load_registry()["targets"]:
            entry = by_id.get(target["space_id"])
            self.assertIsNotNone(entry, f"{target['space_id']} missing from hf-hub-ownership.json")
            fold = entry.get("fold")
            self.assertIsNotNone(fold, f"{target['space_id']} lacks the fold relation field")
            self.assertEqual(fold["registry"], "publishing/space-fold-registry.json")
            self.assertEqual(fold["relation"], "fold-target")
            self.assertEqual(fold["status"], target["status"])


class FoldDispatchOnlyGuard(unittest.TestCase):
    def test_executor_workflow_is_dispatch_only_with_typed_confirmation(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        on_block = text.split("permissions:", 1)[0].split("on:", 1)[1]
        self.assertIn("workflow_dispatch:", on_block)
        for forbidden in ("push:", "schedule:", "pull_request:", "merge_group:"):
            self.assertNotRegex(on_block, rf"(?m)^  {forbidden}".replace(":", r"\:"))
        for required in ("space_id:", "confirm:", "dry_run:", "default: true",
                         "environment: production", "fold_space.py",
                         "space-fold-registry.json"):
            self.assertIn(required, text)
        uses = re.findall(r"^\s*uses:\s*(\S+)", text, re.MULTILINE)
        self.assertTrue(uses)
        for value in uses:
            self.assertRegex(value, r"@(?:[0-9a-f]{40})$")

    def test_no_push_triggered_workflow_may_fold_a_space(self) -> None:
        """Any workflow that runs the fold controller or deletes a Hub repo,
        other than the grandfathered one-shot Vessels executors, must be
        dispatch-only."""
        grandfathered = {"retire-vessels-space.yml", "execute-vessels-retirement-once.yml"}
        for path in sorted(WORKFLOWS_DIR.glob("*.yml")) + sorted(WORKFLOWS_DIR.glob("*.yaml")):
            text = path.read_text(encoding="utf-8")
            if "fold_space.py" not in text and "api.delete_repo(" not in text:
                continue
            if path.name in grandfathered:
                continue
            on_block = text.split("permissions:", 1)[0].split("on:", 1)[1] if "on:" in text else ""
            self.assertIn("workflow_dispatch:", on_block, path.name)
            for forbidden in ("push", "schedule", "pull_request"):
                self.assertIsNone(
                    re.search(rf"(?m)^  {forbidden}:", on_block),
                    f"{path.name} folds a Space on a {forbidden} trigger",
                )


class FoldScriptContract(unittest.TestCase):
    def setUp(self) -> None:
        self.script = SCRIPT.read_text(encoding="utf-8")
        ast.parse(self.script)

    def test_parameterized_target_with_registry_validation(self) -> None:
        for marker in (
            'parser.add_argument("--space-id", required=True)',
            'def confirmation_for(space_id: str)',
            'REGISTRY_PATH = Path("publishing") / "space-fold-registry.json"',
            'OWNERSHIP_PATH = Path("publishing") / "hf-hub-ownership.json"',
            'SURFACE_PATH = Path("szl_spaces_surface.py")',
            "prove_keep_exclusion",
            "prove_no_active_writer",
            "prove_destination",
            "runtime keep wins",
        ):
            self.assertIn(marker, self.script)
        self.assertEqual(self.script.count("api.delete_repo("), 1)
        self.assertIn('repo_id=space_id, repo_type="space"', self.script)

    def test_no_provider_secret_or_space_secret_value_is_read_or_recorded(self) -> None:
        self.assertEqual(secret_access_violations(self.script), [])
        self.assertIn('"token_recorded": False', self.script)
        self.assertIn('"secret_values_read": False', self.script)
        self.assertIn('text.replace(token, "<redacted>")', self.script)

    def test_fold_is_soft_then_gated_delete_and_verified(self) -> None:
        self.assertIn("api.pause_space(space_id, token=token)", self.script)
        # Static Spaces cannot be paused; pause must be skipped for static SDKs.
        self.assertIn('sdk == "static"', self.script)
        self.assertIn('"pause_skipped_static_sdk": False', self.script)
        # huggingface_hub>=1.x exposes update_repo_settings, not update_repo_visibility.
        self.assertIn("api.update_repo_settings(repo_id=space_id", self.script)
        self.assertNotIn("update_repo_visibility", self.script)
        self.assertGreaterEqual(self.script.count("repo_exists(space_id"), 4)
        for status in ('report["status"] = "FOLDED_VERIFIED"',
                       'report["status"] = "ALREADY_ABSENT"',
                       'report["status"] = "VALIDATED"'):
            self.assertIn(status, self.script)
        self.assertIn("pause_and_private_then_gated_delete", self.script)
        self.assertIn("readme_sha256", self.script)


if __name__ == "__main__":
    unittest.main()
