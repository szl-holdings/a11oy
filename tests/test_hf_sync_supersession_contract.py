from __future__ import annotations

import re
import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "hf-sync.yml"
HELPER = ROOT / "scripts" / "hf_exact_main_ownership.py"
TARGET_JOB = "Publish and live-verify six domain-native flagship Spaces"


class WorkflowContractError(AssertionError):
    pass


def workflow_document(source: str) -> dict:
    """Read this workflow's safe YAML subset, rejecting ambiguous mappings.

    This is deliberately not a general YAML loader. Aliases, tags, flow maps,
    tabs, duplicate keys and unsupported indentation require explicit review.
    Block shell bodies are data and cannot masquerade as mapping keys.
    """
    lines = source.splitlines()
    if any("\t" in line[:len(line) - len(line.lstrip())] for line in lines):
        raise WorkflowContractError("unsupported indentation")

    def skip(index):
        while index < len(lines) and (not lines[index].strip() or lines[index].lstrip().startswith("#")):
            index += 1
        return index

    def scalar(raw):
        raw = re.sub(r"\s+#.*$", "", raw).strip()
        if raw == "{}":
            return {}
        if raw.startswith(("&", "*", "!")) or (raw.startswith("{") and not raw.startswith("${{")) or raw in ("---", "..."):
            raise WorkflowContractError("unsupported YAML value")
        if raw.startswith("["):
            if not raw.endswith("]"):
                raise WorkflowContractError("invalid flow sequence")
            return [scalar(value) for value in raw[1:-1].split(",") if value.strip()]
        if raw.startswith(("'", '"')):
            if len(raw) < 2 or raw[-1] != raw[0]:
                raise WorkflowContractError("invalid quoted scalar")
            return raw[1:-1]
        if raw in ("true", "false"):
            return raw == "true"
        return raw

    def entry(text):
        match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_-]*):(?:\s+(.*))?", text)
        if match is None:
            raise WorkflowContractError("unsupported mapping entry")
        return match.group(1), match.group(2) or ""

    def value(raw, index, level):
        if raw in ("|", ">-", ">", "|-"):
            body = []
            while index < len(lines):
                if lines[index].strip() and indent(lines[index]) <= level:
                    break
                body.append(lines[index][level + 2:])
                index += 1
            return "\n".join(body), index
        if raw:
            return scalar(raw), index
        index = skip(index)
        if index == len(lines) or indent(lines[index]) <= level:
            return {}, index
        return block(index, indent(lines[index]))

    def mapping(index, level, initial=None):
        result = {} if initial is None else initial
        while True:
            index = skip(index)
            if index == len(lines) or indent(lines[index]) < level:
                return result, index
            if indent(lines[index]) != level or lines[index].lstrip().startswith("- "):
                raise WorkflowContractError("unsupported mapping indentation")
            key, raw = entry(lines[index].strip())
            if key in result:
                raise WorkflowContractError("duplicate mapping key: " + key)
            result[key], index = value(raw, index + 1, level)

    def block(index, level):
        if not lines[index].lstrip().startswith("- "):
            return mapping(index, level)
        result = []
        while True:
            index = skip(index)
            if index == len(lines) or indent(lines[index]) < level:
                return result, index
            if indent(lines[index]) != level or not lines[index].lstrip().startswith("- "):
                raise WorkflowContractError("unsupported sequence indentation")
            key, raw = entry(lines[index].strip()[2:])
            item_value, index = value(raw, index + 1, level + 2)
            item, index = mapping(index, level + 2, {key: item_value})
            result.append(item)

    start = skip(0)
    if start == len(lines) or indent(lines[start]) != 0:
        raise WorkflowContractError("missing root mapping")
    result, end = block(start, 0)
    if skip(end) != len(lines) or type(result) is not dict:
        raise WorkflowContractError("incomplete workflow")
    return result


def assert_manual_dependency_graph(source: str) -> dict:
    jobs = workflow_document(source).get("jobs", {})
    dependencies = {
        "source-admission": [],
        "manual-prerequisites": ["source-admission"],
        "resume-paused-space": ["source-admission", "manual-prerequisites"],
        "deploy": ["source-admission", "manual-prerequisites", "resume-paused-space"],
        "runtime-config": ["manual-prerequisites", "deploy"],
        "publish-vertical-flagships": ["manual-prerequisites", "deploy"],
        "publish-finance-projection": ["manual-prerequisites", "relock"],
        "readiness-verdict": ["manual-prerequisites", "runtime-config"],
        "relock": ["manual-prerequisites", "runtime-config", "readiness-verdict"],
        "post-deployment-parity": ["relock"],
        "terminal-source-authorization": [
            "post-deployment-parity",
            "publish-vertical-flagships",
            "publish-finance-projection",
        ],
    }
    if set(jobs) != set(dependencies):
        raise WorkflowContractError("job set requires review")
    conditions = {
        "manual-prerequisites": "${{ needs.source-admission.outputs.publish == 'true' }}",
        "resume-paused-space": "${{ needs.source-admission.outputs.publish == 'true' && needs.manual-prerequisites.result == 'success' }}",
        "deploy": "${{ needs.source-admission.outputs.publish == 'true' && needs.manual-prerequisites.result == 'success' && needs.resume-paused-space.result == 'success' }}",
        "publish-vertical-flagships": "${{ needs.manual-prerequisites.result == 'success' && github.event_name == 'workflow_dispatch' && inputs.publish_vertical_flagships }}",
        "publish-finance-projection": "${{ needs.manual-prerequisites.result == 'success' && (github.event_name == 'push' || !inputs.publish_vertical_flagships) }}",
        "terminal-source-authorization": "${{ always() && needs.post-deployment-parity.result == 'success' && (needs.publish-vertical-flagships.result == 'success' || needs.publish-vertical-flagships.result == 'skipped') && (needs.publish-finance-projection.result == 'success' || needs.publish-finance-projection.result == 'skipped') }}",
    }
    for name, required in dependencies.items():
        job = jobs[name]
        actual = job.get("needs", [])
        actual = [actual] if isinstance(actual, str) else actual
        if actual != required:
            raise WorkflowContractError("dependency gate: " + name)
        if job.get("if") != conditions.get(name):
            raise WorkflowContractError("condition gate: " + name)
        if "continue-on-error" in job:
            raise WorkflowContractError("job failure bypass: " + name)
        ids = [step["id"] for step in job.get("steps", []) if "id" in step]
        if len(ids) != len(set(ids)):
            raise WorkflowContractError("duplicate step id: " + name)
        for step in job.get("steps", []):
            if "continue-on-error" in step:
                raise WorkflowContractError("step failure bypass: " + name)
    for name in jobs:
        if name in ("source-admission", "manual-prerequisites"):
            continue
        pending, ancestors = list(dependencies[name]), set()
        while pending:
            parent = pending.pop()
            if parent in ancestors:
                continue
            ancestors.add(parent)
            pending.extend(dependencies[parent])
        if not {"source-admission", "manual-prerequisites"}.issubset(ancestors):
            raise WorkflowContractError("provider effects lack admission: " + name)
    return jobs


def indent(line: str) -> int:
    return len(line) - len(line.lstrip())


def job_block(source: str, name: str) -> str:
    lines = source.splitlines()
    pattern = re.compile(rf"^\s*name:\s*[\"']?{re.escape(name)}[\"']?\s*$")
    matches = [index for index, line in enumerate(lines) if pattern.fullmatch(line)]
    if len(matches) != 1:
        raise AssertionError(f"expected one job named {name!r}, found {len(matches)}")
    name_index = matches[0]
    name_indent = indent(lines[name_index])
    key_pattern = re.compile(r"^[A-Za-z0-9_-]+:\s*$")
    start = None
    for index in range(name_index - 1, -1, -1):
        if indent(lines[index]) < name_indent and key_pattern.fullmatch(lines[index].strip()):
            start = index
            break
    if start is None:
        raise AssertionError("target job key was not found")
    job_indent = indent(lines[start])
    end = len(lines)
    for index in range(start + 1, len(lines)):
        stripped = lines[index].strip()
        if (
            stripped
            and not stripped.startswith("#")
            and indent(lines[index]) == job_indent
            and key_pattern.fullmatch(stripped)
        ):
            end = index
            break
    return "\n".join(lines[start:end])


def step_block(job: str, name: str) -> str:
    lines = job.splitlines()
    pattern = re.compile(rf"^(\s*)- name:\s*[\"']?{re.escape(name)}[\"']?\s*$")
    matches = []
    for index, line in enumerate(lines):
        match = pattern.fullmatch(line)
        if match:
            matches.append((index, len(match.group(1))))
    if len(matches) != 1:
        raise AssertionError(f"expected one step named {name!r}, found {len(matches)}")
    start, step_indent = matches[0]
    end = len(lines)
    for index in range(start + 1, len(lines)):
        stripped = lines[index].strip()
        if not stripped or stripped.startswith("#"):
            continue
        current = indent(lines[index])
        if current < step_indent or (
            current == step_indent and lines[index].lstrip().startswith("- name:")
        ):
            end = index
            break
    return "\n".join(lines[start:end])


class HFSyncSupersessionContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")
        cls.job = job_block(cls.workflow, TARGET_JOB)

    def test_exact_main_controller_and_receipt_are_mandatory(self) -> None:
        ownership = step_block(self.job, "Assert the workflow owns exact protected main")
        receipt = step_block(self.job, "Upload exact-main ownership receipt")
        self.assertIn("id: exact_main_owner", ownership)
        self.assertIn("scripts/hf_exact_main_ownership.py", ownership)
        self.assertIn('--repository "$GITHUB_REPOSITORY"', ownership)
        self.assertIn('--expected-sha "$GITHUB_SHA"', ownership)
        self.assertIn('--github-output "$GITHUB_OUTPUT"', ownership)
        self.assertIn("GITHUB_TOKEN: ${{ github.token }}", ownership)
        self.assertNotIn("continue-on-error", ownership)
        self.assertIn("if: always()", receipt)
        self.assertRegex(receipt, r"uses: actions/upload-artifact@[0-9a-f]{40}")
        self.assertIn("${{ runner.temp }}/hf-main-ownership.json", receipt)
        self.assertIn("if-no-files-found: error", receipt)

    def test_every_publication_capable_step_requires_owned_source(self) -> None:
        gate = "steps.exact_main_owner.outputs.publish == 'true'"
        for name in (
            "Set up Python",
            "Install pinned vertical publisher",
            "Publish and verify the v4 vertical estate",
        ):
            self.assertIn(gate, step_block(self.job, name), name)
        publication_receipt = step_block(
            self.job, "Upload immutable vertical publication receipt"
        )
        self.assertIn(gate, publication_receipt)
        self.assertIn("always()", publication_receipt)

    def test_helper_requires_ancestry_and_has_no_write_authority(self) -> None:
        helper = HELPER.read_text(encoding="utf-8")
        self.assertIn("prove_ancestor", helper)
        self.assertIn("/compare/", helper)
        self.assertIn("SUPERSEDED_BY_NEWER_MAIN", helper)
        self.assertIn('"status": "ERROR"', helper)
        self.assertIn('"external_writes_performed": False', helper)
        self.assertIn('method="GET"', helper)
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            self.assertNotIn(f'method="{method}"', helper)

    def test_both_initial_provider_jobs_require_successful_owned_admission(self) -> None:
        jobs = assert_manual_dependency_graph(self.workflow)
        for name in (
            "Resume the canonical Space without changing its allocation",
            "Deploy, source-bind, and attest exact surface",
        ):
            with self.subTest(job=name):
                job = job_block(self.workflow, name)
                self.assertIn("needs.source-admission.outputs.publish == 'true'", job)
                self.assertIn("needs.manual-prerequisites.result == 'success'", job)
                self.assertNotRegex(job, r"(?m)^    if:.*always\(")
                self.assertNotIn("continue-on-error", job)
        deploy = job_block(self.workflow, "Deploy, source-bind, and attest exact surface")
        self.assertIn("require-default-branch-tip: true", deploy)
        self.assertIn("ref: ${{ github.sha }}", deploy)
        self.assertIn("cancel-in-progress: false", self.workflow)
        self.assertIn("resume-paused-space", jobs["deploy"]["needs"])

    def test_every_effect_job_requires_the_complete_dependency_graph(self) -> None:
        assert_manual_dependency_graph(self.workflow)

    def test_deleted_or_bypassed_dependency_gates_are_rejected(self) -> None:
        mutations = (
            ("    needs: [source-admission, manual-prerequisites]\n", "    needs: source-admission\n", "dependency gate: resume-paused-space"),
            ("    needs: [source-admission, manual-prerequisites, resume-paused-space]\n", "    needs: [source-admission, manual-prerequisites]\n", "dependency gate: deploy"),
            ("    needs: [manual-prerequisites, runtime-config]\n", "    needs: runtime-config\n", "dependency gate: readiness-verdict"),
            ("    needs: [manual-prerequisites, relock]\n", "    needs: manual-prerequisites\n", "dependency gate: publish-finance-projection"),
            ("    if: ${{ needs.source-admission.outputs.publish == 'true' && needs.manual-prerequisites.result == 'success' }}\n", "    if: always()\n", "condition gate: resume-paused-space"),
            ("    if: ${{ needs.source-admission.outputs.publish == 'true' && needs.manual-prerequisites.result == 'success' && needs.resume-paused-space.result == 'success' }}\n", "", "condition gate: deploy"),
            ("    needs: [manual-prerequisites, deploy]\n", "    needs: deploy\n", "dependency gate: runtime-config"),
            ("    if: ${{ needs.manual-prerequisites.result == 'success' && github.event_name == 'workflow_dispatch' && inputs.publish_vertical_flagships }}\n", "    if: ${{ needs.manual-prerequisites.result == 'success' || inputs.publish_vertical_flagships }}\n", "condition gate: publish-vertical-flagships"),
            ("    needs: [manual-prerequisites, runtime-config, readiness-verdict]\n", "    needs: [runtime-config, readiness-verdict]\n", "dependency gate: relock"),
            ("    needs: [post-deployment-parity, publish-vertical-flagships, publish-finance-projection]\n", "    needs: post-deployment-parity\n", "dependency gate: terminal-source-authorization"),
        )
        for original, replacement, diagnostic in mutations:
            with self.subTest(diagnostic=diagnostic):
                self.assertIn(original, self.workflow)
                changed = self.workflow.replace(original, replacement, 1)
                with self.assertRaisesRegex(WorkflowContractError, re.escape(diagnostic)):
                    assert_manual_dependency_graph(changed)

    def test_duplicate_jobs_properties_and_step_ids_are_rejected(self) -> None:
        mutations = (
            ("  manual-prerequisites:\n", "  manual-prerequisites: {}\n  manual-prerequisites:\n", "duplicate mapping key: manual-prerequisites"),
            ("    needs: source-admission\n", "    needs: source-admission\n    needs: deploy\n", "duplicate mapping key: needs"),
            ("    if: ${{ needs.source-admission.outputs.publish == 'true' }}\n", "    if: ${{ needs.source-admission.outputs.publish == 'true' }}\n    if: always()\n", "duplicate mapping key: if"),
            ("        id: owner\n", "        id: owner\n        id: forged\n", "duplicate mapping key: id"),
            ("      - name: Retain the source admission decision\n", "      - name: Retain the source admission decision\n        id: owner\n", "duplicate step id: source-admission"),
        )
        for original, replacement, diagnostic in mutations:
            with self.subTest(diagnostic=diagnostic):
                changed = self.workflow.replace(original, replacement, 1)
                with self.assertRaisesRegex(WorkflowContractError, re.escape(diagnostic)):
                    assert_manual_dependency_graph(changed)

    def test_new_jobs_missing_manual_job_and_failure_bypasses_require_review(self) -> None:
        cases = (
            (self.workflow + "\n  unreviewed-job:\n    runs-on: ubuntu-latest\n", "job set requires review"),
            (self.workflow.replace("  manual-prerequisites:\n", "  removed-prerequisites:\n", 1), "job set requires review"),
            (self.workflow.replace("  deploy:\n", "  deploy:\n    continue-on-error: true\n", 1), "job failure bypass: deploy"),
            (self.workflow.replace("      - name: Require main and classify current source ownership\n", "      - name: Require main and classify current source ownership\n        continue-on-error: true\n", 1), "step failure bypass: source-admission"),
        )
        for changed, diagnostic in cases:
            with self.subTest(diagnostic=diagnostic), self.assertRaisesRegex(WorkflowContractError, re.escape(diagnostic)):
                assert_manual_dependency_graph(changed)

    def test_admission_is_read_only_source_bound_and_retained(self) -> None:
        job = job_block(self.workflow, "Admit the queued source before provider mutation")
        self.assertIn("publish: ${{ steps.owner.outputs.publish }}", job)
        self.assertIn("contents: read", job)
        self.assertNotIn("secrets.", job)
        self.assertNotIn("HF_TOKEN", job)
        self.assertIn("ref: ${{ github.sha }}", job)
        step = step_block(job, "Require main and classify current source ownership")
        self.assertIn('test "$GITHUB_REF" = refs/heads/main', step)
        self.assertIn("scripts/hf_exact_main_ownership.py", step)
        self.assertIn('--expected-sha "$GITHUB_SHA"', step)
        self.assertNotIn("continue-on-error", job)
        receipt = step_block(job, "Retain the source admission decision")
        self.assertIn("if: always()", receipt)
        self.assertIn("if-no-files-found: error", receipt)
        self.assertIn("canonical-source-admission-${{ github.run_id }}-${{ github.run_attempt }}", receipt)

    def test_post_deploy_relock_rejects_a_source_that_became_stale(self) -> None:
        job = job_block(
            self.workflow,
            "Prove exact live source, runtime, routes, and singleton state",
        )
        owner = step_block(
            job,
            "Re-admit exact current main after live verification",
        )
        evidence = step_block(job, "Upload immutable relock evidence")
        enforce = step_block(job, "Enforce exact live state")
        self.assertIn("id: post_deploy_owner", owner)
        self.assertIn("scripts/hf_exact_main_ownership.py", owner)
        self.assertIn('--expected-sha "$GITHUB_SHA"', owner)
        self.assertIn("GITHUB_TOKEN: ${{ github.token }}", owner)
        self.assertIn("post-deploy-source-admission.json", evidence)
        owner_output = "steps.post_deploy_owner.outputs.publish"
        self.assertIn(owner_output, enforce)
        self.assertIn("CURRENT_MAIN:-false", enforce)
        self.assertLess(job.index("Evaluate the canonical application contract"), job.index(owner))
        self.assertLess(job.index(owner), job.index(enforce))

    def test_terminal_authorization_follows_all_publication_proofs(self) -> None:
        jobs = assert_manual_dependency_graph(self.workflow)
        terminal = job_block(
            self.workflow,
            "Re-authorize exact protected main after all publication proofs",
        )
        owner = step_block(
            terminal,
            "Re-authorize exact protected main after awaited parity",
        )
        receipt = step_block(terminal, "Retain terminal source authorization")
        enforce = step_block(
            terminal,
            "Re-read and enforce exact protected-main ownership as the final step",
        )
        self.assertEqual(
            jobs["terminal-source-authorization"]["needs"],
            [
                "post-deployment-parity",
                "publish-vertical-flagships",
                "publish-finance-projection",
            ],
        )
        self.assertIn("scripts/hf_exact_main_ownership.py", owner)
        self.assertIn('--expected-sha "$GITHUB_SHA"', owner)
        self.assertIn("GITHUB_TOKEN: ${{ github.token }}", owner)
        self.assertNotIn("HF_TOKEN", terminal)
        self.assertNotIn("secrets.", terminal)
        self.assertIn("if: always()", receipt)
        self.assertIn("if-no-files-found: error", receipt)
        self.assertIn("scripts/hf_exact_main_ownership.py", enforce)
        self.assertIn('--expected-sha "$GITHUB_SHA"', enforce)
        self.assertIn("terminal-source-authorization-final.json", enforce)
        self.assertIn("grep -Fqx 'publish=true'", enforce)
        self.assertEqual(terminal.count("scripts/hf_exact_main_ownership.py"), 2)
        self.assertLess(terminal.index(owner), terminal.index(receipt))
        self.assertLess(terminal.index(receipt), terminal.index(enforce))
        self.assertEqual(terminal.rstrip().splitlines()[-1], "          echo 'Completed A11oy publication remains exact protected main.'")

    def test_actual_admission_outputs_deny_stale_and_uncertain_provider_jobs(self) -> None:
        # Exercise the helper consumed by both job conditions. These are injected
        # GitHub replies; no provider mutation or live deployment is performed.
        spec = importlib.util.spec_from_file_location("canonical_admission_test", HELPER)
        ownership = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ownership)
        expected, newer = "a" * 40, "b" * 40
        cases = (
            ("current", [{"commit": {"sha": expected}}], 0, "true", "OWNED"),
            ("superseded", [{"commit": {"sha": newer}}, {
                "status": "ahead", "ahead_by": 1, "behind_by": 0,
                "merge_base_commit": {"sha": expected},
            }], 0, "false", "SUPERSEDED_BY_NEWER_MAIN"),
            ("diverged", [{"commit": {"sha": newer}}, {
                "status": "diverged", "ahead_by": 1, "behind_by": 1,
                "merge_base_commit": {"sha": "c" * 40},
            }], 1, "false", "ERROR"),
            ("unavailable", [OSError("unavailable fixture")], 1, "false", "ERROR"),
        )
        for name, replies, code, publish, status in cases:
            with self.subTest(case=name), tempfile.TemporaryDirectory() as temporary:
                receipt = Path(temporary) / "admission.json"
                output = Path(temporary) / "output"
                with mock.patch.object(ownership, "request_json", side_effect=replies), redirect_stdout(io.StringIO()):
                    observed = ownership.execute(repository="szl-holdings/a11oy",
                        expected_sha=expected, receipt_path=receipt,
                        github_output=output, token="github-fixture")
                values = dict(line.split("=", 1) for line in output.read_text().splitlines())
                report = json.loads(receipt.read_text())
                self.assertEqual(observed, code)
                self.assertEqual(values["publish"], publish)
                self.assertEqual(report["status"], status)
                self.assertIs(report["external_writes_performed"], False)
                self.assertIs(report["secret_values_recorded"], False)


if __name__ == "__main__":
    unittest.main(verbosity=2)
