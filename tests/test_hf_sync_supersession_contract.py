"""Livelock-free hf-sync supersession and dependency contract (stdlib only).

The canonical deploy graph is source-admission -> preflight -> deploy ->
runtime-config -> readiness-verdict -> relock -> post-deployment-parity ->
terminal-source-authorization. Every gate is an invariant: protected main only,
the newest main wins and a superseded run ends neutral, reruns and manual
dispatch on main may deploy, and no job depends on an exact run, artifact,
parent commit or first attempt. The 2026-10-04..06 incident jobs that pinned
those identities (and livelocked 47+ consecutive main pushes) stay retired.
"""

from __future__ import annotations

import ast
import importlib.util
import io
import json
import re
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "hf-sync.yml"
HELPER = ROOT / "scripts" / "hf_exact_main_ownership.py"
TARGET_JOB = "Publish and live-verify six domain-native flagship Spaces"
RETIRED_JOBS = (
    "recovery-reconciliation", "manual-prerequisites", "durable-acquisition",
    "resume-paused-space", "publish-finance-projection",
)
EXPECTED_DEPENDENCIES = {
    "source-admission": [],
    "preflight": ["source-admission"],
    "deploy": ["source-admission", "preflight"],
    "runtime-config": ["preflight", "deploy"],
    "publish-vertical-flagships": ["source-admission", "deploy"],
    "readiness-verdict": ["runtime-config"],
    "relock": ["runtime-config", "readiness-verdict"],
    "post-deployment-parity": ["relock"],
    "terminal-source-authorization": ["relock", "post-deployment-parity", "publish-vertical-flagships"],
}
EXPECTED_CONDITIONS = {
    "source-admission": None,
    "preflight": "${{ needs.source-admission.result == 'success' && needs.source-admission.outputs.publish == 'true' }}",
    "deploy": "${{ needs.source-admission.outputs.publish == 'true' && needs.preflight.result == 'success' && needs.preflight.outputs.publish == 'true' }}",
    "runtime-config": None,
    "publish-vertical-flagships": "${{ needs.source-admission.outputs.publish == 'true' && needs.deploy.result == 'success' && github.event_name == 'workflow_dispatch' && inputs.publish_vertical_flagships }}",
    "readiness-verdict": None,
    "relock": None,
    "post-deployment-parity": "${{ needs.relock.outputs.current_main == 'true' }}",
    "terminal-source-authorization": "${{ always() && needs.relock.result == 'success' && (needs.post-deployment-parity.result == 'success' || (needs.post-deployment-parity.result == 'skipped' && needs.relock.outputs.current_main != 'true')) && (needs.publish-vertical-flagships.result == 'success' || needs.publish-vertical-flagships.result == 'skipped') }}",
}
# Only these reviewed steps tolerate a failed command, and only by recording it:
# none uses continue-on-error, so a failure can never be silently masked.
OUTPUT_KEYS = {
    "source-admission": ("publish",),
    "preflight": ("publish", "restart_required", "converged"),
    "relock": ("current_main",),
}


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


def needs_of(job: dict) -> list:
    actual = job.get("needs", [])
    return [actual] if isinstance(actual, str) else list(actual)


def assert_deploy_dependency_graph(source: str) -> dict:
    """Admit only the reviewed livelock-free graph; return its jobs."""
    jobs = workflow_document(source).get("jobs", {})
    if set(jobs) != set(EXPECTED_DEPENDENCIES):
        raise WorkflowContractError("job set requires review")
    for name, required in EXPECTED_DEPENDENCIES.items():
        job = jobs[name]
        if needs_of(job) != required:
            raise WorkflowContractError("dependency gate: " + name)
        if job.get("if") != EXPECTED_CONDITIONS[name]:
            raise WorkflowContractError("condition gate: " + name)
        if "continue-on-error" in job:
            raise WorkflowContractError("job failure bypass: " + name)
        steps = job.get("steps", [])
        ids = [step["id"] for step in steps if "id" in step]
        if len(ids) != len(set(ids)):
            raise WorkflowContractError("duplicate step id: " + name)
        if any("continue-on-error" in step for step in steps):
            raise WorkflowContractError("step failure bypass: " + name)
    for name in jobs:
        if name == "source-admission":
            continue
        pending, ancestors = list(EXPECTED_DEPENDENCIES[name]), set()
        while pending:
            parent = pending.pop()
            if parent not in ancestors:
                ancestors.add(parent)
                pending.extend(EXPECTED_DEPENDENCIES[parent])
        if "source-admission" not in ancestors:
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


def explicit_condition_allows(job: dict, context: dict) -> bool:
    """Evaluate only this workflow's reviewed literal boolean condition subset."""
    condition = job["if"]
    if not condition.startswith("${{") or not condition.endswith("}}"):
        raise WorkflowContractError("unsupported condition expression")
    expression = re.sub(r"\b(?:github|needs|inputs)\.[A-Za-z0-9_.-]+",
                        lambda match: repr(context[match.group()]), condition[3:-2])
    expression = expression.replace("always()", "True").replace("&&", " and ").replace("||", " or ")
    expression = re.sub(r"!(?!=)", " not ", expression).strip()
    parsed = ast.parse(expression, mode="eval")

    class LiteralBooleans(ast.NodeTransformer):
        def visit_Name(self, node):
            if node.id in ("true", "false"):
                return ast.copy_location(ast.Constant(node.id == "true"), node)
            return node

    parsed = ast.fix_missing_locations(LiteralBooleans().visit(parsed))
    allowed = (ast.Expression, ast.Constant, ast.BoolOp, ast.And, ast.Or,
               ast.UnaryOp, ast.Not, ast.Compare, ast.Eq, ast.NotEq)
    if any(type(node) not in allowed for node in ast.walk(parsed)):
        raise WorkflowContractError("unsupported condition expression")
    return eval(compile(parsed, "<reviewed-workflow-condition>", "eval"), {"__builtins__": {}}, {})


def simulate(jobs: dict, *, event="push", attempt=1, vertical=False,
             outputs=None, failures=()) -> dict:
    """Model the job graph, including GitHub's implicit success() rule.

    ``outputs`` supplies job outputs (missing outputs read as empty strings);
    ``failures`` names jobs whose execution fails when they are scheduled.
    """
    produced = {"source-admission": {"publish": "true"},
                "preflight": {"publish": "true", "restart_required": "false", "converged": "true"},
                "relock": {"current_main": "true"}}
    for name, values in (outputs or {}).items():
        produced.setdefault(name, {}).update(values)
    context = {"github.event_name": event, "github.run_attempt": attempt,
               "inputs.publish_vertical_flagships": vertical}
    results, pending = {}, set(jobs)
    while pending:
        ready = sorted(name for name in pending
                       if all(parent in results for parent in needs_of(jobs[name])))
        if not ready:
            raise AssertionError("cyclic or unresolved dependency graph")
        for name in ready:
            job = jobs[name]
            condition = job.get("if")
            allows = condition is None or explicit_condition_allows(job, context)
            if condition is None or "always()" not in condition:
                allows = allows and all(results[parent] == "success" for parent in needs_of(job))
            result = ("failure" if name in failures else "success") if allows else "skipped"
            results[name] = result
            context["needs." + name + ".result"] = result
            for key in OUTPUT_KEYS.get(name, ()):
                value = produced.get(name, {}).get(key, "") if result == "success" else ""
                context["needs." + name + ".outputs." + key] = value
            pending.remove(name)
    return results


DEPLOY_PATH = ("preflight", "deploy", "runtime-config", "readiness-verdict", "relock",
               "post-deployment-parity", "terminal-source-authorization")


class HFSyncLivelockFreeGraphTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = WORKFLOW.read_text(encoding="utf-8")
        cls.jobs = assert_deploy_dependency_graph(cls.source)

    def test_exact_livelock_free_graph(self) -> None:
        self.assertNotIn("run_attempt == 1", self.source)
        for name in RETIRED_JOBS:
            self.assertNotIn(name, self.source)

    def test_push_dispatch_and_reruns_on_current_main_deploy(self) -> None:
        # G3/G4: a transient failure no longer burns the commit, and an
        # operator can redeploy main by dispatch.
        for event in ("push", "workflow_dispatch"):
            for attempt in (1, 2, 3):
                with self.subTest(event=event, attempt=attempt):
                    results = simulate(self.jobs, event=event, attempt=attempt)
                    for name in ("source-admission", *DEPLOY_PATH):
                        self.assertEqual(results[name], "success", name)
                    self.assertEqual(results["publish-vertical-flagships"], "skipped")

    def test_superseded_admission_skips_every_effect_neutrally(self) -> None:
        results = simulate(self.jobs, outputs={"source-admission": {"publish": "false"}})
        self.assertEqual(results["source-admission"], "success")
        self.assertEqual({name for name, result in results.items() if result != "skipped"},
                         {"source-admission"})

    def test_superseded_before_deploy_never_publishes(self) -> None:
        results = simulate(self.jobs, outputs={"preflight": {"publish": "false"}})
        self.assertEqual(results["preflight"], "success")
        self.assertNotIn("failure", results.values())
        for name in DEPLOY_PATH[1:]:
            self.assertEqual(results[name], "skipped", name)

    def test_superseded_after_verification_is_neutral(self) -> None:
        # G21: newest main wins; the older run neither fails nor runs parity.
        results = simulate(self.jobs, outputs={"relock": {"current_main": "false"}})
        self.assertEqual(results["relock"], "success")
        self.assertEqual(results["post-deployment-parity"], "skipped")
        self.assertEqual(results["terminal-source-authorization"], "success")

    def test_failed_effects_never_reach_terminal_authorization(self) -> None:
        for failed in ("preflight", "deploy", "runtime-config", "readiness-verdict",
                       "relock", "post-deployment-parity"):
            with self.subTest(failed=failed):
                results = simulate(self.jobs, failures=(failed,))
                self.assertEqual(results[failed], "failure")
                self.assertNotEqual(results["terminal-source-authorization"], "success")
                later = DEPLOY_PATH[DEPLOY_PATH.index(failed) + 1:]
                for name in later:
                    self.assertNotEqual(results[name], "success", name)

    def test_parity_skip_cannot_mask_a_current_main_failure(self) -> None:
        results = simulate(self.jobs, failures=("post-deployment-parity",))
        self.assertEqual(results["terminal-source-authorization"], "skipped")

    def test_vertical_publication_requires_dispatch_opt_in_and_deploy(self) -> None:
        self.assertEqual(simulate(self.jobs, event="workflow_dispatch", vertical=True)[
            "publish-vertical-flagships"], "success")
        for kwargs in ({"event": "push", "vertical": True},
                       {"event": "workflow_dispatch", "vertical": False},
                       {"event": "workflow_dispatch", "vertical": True, "failures": ("deploy",)},
                       {"event": "workflow_dispatch", "vertical": True,
                        "outputs": {"source-admission": {"publish": "false"}}}):
            with self.subTest(**{key: str(value) for key, value in kwargs.items()}):
                self.assertNotEqual(simulate(self.jobs, **kwargs)["publish-vertical-flagships"], "success")
        failed = simulate(self.jobs, event="workflow_dispatch", vertical=True,
                          failures=("publish-vertical-flagships",))
        self.assertEqual(failed["terminal-source-authorization"], "skipped")

    def test_deploy_path_starts_the_space_once(self) -> None:
        deploy = job_block(self.source, "Deploy, source-bind, and attest exact surface")
        self.assertIn("restart-space: ${{ needs.preflight.outputs.restart_required == 'true' }}", deploy)
        self.assertIn("require-default-branch-tip: true", deploy)
        self.assertIn("ref: ${{ github.sha }}", deploy)
        self.assertIn("cancel-in-progress: false", self.source)
        for script in ("prove_hf_series_a_restart.py", "prove_hf_gdw_runtime.py"):
            self.assertNotIn(script, self.source)
        # The verdict gate runs, but never writes the restart-inducing variable.
        self.assertEqual(self.source.count("publish_readiness_verdict.py"), 1)
        self.assertIn("publish_readiness_verdict.py\n          --validate-only\n", self.source)

    def test_dependency_and_condition_mutations_are_rejected(self) -> None:
        mutations = (
            ("    needs: [source-admission, preflight]\n", "    needs: source-admission\n", "dependency gate: deploy"),
            ("    needs: [preflight, deploy]\n", "    needs: deploy\n", "dependency gate: runtime-config"),
            ("    needs: [runtime-config, readiness-verdict]\n", "    needs: runtime-config\n", "dependency gate: relock"),
            ("    needs: [relock, post-deployment-parity, publish-vertical-flagships]\n",
             "    needs: [post-deployment-parity, publish-vertical-flagships]\n", "dependency gate: terminal-source-authorization"),
            ("    if: " + EXPECTED_CONDITIONS["deploy"] + "\n",
             "    if: ${{ github.event_name == 'push' && github.run_attempt == 1 && needs.preflight.result == 'success' }}\n", "condition gate: deploy"),
            ("    if: " + EXPECTED_CONDITIONS["preflight"] + "\n", "    if: always()\n", "condition gate: preflight"),
            ("    if: " + EXPECTED_CONDITIONS["post-deployment-parity"] + "\n", "", "condition gate: post-deployment-parity"),
            ("    needs: runtime-config\n", "    needs: runtime-config\n    if: ${{ always() }}\n", "condition gate: readiness-verdict"),
        )
        for original, replacement, diagnostic in mutations:
            with self.subTest(diagnostic=diagnostic):
                self.assertIn(original, self.source)
                with self.assertRaisesRegex(WorkflowContractError, re.escape(diagnostic)):
                    assert_deploy_dependency_graph(self.source.replace(original, replacement, 1))

    def test_new_retired_duplicate_jobs_and_failure_bypasses_require_review(self) -> None:
        cases = (
            (self.source + "\n  unreviewed-job:\n    runs-on: ubuntu-latest\n", "job set requires review"),
            (self.source + "\n  durable-acquisition:\n    runs-on: ubuntu-latest\n", "job set requires review"),
            (self.source.replace("  preflight:\n", "  resume-paused-space:\n", 1), "job set requires review"),
            (self.source.replace("  deploy:\n", "  deploy:\n    continue-on-error: true\n", 1), "job failure bypass: deploy"),
            (self.source.replace("      - name: Classify the runtime stage without restarting it\n",
                                 "      - name: Classify the runtime stage without restarting it\n        continue-on-error: true\n", 1),
             "step failure bypass: preflight"),
            (self.source.replace("        id: owner\n", "        id: owner\n        id: forged\n", 1), "duplicate mapping key: id"),
            (self.source.replace("        id: converge\n", "        id: owner\n", 1), "duplicate step id: preflight"),
        )
        for changed, diagnostic in cases:
            with self.subTest(diagnostic=diagnostic), self.assertRaisesRegex(WorkflowContractError, re.escape(diagnostic)):
                assert_deploy_dependency_graph(changed)

    def test_literal_boolean_evaluator_keeps_strings_and_rejects_executable_nodes(self) -> None:
        self.assertFalse(explicit_condition_allows({"if": "${{ false }}"}, {}))
        self.assertTrue(explicit_condition_allows({"if": "${{ true && 'false' != false && 'true' != true }}"}, {}))
        for condition in ("${{ unreviewed }}", "${{ success() }}", "${{ unreviewed.value }}"):
            with self.subTest(condition=condition), self.assertRaises(WorkflowContractError):
                explicit_condition_allows({"if": condition}, {})


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

    def test_preflight_readmits_main_immediately_before_deploy(self) -> None:
        job = job_block(self.workflow, "Classify the canonical runtime and converge configuration before deploy")
        owner = step_block(job, "Re-admit current protected main immediately before deploy")
        self.assertIn("id: owner", owner)
        self.assertIn("scripts/hf_exact_main_ownership.py", owner)
        self.assertIn('--expected-sha "$GITHUB_SHA"', owner)
        self.assertIn("set -euo pipefail", owner)
        self.assertIn("publish: ${{ steps.owner.outputs.publish }}", job)
        self.assertLess(job.index("Converge runtime configuration before the single deploy start"), job.index(owner))
        notice = step_block(job, "Skip a superseded source with a notice")
        self.assertIn("::notice::", notice)
        self.assertNotIn("exit", notice)

    def test_post_deploy_relock_neutralizes_only_a_verified_superseded_source(self) -> None:
        job = job_block(self.workflow, "Prove exact live source, runtime, routes, and singleton state")
        owner = step_block(job, "Re-admit exact current main after live verification")
        evidence = step_block(job, "Upload immutable relock evidence")
        enforce = step_block(job, "Enforce exact live state")
        self.assertIn("id: post_deploy_owner", owner)
        self.assertIn("scripts/hf_exact_main_ownership.py", owner)
        self.assertIn('--expected-sha "$GITHUB_SHA"', owner)
        self.assertIn("set -euo pipefail", owner)
        self.assertIn("GITHUB_TOKEN: ${{ github.token }}", owner)
        self.assertIn("post-deploy-source-admission.json", evidence)
        self.assertIn("current_main: ${{ steps.post_deploy_owner.outputs.publish }}", job)
        self.assertIn("steps.post_deploy_owner.outputs.publish", enforce)
        self.assertIn("CURRENT_MAIN:-false", enforce)
        # A failed live verification stays red; supersession alone is neutral.
        self.assertIn('exit "$code"', enforce)
        self.assertLess(enforce.index('exit "$code"'), enforce.index("::notice::"))
        self.assertNotIn("exit 3", enforce)
        self.assertLess(job.index("Evaluate the canonical application contract"), job.index(owner))
        self.assertLess(job.index(owner), job.index(enforce))

    def test_terminal_authorization_follows_all_publication_proofs(self) -> None:
        jobs = assert_deploy_dependency_graph(self.workflow)
        terminal = job_block(self.workflow, "Re-authorize exact protected main after all publication proofs")
        owner = step_block(terminal, "Re-authorize exact protected main after awaited parity")
        receipt = step_block(terminal, "Retain terminal source authorization")
        enforce = step_block(terminal, "Re-read and enforce exact protected-main ownership as the final step")
        self.assertEqual(jobs["terminal-source-authorization"]["needs"],
                         ["relock", "post-deployment-parity", "publish-vertical-flagships"])
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
        self.assertIn("::notice::", enforce)
        self.assertNotIn("exit 3", enforce)
        self.assertEqual(terminal.count("scripts/hf_exact_main_ownership.py"), 2)
        self.assertLess(terminal.index(owner), terminal.index(receipt))
        self.assertLess(terminal.index(receipt), terminal.index(enforce))
        self.assertEqual(terminal.rstrip().splitlines()[-1], "          echo 'Completed A11oy publication remains exact protected main.'")

    def test_actual_admission_outputs_deny_stale_and_uncertain_provider_jobs(self) -> None:
        # Exercise the helper consumed by every ownership gate. These are
        # injected GitHub replies; no provider mutation is performed.
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
