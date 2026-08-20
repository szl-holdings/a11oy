# SPDX-License-Identifier: Apache-2.0

import ast
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".github/scripts/solo_estate_readonly_inventory.py"
POLICY_PATH = ROOT / ".github/solo-estate-readonly-policy.json"
WORKFLOW = ROOT / ".github/workflows/solo-estate-readonly-inventory.yml"


def load_controller_without_module_registration():
    spec = importlib.util.spec_from_file_location("solo_estate_readonly", SCRIPT)
    if spec is None or spec.loader is None:
        raise AssertionError("controller import specification unavailable")
    module = importlib.util.module_from_spec(spec)
    # Deliberately do not add the module to sys.modules. The stale predecessor
    # failed at this exact import boundary because dataclass annotations looked
    # up an unregistered module.
    spec.loader.exec_module(module)
    return module


class SoloEstateReadOnlyInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_controller_without_module_registration()
        cls.policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))

    def test_importlib_exec_module_needs_no_sys_modules_registration(self):
        module = load_controller_without_module_registration()
        finding = module.Finding("security", "HIGH", "TEST", "repo", "detail")
        self.assertEqual(finding.to_dict()["kind"], "TEST")

    def test_policy_is_closed_to_provider_mutation(self):
        self.module.validate_policy(self.policy)
        contract = self.policy["read_only_contract"]
        self.assertFalse(contract["provider_mutations_allowed"])
        self.assertEqual(contract["github_api_methods"], ["GET"])
        self.assertEqual(contract["huggingface_mutation_methods_allowed"], [])
        for key, value in contract.items():
            if key.endswith("_allowed") and key != "local_evidence_artifact_allowed":
                self.assertFalse(value, key)

    def test_source_has_no_provider_mutation_primitive(self):
        source = SCRIPT.read_text(encoding="utf-8")
        tree = ast.parse(source)
        forbidden_names = {
            "create_commit",
            "create_repo",
            "delete_repo",
            "upload_file",
            "update_repo_settings",
            "add_space_secret",
            "delete_space_secret",
            "duplicate_space",
            "pause_space",
            "restart_space",
            "request_space_hardware",
            "github_write",
            "upsert_control_issue",
            "ensure_labels",
        }
        observed_calls = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name):
                observed_calls.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                observed_calls.add(node.func.attr)
        self.assertFalse(forbidden_names & observed_calls)
        http_function = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "http_json"
        )
        parameter_names = {
            argument.arg
            for argument in [
                *http_function.args.posonlyargs,
                *http_function.args.args,
                *http_function.args.kwonlyargs,
            ]
        }
        self.assertNotIn("method", parameter_names)
        self.assertNotIn("payload", parameter_names)
        self.assertNotIn("--apply-labels", source)
        self.assertNotIn("--apply-safe-hf-cards", source)
        self.assertNotIn("--update-control-issue", source)

    def test_workflow_has_read_only_permissions_and_no_writer_trigger(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        permissions = workflow.split("permissions:\n", 1)[1].split(
            "\nconcurrency:", 1
        )[0]
        self.assertNotIn(": write", permissions)
        self.assertNotIn("pull_request_target", workflow)
        self.assertNotIn("apply_safe_hf_cards", workflow)
        self.assertNotIn("solo-estate-review-router", workflow)
        self.assertNotIn("issue_comment:", workflow)

    def test_safe_text_redacts_common_provider_tokens(self):
        fine_grained = "github" + "_pat_" + "a" * 24
        classic = "ghp" + "_" + "b" * 26
        hugging_face = "hf" + "_" + "c" * 26
        value = self.module.safe_text(
            "authorization: bearer alpha-secret "
            + fine_grained
            + " "
            + classic
            + " "
            + hugging_face
        )
        self.assertNotIn("alpha-secret", value)
        self.assertNotIn(fine_grained, value)
        self.assertNotIn(classic, value)
        self.assertNotIn(hugging_face, value)

    def test_source_binding_requires_exact_current_protected_sha(self):
        local = "a" * 40
        with mock.patch.object(
            self.module,
            "http_json",
            return_value={"object": {"sha": "b" * 40}},
        ):
            result = self.module.audit_source_binding(
                "szl-holdings/a11oy", "main", "token", local
            )
        self.assertEqual(result["status"], "BLOCKED_SOURCE_DRIFT")
        self.assertFalse(result["exact_match"])

        with mock.patch.object(
            self.module,
            "http_json",
            return_value={"object": {"sha": local}},
        ):
            result = self.module.audit_source_binding(
                "szl-holdings/a11oy", "main", "token", local
            )
        self.assertEqual(result["status"], "PASS")
        self.assertTrue(result["exact_match"])

    def test_github_pagination_exhaustion_is_blocked(self):
        with mock.patch.object(
            self.module,
            "http_json",
            return_value=[{"number": number} for number in range(100)],
        ):
            with self.assertRaises(self.module.ApiFailure):
                self.module.github_pages("/example?per_page=100", "token", max_pages=2)

    def test_security_permission_denial_is_terminal(self):
        denial = self.module.ApiFailure("github", 403, "/security")
        with mock.patch.object(self.module, "github_pages", side_effect=denial), mock.patch.object(
            self.module, "http_json", side_effect=denial
        ):
            report = self.module.audit_security(
                "szl-holdings/a11oy", "main", "token", self.policy
            )
        self.assertEqual(report["status"], "BLOCKED")
        self.assertGreaterEqual(len(report["terminal_findings"]), 5)
        self.assertEqual(report["provider_mutations_performed"], [])
        for surface in report["inventory"].values():
            self.assertEqual(surface["status"], "BLOCKED_PERMISSION_OR_PROVIDER")

    def test_open_high_alert_is_terminal_and_normalized(self):
        def pages(path, _token, **_kwargs):
            if "/dependabot/" in path:
                return [
                    {
                        "number": 12,
                        "state": "open",
                        "html_url": "https://example.invalid/alert/12",
                        "security_advisory": {
                            "severity": "high",
                            "summary": "Affected package",
                        },
                        "dependency": {"package": {"name": "example"}},
                    }
                ]
            return []

        protection = {
            "required_status_checks": {"strict": True},
            "required_pull_request_reviews": {"required_approving_review_count": 0},
            "enforce_admins": {"enabled": True},
        }
        with mock.patch.object(self.module, "github_pages", side_effect=pages), mock.patch.object(
            self.module, "http_json", return_value=protection
        ):
            report = self.module.audit_security(
                "szl-holdings/a11oy", "main", "token", self.policy
            )
        self.assertEqual(report["status"], "BLOCKED")
        alert = report["inventory"]["dependabot"]["alerts"][0]
        self.assertEqual(alert["package"], "example")
        self.assertEqual(alert["severity"], "high")
        self.assertIn(alert, report["terminal_findings"])

    def test_issue_inventory_classifies_without_label_recommendation(self):
        raw = [
            {
                "number": 2,
                "title": "Critical Hugging Face production drift",
                "body": "external blocker and breaking change",
                "labels": [{"name": "existing"}],
            }
        ]
        with mock.patch.object(self.module, "github_pages", return_value=raw):
            report = self.module.audit_issues(
                "szl-holdings/a11oy", "token", self.policy
            )
        self.assertEqual(report["status"], "OBSERVED")
        self.assertEqual(report["counts"], {"open": 1, "p0": 1, "p1": 0, "p2": 0})
        item = report["issues"][0]
        self.assertEqual(item["priority"], "P0")
        self.assertEqual(item["observed_labels"], ["existing"])
        self.assertNotIn("recommended_labels", item)
        self.assertEqual(report["provider_mutations_performed"], [])

    def test_card_read_failure_is_not_reported_as_missing(self):
        card = self.module.audit_card(
            text=None,
            resource_type="model",
            policy=self.policy,
            is_kernel=False,
            read_error="ProviderTimeout",
        )
        self.assertEqual(card["status"], "BLOCKED_READBACK")
        self.assertIsNone(card["present"])
        self.assertNotIn("README.md is missing", card["mobile_risks"])

    def test_huggingface_requires_token_and_bound_org_identity(self):
        missing = self.module.audit_huggingface("SZLHOLDINGS", "", self.policy)
        self.assertEqual(missing["status"], "BLOCKED_CREDENTIAL")

        class UnauthorizedApi:
            def __init__(self, token):
                self.token_was_present = bool(token)

            def whoami(self):
                return {"name": "someone", "orgs": [{"name": "another-org"}]}

        fake_module = types.SimpleNamespace(HfApi=UnauthorizedApi)
        with mock.patch.dict(sys.modules, {"huggingface_hub": fake_module}):
            unbound = self.module.audit_huggingface(
                "SZLHOLDINGS", "test-token", self.policy
            )
        self.assertEqual(unbound["status"], "BLOCKED_ORG_AUTHORITY")
        self.assertEqual(unbound["provider_mutations_performed"], [])

    def test_huggingface_inventory_uses_only_read_surfaces(self):
        sha = "c" * 40

        class Info:
            def __init__(self, identifier, **values):
                self.id = identifier
                self.sha = values.get("sha", sha)
                self.tags = values.get("tags", [])
                self.cardData = values.get("cardData", {})
                self.pipeline_tag = values.get("pipeline_tag")
                self.sdk = values.get("sdk")
                self.private = values.get("private", True)
                self.lastModified = "2026-08-20T00:00:00Z"

        class Collection:
            slug = "SZLHOLDINGS/research"
            title = "Research"
            private = True
            lastModified = "2026-08-20T00:00:00Z"
            items = [object()]

        class Runtime:
            stage = "RUNNING"

        calls = []

        class ReadOnlyApi:
            def __init__(self, token):
                calls.append(("init", bool(token)))

            def whoami(self):
                calls.append(("whoami", None))
                return {"name": "operator", "orgs": [{"name": "SZLHOLDINGS"}]}

            def list_models(self, **kwargs):
                calls.append(("list_models", kwargs))
                return [
                    Info(
                        "SZLHOLDINGS/model",
                        cardData={"license": "apache-2.0"},
                        pipeline_tag="text-generation",
                    )
                ]

            def list_datasets(self, **kwargs):
                calls.append(("list_datasets", kwargs))
                return [
                    Info(
                        "SZLHOLDINGS/dataset",
                        cardData={"license": "apache-2.0"},
                    )
                ]

            def list_spaces(self, **kwargs):
                calls.append(("list_spaces", kwargs))
                return [Info("SZLHOLDINGS/space", sdk="docker")]

            def list_collections(self, **kwargs):
                calls.append(("list_collections", kwargs))
                return [Collection()]

            def get_space_runtime(self, repo_id):
                calls.append(("get_space_runtime", repo_id))
                return Runtime()

        def readme(_repo_id, resource_type, _revision, _token):
            sections = {
                "model": ["Overview", "Status", "Usage", "Limitations"],
                "dataset": ["Overview", "Data", "License", "Limitations"],
                "space": ["Overview", "Status", "Evidence", "Usage"],
            }[resource_type]
            text = "---\ntags: [test]\n---\n# Demo\n"
            text += "\n".join(f"## {section}" for section in sections)
            text += "\n" + "evidence line\n" * 30
            return text, None

        fake_module = types.SimpleNamespace(HfApi=ReadOnlyApi)
        with mock.patch.dict(sys.modules, {"huggingface_hub": fake_module}), mock.patch.object(
            self.module, "load_hf_readme", side_effect=readme
        ):
            report = self.module.audit_huggingface(
                "SZLHOLDINGS", "test-token", self.policy
            )
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(
            report["counts"],
            {
                "models": 1,
                "datasets": 1,
                "spaces": 1,
                "collections": 1,
                "kernels": 0,
                "findings": 0,
                "high_findings": 0,
            },
        )
        self.assertEqual(report["provider_mutations_performed"], [])
        call_names = {name for name, _detail in calls}
        self.assertEqual(
            call_names,
            {
                "init",
                "whoami",
                "list_models",
                "list_datasets",
                "list_spaces",
                "list_collections",
                "get_space_runtime",
            },
        )

    def test_main_writes_local_digest_bound_report_only(self):
        revision = "d" * 40
        source_binding = {
            "status": "PASS",
            "branch": "main",
            "local_revision": revision,
            "protected_revision": revision,
            "exact_match": True,
        }
        security = {
            "status": "PASS",
            "inventory": {
                name: {"status": "OBSERVED", "count": 0, "alerts": []}
                for name in self.module.SECURITY_ENDPOINTS
            },
            "controls": {},
            "terminal_findings": [],
            "provider_mutations_performed": [],
            "secret_values_recorded": False,
        }
        issues = {
            "status": "OBSERVED",
            "counts": {"open": 0, "p0": 0, "p1": 0, "p2": 0},
            "issues": [],
            "provider_mutations_performed": [],
        }
        hf = {
            "status": "PASS",
            "counts": {
                "models": 0,
                "datasets": 0,
                "spaces": 0,
                "collections": 0,
                "kernels": 0,
                "findings": 0,
                "high_findings": 0,
            },
            "resources": {},
            "findings": [],
            "provider_mutations_performed": [],
            "secret_values_recorded": False,
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            argv = [
                str(SCRIPT),
                "--policy",
                str(POLICY_PATH),
                "--repo",
                "szl-holdings/a11oy",
                "--hf-org",
                "SZLHOLDINGS",
                "--output-dir",
                temp_dir,
            ]
            with mock.patch.object(sys, "argv", argv), mock.patch.dict(
                os.environ,
                {"GITHUB_TOKEN": "github-token", "HF_TOKEN": "hf-token"},
                clear=False,
            ), mock.patch.object(
                self.module, "current_revision", return_value=revision
            ), mock.patch.object(
                self.module, "audit_source_binding", return_value=source_binding
            ), mock.patch.object(
                self.module, "audit_security", return_value=security
            ), mock.patch.object(
                self.module, "audit_issues", return_value=issues
            ), mock.patch.object(
                self.module, "audit_huggingface", return_value=hf
            ), contextlib.redirect_stdout(io.StringIO()):
                exit_code = self.module.main()
            self.assertEqual(exit_code, 0)
            output = Path(temp_dir)
            report_path = output / "estate-report.json"
            digest_line = (output / "estate-report.json.sha256").read_text(
                encoding="utf-8"
            )
            expected = hashlib.sha256(report_path.read_bytes()).hexdigest()
            self.assertEqual(digest_line, f"{expected}  estate-report.json\n")
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["provider_mutations_performed"], [])
            self.assertEqual(report["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
