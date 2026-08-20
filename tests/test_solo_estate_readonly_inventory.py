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
        permissions = workflow.split("permissions:\n", 1)[1].split("\nconcurrency:", 1)[
            0
        ]
        self.assertNotIn(": write", permissions)
        self.assertNotIn("pull_request_target", workflow)
        self.assertNotIn("apply_safe_hf_cards", workflow)
        self.assertNotIn("solo-estate-review-router", workflow)
        self.assertNotIn("issue_comment:", workflow)
        inventory_prefix = workflow.split("  inventory:\n", 1)[1]
        job_env = inventory_prefix.split("    steps:\n", 1)[0]
        self.assertNotIn("GH_TOKEN", job_env)
        self.assertNotIn("HF_INVENTORY_READ_TOKEN", job_env)
        self.assertIn(
            "HF_INVENTORY_READ_TOKEN: ${{ secrets.HF_INVENTORY_READ_TOKEN }}",
            workflow,
        )
        self.assertNotIn("secrets.HF_ORG_TOKEN", workflow)
        self.assertNotIn("secrets.HF_TOKEN", workflow)
        controller = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('os.environ.get("HF_INVENTORY_READ_TOKEN")', controller)
        self.assertNotIn('os.environ.get("HF_TOKEN")', controller)

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

    def test_github_search_rejects_incomplete_or_mismatched_results(self):
        incomplete = {
            "total_count": 1,
            "incomplete_results": True,
            "items": [{"number": 1}],
        }
        with mock.patch.object(self.module, "http_json", return_value=incomplete):
            with self.assertRaises(self.module.ApiFailure):
                self.module.github_pages("/search/issues?per_page=100", "token")

        mismatched = {
            "total_count": 2,
            "incomplete_results": False,
            "items": [{"number": 1}],
        }
        with mock.patch.object(self.module, "http_json", return_value=mismatched):
            with self.assertRaises(self.module.ApiFailure):
                self.module.github_pages("/search/issues?per_page=100", "token")

    def test_github_pages_rejects_empty_or_malformed_provider_rows(self):
        for payload in (None, [{"number": 1}, "not-an-object"]):
            with (
                self.subTest(payload=payload),
                mock.patch.object(self.module, "http_json", return_value=payload),
            ):
                with self.assertRaises(self.module.ApiFailure):
                    self.module.github_pages("/example?per_page=100", "token")

    def test_current_revision_rejects_dirty_tracked_tree(self):
        with (
            mock.patch.object(
                self.module.subprocess,
                "check_output",
                return_value="a" * 40 + "\n",
            ),
            mock.patch.object(self.module, "tracked_tree_is_clean", return_value=False),
        ):
            self.assertIsNone(self.module.current_revision())

    def test_effective_branch_rules_require_named_checks_and_approval(self):
        required_workflows = self.policy["security"]["required_workflows"]
        rules = [
            {
                "type": "required_status_checks",
                "parameters": {
                    "strict_required_status_checks_policy": True,
                    "required_status_checks": [{"context": "Tests"}],
                },
                "ruleset_id": 7,
                "ruleset_source_type": "Organization",
                "ruleset_source": "szl-holdings",
            },
            {
                "type": "pull_request",
                "parameters": {"required_approving_review_count": 1},
                "ruleset_id": 7,
                "ruleset_source_type": "Organization",
                "ruleset_source": "szl-holdings",
            },
            {
                "type": "workflows",
                "parameters": {
                    "do_not_enforce_on_create": False,
                    "workflows": [dict(required_workflows[0])],
                },
                "ruleset_id": 7,
                "ruleset_source_type": "Organization",
                "ruleset_source": "szl-holdings",
            },
        ]
        with mock.patch.object(self.module, "github_pages", return_value=rules):
            observed = self.module.audit_effective_branch_rules(
                "szl-holdings/a11oy", "main", "token", required_workflows
            )
        self.assertTrue(observed["required_status_checks"])
        self.assertTrue(observed["required_pull_request_reviews"])
        self.assertTrue(observed["required_workflows"])
        self.assertTrue(observed["workflow_rules_enforce_on_create"])
        self.assertEqual(
            observed["required_workflow_identities"], required_workflows
        )
        self.assertEqual(observed["required_approving_review_count"], 1)
        self.assertEqual(observed["bypass_visibility"], "UNAVAILABLE")
        self.assertEqual(observed["administrator_enforcement"], "NOT_INFERRED")

        weak_strict_rules = [
            {
                **rules[0],
                "parameters": {
                    **rules[0]["parameters"],
                    "strict_required_status_checks_policy": False,
                },
            },
            *rules[1:],
        ]
        with mock.patch.object(
            self.module, "github_pages", return_value=weak_strict_rules
        ):
            weak_strict = self.module.audit_effective_branch_rules(
                "szl-holdings/a11oy", "main", "token", required_workflows
            )
        self.assertFalse(weak_strict["required_status_checks"])
        self.assertFalse(weak_strict["strict_required_status_checks_policy"])

        empty_rules = [
            {
                "type": "required_status_checks",
                "parameters": {"required_status_checks": []},
            },
            {
                "type": "pull_request",
                "parameters": {"required_approving_review_count": 0},
            },
        ]
        with mock.patch.object(self.module, "github_pages", return_value=empty_rules):
            missing = self.module.audit_effective_branch_rules(
                "szl-holdings/a11oy", "main", "token", required_workflows
            )
        self.assertFalse(missing["required_status_checks"])
        self.assertFalse(missing["required_pull_request_reviews"])
        self.assertFalse(missing["required_workflows"])

        wrong_identity = [
            *rules[:-1],
            {
                **rules[-1],
                "parameters": {
                    "do_not_enforce_on_create": False,
                    "workflows": [
                        {
                            "repository_id": required_workflows[0]["repository_id"],
                            "path": ".github/workflows/different.yml",
                        }
                    ],
                },
            },
        ]
        with mock.patch.object(
            self.module, "github_pages", return_value=wrong_identity
        ):
            observed_wrong = self.module.audit_effective_branch_rules(
                "szl-holdings/a11oy", "main", "token", required_workflows
            )
        self.assertFalse(observed_wrong["required_workflows"])

        not_enforced_on_create = [
            *rules[:-1],
            {
                **rules[-1],
                "parameters": {
                    **rules[-1]["parameters"],
                    "do_not_enforce_on_create": True,
                },
            },
        ]
        with mock.patch.object(
            self.module, "github_pages", return_value=not_enforced_on_create
        ):
            observed_weak = self.module.audit_effective_branch_rules(
                "szl-holdings/a11oy", "main", "token", required_workflows
            )
        self.assertFalse(observed_weak["required_workflows"])

        unrelated_weak_rule = {
            **rules[-1],
            "parameters": {
                "do_not_enforce_on_create": True,
                "workflows": [
                    {
                        "repository_id": required_workflows[0]["repository_id"],
                        "path": ".github/workflows/unrelated.yml",
                    }
                ],
            },
        }
        with mock.patch.object(
            self.module,
            "github_pages",
            return_value=[*rules, unrelated_weak_rule],
        ):
            observed_with_unrelated_weak_rule = (
                self.module.audit_effective_branch_rules(
                    "szl-holdings/a11oy", "main", "token", required_workflows
                )
            )
        self.assertTrue(observed_with_unrelated_weak_rule["required_workflows"])
        self.assertTrue(
            observed_with_unrelated_weak_rule[
                "workflow_rules_enforce_on_create"
            ]
        )

    def test_security_permission_denial_is_terminal(self):
        denial = self.module.ApiFailure("github", 403, "/security")
        with (
            mock.patch.object(self.module, "github_pages", side_effect=denial),
            mock.patch.object(self.module, "http_json", side_effect=denial),
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
            if "/rules/branches/" in path:
                return [
                    {
                        "type": "required_status_checks",
                        "parameters": {
                            "strict_required_status_checks_policy": True,
                            "required_status_checks": [{"context": "Tests"}]
                        },
                    },
                    {
                        "type": "pull_request",
                        "parameters": {"required_approving_review_count": 1},
                    },
                ]
            return []

        with mock.patch.object(self.module, "github_pages", side_effect=pages):
            report = self.module.audit_security(
                "szl-holdings/a11oy", "main", "token", self.policy
            )
        self.assertEqual(report["status"], "BLOCKED")
        alert = report["inventory"]["dependabot"]["alerts"][0]
        self.assertEqual(alert["package"], "example")
        self.assertEqual(alert["severity"], "high")
        self.assertIn(alert, report["terminal_findings"])

    def test_unknown_alert_severity_and_missing_effective_rules_are_terminal(self):
        def pages(path, _token, **_kwargs):
            if "/dependabot/" in path:
                return [
                    {
                        "number": 14,
                        "state": "open",
                        "security_advisory": {"summary": "Unclassified alert"},
                        "dependency": {"package": {"name": "example"}},
                    }
                ]
            return []

        with mock.patch.object(self.module, "github_pages", side_effect=pages):
            report = self.module.audit_security(
                "szl-holdings/a11oy", "main", "token", self.policy
            )
        self.assertEqual(report["status"], "BLOCKED")
        kinds = [item.get("kind") for item in report["terminal_findings"]]
        self.assertIn("dependabot", kinds)
        missing_controls = {
            item.get("summary")
            for item in report["terminal_findings"]
            if item.get("kind") == "protected_branch_control"
        }
        self.assertEqual(
            missing_controls,
            {
                "required_status_checks",
                "required_pull_request_reviews",
                "required_workflows",
            },
        )

    def test_policy_validation_rejects_fail_closed_weakening(self):
        mutations = {
            "terminal severities": lambda policy: policy["security"].update(
                {"terminal_security_severities": ["critical"]}
            ),
            "secret terminality": lambda policy: policy["security"].update(
                {"secret_scanning_is_terminal": False}
            ),
            "required control": lambda policy: policy["security"][
                "required_repository_controls"
            ].pop("codeowners"),
            "required workflow": lambda policy: policy["security"].update(
                {"required_workflows": []}
            ),
            "required workflow identity": lambda policy: policy["security"][
                "required_workflows"
            ][0].update({"path": ".github/workflows/different.yml"}),
            "private inventory": lambda policy: policy["huggingface"].update(
                {"private_inventory_token_required": False}
            ),
            "org binding": lambda policy: policy["huggingface"].update(
                {"organization_membership_readback_required": False}
            ),
            "p0 terms": lambda policy: policy["issue_inventory"]["classifiers"].update(
                {"p0": ["critical"]}
            ),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                candidate = json.loads(json.dumps(self.policy))
                mutate(candidate)
                with self.assertRaises(ValueError):
                    self.module.validate_policy(candidate)

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

    def test_issue_inventory_honors_p0_label_and_full_body(self):
        label_issue = {
            "number": 3,
            "title": "Routine task",
            "body": "No keyword here",
            "labels": [{"name": "priority/P0"}],
        }
        body_issue = {
            "number": 4,
            "title": "Long report",
            "body": "x" * 5000 + " credential leak",
            "labels": [],
        }
        with mock.patch.object(
            self.module, "github_pages", return_value=[label_issue, body_issue]
        ):
            report = self.module.audit_issues(
                "szl-holdings/a11oy", "token", self.policy
            )
        self.assertEqual(report["counts"]["p0"], 2)
        self.assertEqual([item["priority"] for item in report["issues"]], ["P0", "P0"])

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

    def test_card_sections_match_complete_normalized_headings(self):
        text = (
            "---\ntags: [test]\n---\n"
            "# Overview\n## Metadata\n## License\n## Limitations\n"
            + "evidence line\n" * 30
        )
        card = self.module.audit_card(
            text=text,
            resource_type="dataset",
            policy=self.policy,
            is_kernel=False,
        )
        self.assertEqual(card["status"], "POLISH_REQUIRED")
        self.assertIn("data", card["missing_sections"])
        self.assertNotIn("license", card["missing_sections"])

    def test_huggingface_requires_token_and_bound_org_identity(self):
        missing = self.module.audit_huggingface("SZLHOLDINGS", "", self.policy)
        self.assertEqual(missing["status"], "BLOCKED_CREDENTIAL")

        class UnauthorizedApi:
            def __init__(self, token):
                self.token_was_present = bool(token)

            def whoami(self):
                return {
                    "name": "someone",
                    "orgs": [{"name": "another-org"}],
                    "auth": {"accessToken": {"role": "read"}},
                }

        fake_module = types.SimpleNamespace(HfApi=UnauthorizedApi)
        with mock.patch.dict(sys.modules, {"huggingface_hub": fake_module}):
            unbound = self.module.audit_huggingface(
                "SZLHOLDINGS", "test-token", self.policy
            )
        self.assertEqual(unbound["status"], "BLOCKED_ORG_AUTHORITY")
        self.assertEqual(unbound["provider_mutations_performed"], [])

    def test_huggingface_rejects_write_or_unscoped_tokens(self):
        class ScopedApi:
            role = "write"

            def __init__(self, token):
                self.token = token

            def whoami(self):
                return {
                    "name": "operator",
                    "orgs": [{"name": "SZLHOLDINGS"}],
                    "auth": {"accessToken": {"role": self.role}},
                }

        fake_module = types.SimpleNamespace(HfApi=ScopedApi)
        for role in ("write", "fineGrained", None):
            with (
                self.subTest(role=role),
                mock.patch.dict(sys.modules, {"huggingface_hub": fake_module}),
            ):
                ScopedApi.role = role
                report = self.module.audit_huggingface(
                    "SZLHOLDINGS", "test-token", self.policy
                )
            self.assertEqual(report["status"], "BLOCKED_TOKEN_SCOPE")

    def test_huggingface_readme_cache_is_temporary(self):
        observed_cache_dirs = []

        def download(**kwargs):
            cache_dir = Path(kwargs["cache_dir"])
            observed_cache_dirs.append(cache_dir)
            path = cache_dir / "README.md"
            path.write_text("# private card", encoding="utf-8")
            return str(path)

        fake_module = types.SimpleNamespace(hf_hub_download=download)
        with mock.patch.dict(sys.modules, {"huggingface_hub": fake_module}):
            text, error = self.module.load_hf_readme(
                "SZLHOLDINGS/private", "model", "a" * 40, "read-token"
            )
        self.assertEqual(text, "# private card")
        self.assertIsNone(error)
        self.assertEqual(len(observed_cache_dirs), 1)
        self.assertFalse(observed_cache_dirs[0].exists())

    def test_huggingface_inventory_uses_only_read_surfaces(self):
        sha = "c" * 40

        class Info:
            def __init__(self, identifier, **values):
                self.id = identifier
                self.sha = values.get("sha", sha)
                self.tags = values.get("tags", [])
                self.card_data = values.get("card_data", {})
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
                return {
                    "name": "operator",
                    "orgs": [{"name": "SZLHOLDINGS"}],
                    "auth": {"accessToken": {"role": "read"}},
                }

            def list_models(self, **kwargs):
                calls.append(("list_models", kwargs))
                return [
                    Info(
                        "SZLHOLDINGS/model",
                        card_data={"license": "apache-2.0"},
                        pipeline_tag="text-generation",
                    )
                ]

            def list_datasets(self, **kwargs):
                calls.append(("list_datasets", kwargs))
                return [
                    Info(
                        "SZLHOLDINGS/dataset",
                        card_data={"license": "apache-2.0"},
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
        with (
            mock.patch.dict(sys.modules, {"huggingface_hub": fake_module}),
            mock.patch.object(self.module, "load_hf_readme", side_effect=readme),
        ):
            report = self.module.audit_huggingface(
                "SZLHOLDINGS", "test-token", self.policy
            )
            del Runtime.stage
            missing_stage_report = self.module.audit_huggingface(
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
        self.assertIn(
            "SPACE_RUNTIME_UNOBSERVED",
            [finding["kind"] for finding in missing_stage_report["findings"]],
        )
        self.assertFalse(
            self.module.provider_readbacks_complete(
                {
                    "source_binding": {"status": "PASS"},
                    "github_security": {
                        "inventory": {
                            name: {"status": "OBSERVED"}
                            for name in self.module.SECURITY_ENDPOINTS
                        },
                        "controls": {"protected_branch": {"status": "OBSERVED"}},
                    },
                    "issues": {"status": "OBSERVED"},
                    "huggingface": missing_stage_report,
                }
            )
        )
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

    def test_huggingface_collection_without_identifier_is_terminal(self):
        class Collection:
            title = "Research"
            private = True
            lastModified = "2026-08-20T00:00:00Z"
            items = (object(),)

        class ReadOnlyApi:
            def __init__(self, token):
                self.token = token

            def whoami(self):
                return {
                    "name": "operator",
                    "orgs": [{"name": "SZLHOLDINGS"}],
                    "auth": {"accessToken": {"role": "read"}},
                }

            def list_models(self, **_kwargs):
                return []

            def list_datasets(self, **_kwargs):
                return []

            def list_spaces(self, **_kwargs):
                return []

            def list_collections(self, **_kwargs):
                return [Collection()]

        fake_module = types.SimpleNamespace(HfApi=ReadOnlyApi)
        with mock.patch.dict(sys.modules, {"huggingface_hub": fake_module}):
            report = self.module.audit_huggingface(
                "SZLHOLDINGS", "test-token", self.policy
            )
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["resources"]["collections"][0]["id"], None)
        self.assertIn(
            "COLLECTION_ID_MISSING",
            [finding["kind"] for finding in report["findings"]],
        )
        self.assertEqual(report["provider_mutations_performed"], [])

    def test_source_binding_closes_over_start_and_end(self):
        revision = "d" * 40
        start = {
            "status": "PASS",
            "branch": "main",
            "local_revision": revision,
            "protected_revision": revision,
            "exact_match": True,
        }
        end = {
            **start,
            "protected_revision": "e" * 40,
            "status": "BLOCKED_SOURCE_DRIFT",
        }
        closed = self.module.close_source_binding(start, end)
        self.assertEqual(closed["status"], "BLOCKED_SOURCE_DRIFT")
        self.assertFalse(closed["exact_match"])
        self.assertEqual(closed["start"], start)
        self.assertEqual(closed["end"], end)

    def test_provider_truth_label_requires_complete_readbacks(self):
        report = {
            "source_binding": {"status": "PASS"},
            "github_security": {
                "inventory": {
                    name: {"status": "OBSERVED"}
                    for name in self.module.SECURITY_ENDPOINTS
                },
                "controls": {"protected_branch": {"status": "OBSERVED"}},
            },
            "issues": {"status": "OBSERVED"},
            "huggingface": {
                "identity": {"status": "AUTHORIZED", "token_role": "read"},
                "counts": {
                    "models": 1,
                    "datasets": 0,
                    "spaces": 0,
                    "collections": 0,
                    "kernels": 0,
                    "findings": 1,
                    "high_findings": 1,
                },
                "findings": [
                    {
                        "kind": "CARD_READBACK_UNAVAILABLE",
                        "resource": "SZLHOLDINGS/private",
                    }
                ],
            },
        }
        for incomplete_kind in (
            "CARD_READBACK_UNAVAILABLE",
            "COLLECTION_ID_MISSING",
        ):
            with self.subTest(incomplete_kind=incomplete_kind):
                report["huggingface"]["findings"][0]["kind"] = incomplete_kind
                self.assertFalse(self.module.provider_readbacks_complete(report))

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
            "controls": {"protected_branch": {"status": "OBSERVED"}},
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
            "identity": {"status": "AUTHORIZED", "token_role": "read"},
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
        binding_audit = mock.Mock(return_value=source_binding)
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
            with (
                mock.patch.object(sys, "argv", argv),
                mock.patch.dict(
                    os.environ,
                    {
                        "GITHUB_TOKEN": "github-token",
                        "HF_INVENTORY_READ_TOKEN": "hf-token",
                    },
                    clear=False,
                ),
                mock.patch.object(
                    self.module, "current_revision", return_value=revision
                ),
                mock.patch.object(
                    self.module, "audit_source_binding", new=binding_audit
                ),
                mock.patch.object(self.module, "audit_security", return_value=security),
                mock.patch.object(self.module, "audit_issues", return_value=issues),
                mock.patch.object(self.module, "audit_huggingface", return_value=hf),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                exit_code = self.module.main()
            self.assertEqual(exit_code, 0)
            self.assertEqual(binding_audit.call_count, 2)
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
            self.assertEqual(
                report["truth_boundary"]["live_provider_inventory"],
                "MEASURED",
            )


if __name__ == "__main__":
    unittest.main()
