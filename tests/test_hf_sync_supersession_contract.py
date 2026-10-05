from __future__ import annotations

import re
import ast
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
FIRST_PUSH_JOBS = (
    "recovery-reconciliation", "manual-prerequisites", "durable-acquisition",
    "resume-paused-space", "deploy", "runtime-config",
    "publish-finance-projection", "readiness-verdict",
)
DISABLED_JOBS = ("recovery-reconciliation", "manual-prerequisites")
REVIEWED_MANUAL_FAILURE_STEPS = (
    {
        "name": "Preserve stopped private stores before any runtime mutation",
        "id": "preserve_stores",
        "continue-on-error": True,
        "run": 'python -B scripts/preserve_hf_gdw_store.py --supervised-acquisition --output "${{ runner.temp }}/gdw-store-preservation.json"',
    },
    {
        "name": "Qualify the pinned private capture without admitting restore",
        "id": "qualify_stores",
        "if": "${{ always() && steps.preserve_stores.outcome == 'failure' }}",
        "continue-on-error": True,
        "run": (
            "python -B scripts/qualify_gdw_store_recovery.py "
            "--capture-report docs/operations/evidence/gdw-capture-37223162231.json "
            "--historical-anchors docs/operations/evidence/gdw-recovery-historical-anchors.json "
            '--output "${{ runner.temp }}/gdw-store-recovery-qualification.json"'
        ),
    },
)


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
        "recovery-reconciliation": ["source-admission"],
        "manual-prerequisites": ["source-admission", "recovery-reconciliation"],
        "durable-acquisition": ["source-admission", "recovery-reconciliation", "manual-prerequisites"],
        "resume-paused-space": ["source-admission", "manual-prerequisites"],
        "deploy": ["source-admission", "manual-prerequisites", "durable-acquisition", "resume-paused-space"],
        "runtime-config": ["manual-prerequisites", "durable-acquisition", "deploy"],
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
        "recovery-reconciliation": "${{ github.event_name == 'push' && github.run_attempt == 1 && needs.source-admission.result == 'success' && needs.source-admission.outputs.publish == 'true' && false }}",
        "manual-prerequisites": "${{ github.event_name == 'push' && github.run_attempt == 1 && needs.source-admission.outputs.publish == 'true' && needs.recovery-reconciliation.result == 'success' && needs.recovery-reconciliation.outputs.admitted == 'true' && false }}",
        "durable-acquisition": "${{ github.event_name == 'push' && github.run_attempt == 1 && always() && needs.source-admission.result == 'success' && needs.source-admission.outputs.publish == 'true' && needs.recovery-reconciliation.result == 'skipped' && needs.manual-prerequisites.result == 'skipped' }}",
        "resume-paused-space": "${{ github.event_name == 'push' && github.run_attempt == 1 && needs.source-admission.outputs.publish == 'true' && needs.manual-prerequisites.result == 'success' && needs.manual-prerequisites.outputs.mode != 'managed-recovery' }}",
        "deploy": "${{ github.event_name == 'push' && github.run_attempt == 1 && always() && needs.source-admission.outputs.publish == 'true' && needs.manual-prerequisites.result == 'success' && ((needs.manual-prerequisites.outputs.mode == 'managed-recovery' && needs.durable-acquisition.result == 'success') || (needs.manual-prerequisites.outputs.mode != 'managed-recovery' && needs.resume-paused-space.result == 'success')) }}",
        "runtime-config": "${{ github.event_name == 'push' && github.run_attempt == 1 && always() && needs.manual-prerequisites.result == 'success' && needs.durable-acquisition.result == 'success' && needs.deploy.result == 'success' }}",
        "publish-vertical-flagships": "${{ github.run_attempt == 1 && needs.manual-prerequisites.result == 'success' && github.event_name == 'workflow_dispatch' && inputs.publish_vertical_flagships }}",
        "publish-finance-projection": "${{ github.event_name == 'push' && github.run_attempt == 1 && needs.manual-prerequisites.result == 'success' && (github.event_name == 'push' || !inputs.publish_vertical_flagships) }}",
        "readiness-verdict": "${{ github.event_name == 'push' && github.run_attempt == 1 }}",
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
                # Only these complete, fixed manual steps can tolerate failure.
                # The disabled job retains its exact classifier and evidence
                # steps; the inspection job gains no failure bypass.
                reviewed = dict(step)
                if isinstance(reviewed.get("run"), str):
                    reviewed["run"] = " ".join(reviewed["run"].split())
                if (name != "manual-prerequisites"
                        or reviewed not in REVIEWED_MANUAL_FAILURE_STEPS):
                    raise WorkflowContractError("step failure bypass: " + name)
    for name in jobs:
        if name in ("source-admission", "recovery-reconciliation", "manual-prerequisites"):
            continue
        pending, ancestors = list(dependencies[name]), set()
        while pending:
            parent = pending.pop()
            if parent in ancestors:
                continue
            ancestors.add(parent)
            pending.extend(dependencies[parent])
        if not {"source-admission", "recovery-reconciliation", "manual-prerequisites"}.issubset(ancestors):
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
    """Evaluate only this workflow's reviewed literal boolean condition subset.

    The fixtures deliberately grant reused dependency successes. No implicit
    scheduling rule is credited with rejecting a later attempt at this boundary.
    """
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


def successful_dependency_context(jobs: dict, *, event="push", attempt=1, mode="managed-recovery") -> dict:
    """Adversarially reusable successes, independent of real action execution."""
    context = {"needs." + name + ".result": "success" for name in jobs}
    context.update({
        "github.event_name": event, "github.run_attempt": attempt,
        "github.ref": "refs/heads/main",
        "needs.source-admission.outputs.publish": "true",
        "needs.recovery-reconciliation.outputs.admitted": "true",
        "needs.manual-prerequisites.outputs.mode": mode,
        "inputs.publish_vertical_flagships": True,
    })
    return context


def inspection_dependency_context(jobs: dict, **kwargs) -> dict:
    context = successful_dependency_context(jobs, **kwargs)
    for name in DISABLED_JOBS:
        context["needs." + name + ".result"] = "skipped"
    context["needs.recovery-reconciliation.outputs.admitted"] = ""
    context["needs.manual-prerequisites.outputs.mode"] = ""
    return context


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

    def test_initial_provider_jobs_require_successful_owned_admission(self) -> None:
        jobs = assert_manual_dependency_graph(self.workflow)
        for name in (
            "Acquire qualified private storage through the canonical publisher",
            "Resume the canonical Space without changing its allocation",
            "Deploy, source-bind, and attest exact surface",
        ):
            with self.subTest(job=name):
                job = job_block(self.workflow, name)
                self.assertIn("needs.source-admission.outputs.publish == 'true'", job)
                self.assertIn("github.event_name == 'push' && github.run_attempt == 1", job)
                if name == "Acquire qualified private storage through the canonical publisher":
                    self.assertIn("needs.source-admission.result == 'success'", job)
                    self.assertIn("needs.recovery-reconciliation.result == 'skipped'", job)
                    self.assertIn("needs.manual-prerequisites.result == 'skipped'", job)
                    self.assertIn("--inspect-held-acquisition", job)
                else:
                    self.assertIn("needs.manual-prerequisites.result == 'success'", job)
                if name == "Resume the canonical Space without changing its allocation":
                    self.assertNotRegex(job, r"(?m)^    if:.*always\(")
                self.assertNotIn("continue-on-error", job)
        deploy = job_block(self.workflow, "Deploy, source-bind, and attest exact surface")
        self.assertIn("require-default-branch-tip: true", deploy)
        self.assertIn("ref: ${{ github.sha }}", deploy)
        self.assertIn("cancel-in-progress: false", self.workflow)
        self.assertIn("resume-paused-space", jobs["deploy"]["needs"])
        self.assertIn("durable-acquisition", jobs["deploy"]["needs"])
        # The reviewed always() only permits evaluation after the other mode's
        # job is skipped; each branch still requires its own successful effect.
        self.assertIn("needs.durable-acquisition.result == 'success'", jobs["deploy"]["if"])
        self.assertIn("needs.resume-paused-space.result == 'success'", jobs["deploy"]["if"])
        self.assertEqual(jobs["runtime-config"]["needs"],
                         ["manual-prerequisites", "durable-acquisition", "deploy"])

    def test_every_effect_job_requires_the_complete_dependency_graph(self) -> None:
        assert_manual_dependency_graph(self.workflow)

    def test_reconciliation_requires_success_and_exact_positive_admission_before_copies(self) -> None:
        jobs = assert_manual_dependency_graph(self.workflow)
        manual = jobs["manual-prerequisites"]
        # Exercise the preserved original predicates independently of the new
        # literal hold. This hypothetical condition is never the admitted job.
        predicates = {"if": manual["if"].replace(" && false }}", " }}", 1)}
        context = successful_dependency_context(jobs)
        self.assertTrue(explicit_condition_allows(predicates, context))
        self.assertFalse(explicit_condition_allows(manual, context))
        for result in ("failure", "cancelled", "skipped", ""):
            context = successful_dependency_context(jobs)
            context["needs.recovery-reconciliation.result"] = result
            with self.subTest(result=result):
                self.assertFalse(explicit_condition_allows(predicates, context))
                self.assertFalse(explicit_condition_allows(manual, context))
        for output in ("false", "", "HELD", "unknown"):
            context = successful_dependency_context(jobs)
            context["needs.recovery-reconciliation.outputs.admitted"] = output
            with self.subTest(output=output):
                self.assertFalse(explicit_condition_allows(predicates, context))
                self.assertFalse(explicit_condition_allows(manual, context))

    def test_inspection_requires_owned_source_and_both_literal_holds_skipped(self) -> None:
        jobs = assert_manual_dependency_graph(self.workflow)
        inspection = jobs["durable-acquisition"]
        self.assertTrue(explicit_condition_allows(inspection, inspection_dependency_context(jobs)))
        for dependency, rejected in (
            ("source-admission", ("failure", "cancelled", "skipped", "")),
            ("recovery-reconciliation", ("success", "failure", "cancelled", "")),
            ("manual-prerequisites", ("success", "failure", "cancelled", "")),
        ):
            for result in rejected:
                context = inspection_dependency_context(jobs)
                context["needs." + dependency + ".result"] = result
                with self.subTest(dependency=dependency, result=result):
                    self.assertFalse(explicit_condition_allows(inspection, context))
        for output in ("false", "", "HELD", "unknown"):
            context = inspection_dependency_context(jobs)
            context["needs.source-admission.outputs.publish"] = output
            with self.subTest(output=output):
                self.assertFalse(explicit_condition_allows(inspection, context))

    def test_literal_job_holds_cannot_be_removed_or_reversed(self) -> None:
        jobs = assert_manual_dependency_graph(self.workflow)
        for name in DISABLED_JOBS:
            job = jobs[name]
            target = job_block(self.workflow, job["name"])
            context = successful_dependency_context(jobs)
            self.assertFalse(explicit_condition_allows(job, context), name)
            for replacement in (" }}", " && true }}"):
                weakened = job["if"].replace(" && false }}", replacement, 1)
                with self.subTest(job=name, replacement=replacement):
                    self.assertNotEqual(job["if"], weakened)
                    self.assertTrue(explicit_condition_allows({"if": weakened}, context))
                    changed = self.workflow.replace(target, target.replace(job["if"], weakened, 1), 1)
                    with self.assertRaisesRegex(WorkflowContractError, "condition gate: " + name):
                        assert_manual_dependency_graph(changed)

    def test_literal_boolean_evaluator_keeps_strings_and_rejects_executable_nodes(self) -> None:
        self.assertFalse(explicit_condition_allows({"if": "${{ false }}"}, {}))
        self.assertTrue(explicit_condition_allows({"if": "${{ true && 'false' != false && 'true' != true }}"}, {}))
        for condition in ("${{ unreviewed }}", "${{ success() }}", "${{ unreviewed.value }}"):
            with self.subTest(condition=condition), self.assertRaises(WorkflowContractError):
                explicit_condition_allows({"if": condition}, {})

    def test_full_and_partial_reruns_hold_even_when_successful_jobs_are_reused(self) -> None:
        jobs = assert_manual_dependency_graph(self.workflow)
        for name in (*FIRST_PUSH_JOBS, "publish-vertical-flagships"):
            event = "workflow_dispatch" if name == "publish-vertical-flagships" else "push"
            mode = "verified-manual" if name == "resume-paused-space" else "managed-recovery"
            first = successful_dependency_context(jobs, event=event, mode=mode)
            if name == "durable-acquisition":
                first = inspection_dependency_context(jobs)
            self.assertEqual(explicit_condition_allows(jobs[name], first), name not in DISABLED_JOBS, name)
            for attempt in (0, 2, 3):
                for reused in (False, True):
                    context = successful_dependency_context(jobs, event=event, attempt=attempt, mode=mode)
                    if not reused:
                        for dependency in ("recovery-reconciliation", "manual-prerequisites", "durable-acquisition", "deploy"):
                            context["needs." + dependency + ".result"] = "skipped"
                        context["needs.recovery-reconciliation.outputs.admitted"] = ""
                    with self.subTest(job=name, attempt=attempt, reused_success=reused):
                        self.assertFalse(explicit_condition_allows(jobs[name], context))

    def test_dispatch_and_other_events_cannot_reuse_push_admission(self) -> None:
        jobs = assert_manual_dependency_graph(self.workflow)
        for name in FIRST_PUSH_JOBS:
            for event in ("workflow_dispatch", "pull_request", "schedule"):
                context = successful_dependency_context(jobs, event=event,
                    mode="verified-manual" if name == "resume-paused-space" else "managed-recovery")
                if name == "durable-acquisition":
                    context = inspection_dependency_context(jobs, event=event)
                with self.subTest(job=name, event=event):
                    self.assertFalse(explicit_condition_allows(jobs[name], context))
        # A fresh dispatch cannot produce successful push-only prerequisites,
        # including when its separate vertical opt-in is explicitly requested.
        context = successful_dependency_context(jobs, event="workflow_dispatch")
        context["needs.manual-prerequisites.result"] = "skipped"
        self.assertFalse(explicit_condition_allows(jobs["publish-vertical-flagships"], context))

    def test_complete_inspection_graph_cannot_schedule_any_downstream_effect(self) -> None:
        jobs = assert_manual_dependency_graph(self.workflow)
        dependencies = {
            name: ([job["needs"]] if isinstance(job.get("needs"), str) else job.get("needs", []))
            for name, job in jobs.items()
        }
        for event in ("push", "workflow_dispatch"):
            for attempt in (1, 2):
                for inspection_result in ("failure", "success"):
                    context = successful_dependency_context(jobs, event=event, attempt=attempt)
                    # Model the actual dependency graph, including GitHub's
                    # implicit success condition when no always() is present.
                    # The synthetic inspection success must not open a writer.
                    results, pending = {}, set(jobs)
                    while pending:
                        ready = sorted(name for name in pending
                                       if all(parent in results for parent in dependencies[name]))
                        self.assertTrue(ready, "cyclic or unresolved dependency graph")
                        for name in ready:
                            job = jobs[name]
                            condition = job.get("if")
                            allows = condition is None or explicit_condition_allows(job, context)
                            if condition is None or "always()" not in condition:
                                allows = allows and all(results[parent] == "success"
                                                        for parent in dependencies[name])
                            result = (inspection_result if name == "durable-acquisition" else "success") if allows else "skipped"
                            results[name] = result
                            context["needs." + name + ".result"] = result
                            if name == "manual-prerequisites":
                                context["needs.manual-prerequisites.outputs.mode"] = ""
                            if name == "recovery-reconciliation":
                                context["needs.recovery-reconciliation.outputs.admitted"] = ""
                            pending.remove(name)
                    with self.subTest(event=event, attempt=attempt, inspection_result=inspection_result):
                        self.assertEqual(results["source-admission"], "success")
                        self.assertEqual(results["durable-acquisition"],
                                         inspection_result if event == "push" and attempt == 1 else "skipped")
                        self.assertEqual({name: result for name, result in results.items()
                                          if name not in ("source-admission", "durable-acquisition")},
                                         {name: "skipped" for name in jobs
                                          if name not in ("source-admission", "durable-acquisition")})
                        pair = next(step for step in jobs["durable-acquisition"]["steps"]
                                    if step["name"] == "Install the persistent old-source guard and both managed configurations once")
                        self.assertFalse(explicit_condition_allows(pair, context))

    def test_current_attempt_predicates_cannot_be_removed_or_reversed(self) -> None:
        jobs = assert_manual_dependency_graph(self.workflow)
        for key in (*FIRST_PUSH_JOBS, "publish-vertical-flagships"):
            job = jobs[key]
            target = job_block(self.workflow, job["name"])
            condition = job["if"]
            removed = condition.replace("github.run_attempt == 1 && ", "", 1)
            if removed == condition:
                removed = condition.replace(" && github.run_attempt == 1", "", 1)
            context = successful_dependency_context(jobs, attempt=2,
                event="workflow_dispatch" if key == "publish-vertical-flagships" else "push",
                mode="verified-manual" if key == "resume-paused-space" else "managed-recovery")
            if key == "durable-acquisition":
                context = inspection_dependency_context(jobs, attempt=2)
            for weakened in (removed, condition.replace("github.run_attempt == 1", "github.run_attempt != 1", 1)):
                with self.subTest(job=key, condition=weakened):
                    self.assertNotEqual(condition, weakened)
                    # Disabled jobs remain held even with a weakened attempt
                    # term, but their strict source contract still rejects it.
                    self.assertEqual(explicit_condition_allows({"if": weakened}, context), key not in DISABLED_JOBS)
                    changed = self.workflow.replace(target, target.replace(condition, weakened, 1), 1)
                    with self.assertRaisesRegex(WorkflowContractError, "condition gate: " + key):
                        assert_manual_dependency_graph(changed)
        for key in FIRST_PUSH_JOBS:
            job = jobs[key]
            target = job_block(self.workflow, job["name"])
            for weakened in (job["if"].replace("github.event_name == 'push' && ", "", 1),
                             job["if"].replace("github.event_name == 'push'", "github.event_name != 'push'", 1)):
                with self.subTest(job=key, condition=weakened):
                    self.assertNotEqual(job["if"], weakened)
                    changed = self.workflow.replace(target, target.replace(job["if"], weakened, 1), 1)
                    with self.assertRaisesRegex(WorkflowContractError, "condition gate: " + key):
                        assert_manual_dependency_graph(changed)

    def test_deleted_or_bypassed_dependency_gates_are_rejected(self) -> None:
        jobs = assert_manual_dependency_graph(self.workflow)
        mutations = (
            ("Reconcile the held acquisition before provider mutation", "    needs: source-admission\n", "", "dependency gate: recovery-reconciliation"),
            ("Check manual authority prerequisites before provider writes", "    needs: [source-admission, recovery-reconciliation]\n", "    needs: source-admission\n", "dependency gate: manual-prerequisites"),
            ("Acquire qualified private storage through the canonical publisher", "    needs: [source-admission, recovery-reconciliation, manual-prerequisites]\n", "    needs: [source-admission, manual-prerequisites]\n", "dependency gate: durable-acquisition"),
            ("Acquire qualified private storage through the canonical publisher", "    needs: [source-admission, recovery-reconciliation, manual-prerequisites]\n", "    needs: source-admission\n", "dependency gate: durable-acquisition"),
            ("Resume the canonical Space without changing its allocation", "    needs: [source-admission, manual-prerequisites]\n", "    needs: source-admission\n", "dependency gate: resume-paused-space"),
            ("Deploy, source-bind, and attest exact surface", "    needs: [source-admission, manual-prerequisites, durable-acquisition, resume-paused-space]\n", "    needs: [source-admission, manual-prerequisites]\n", "dependency gate: deploy"),
            ("Probe and ingest exact post-deploy readiness verdict", "    needs: [manual-prerequisites, runtime-config]\n", "    needs: runtime-config\n", "dependency gate: readiness-verdict"),
            ("Rebind and functionally verify the existing Finance projection", "    needs: [manual-prerequisites, relock]\n", "    needs: manual-prerequisites\n", "dependency gate: publish-finance-projection"),
            ("Resume the canonical Space without changing its allocation", "    if: " + jobs["resume-paused-space"]["if"] + "\n", "    if: always()\n", "condition gate: resume-paused-space"),
            ("Deploy, source-bind, and attest exact surface", "    if: " + jobs["deploy"]["if"] + "\n", "", "condition gate: deploy"),
            ("Verify post-deploy configuration and bounded live proofs", "    needs: [manual-prerequisites, durable-acquisition, deploy]\n", "    needs: deploy\n", "dependency gate: runtime-config"),
            (TARGET_JOB, "    if: " + jobs["publish-vertical-flagships"]["if"] + "\n", "    if: ${{ needs.manual-prerequisites.result == 'success' || inputs.publish_vertical_flagships }}\n", "condition gate: publish-vertical-flagships"),
            ("Prove exact live source, runtime, routes, and singleton state", "    needs: [manual-prerequisites, runtime-config, readiness-verdict]\n", "    needs: [runtime-config, readiness-verdict]\n", "dependency gate: relock"),
            ("Re-authorize exact protected main after all publication proofs", "    needs: [post-deployment-parity, publish-vertical-flagships, publish-finance-projection]\n", "    needs: post-deployment-parity\n", "dependency gate: terminal-source-authorization"),
        )
        for name, original, replacement, diagnostic in mutations:
            with self.subTest(diagnostic=diagnostic):
                target = job_block(self.workflow, name)
                self.assertIn(original, target)
                changed = self.workflow.replace(target, target.replace(original, replacement, 1), 1)
                with self.assertRaisesRegex(WorkflowContractError, re.escape(diagnostic)):
                    assert_manual_dependency_graph(changed)

    def test_mode_gates_reject_reversed_modes_and_skipped_acquisition(self) -> None:
        jobs = assert_manual_dependency_graph(self.workflow)
        mutations = (
            ("Acquire qualified private storage through the canonical publisher",
             "needs.manual-prerequisites.result == 'skipped'",
             "needs.manual-prerequisites.result == 'success'", "durable-acquisition"),
            ("Acquire qualified private storage through the canonical publisher",
             "needs.source-admission.outputs.publish == 'true' && ", "", "durable-acquisition"),
            ("Acquire qualified private storage through the canonical publisher",
             "needs.recovery-reconciliation.result == 'skipped'",
             "needs.recovery-reconciliation.result == 'success'", "durable-acquisition"),
            ("Acquire qualified private storage through the canonical publisher",
             "needs.source-admission.result == 'success' && ", "", "durable-acquisition"),
            ("Acquire qualified private storage through the canonical publisher",
             "needs.manual-prerequisites.result == 'skipped'",
             "needs.manual-prerequisites.outputs.mode == 'managed-recovery'", "durable-acquisition"),
            ("Check manual authority prerequisites before provider writes",
             jobs["manual-prerequisites"]["if"], "${{ true }}", "manual-prerequisites"),
            ("Check manual authority prerequisites before provider writes",
             "needs.recovery-reconciliation.outputs.admitted == 'true'",
             "needs.recovery-reconciliation.outputs.admitted != 'false'", "manual-prerequisites"),
            ("Resume the canonical Space without changing its allocation",
             "needs.manual-prerequisites.outputs.mode != 'managed-recovery'",
             "needs.manual-prerequisites.outputs.mode == 'managed-recovery'", "resume-paused-space"),
            ("Deploy, source-bind, and attest exact surface",
             "needs.durable-acquisition.result == 'success'",
             "needs.durable-acquisition.result == 'skipped'", "deploy"),
            ("Deploy, source-bind, and attest exact surface",
             "needs.manual-prerequisites.outputs.mode == 'managed-recovery'",
             "needs.manual-prerequisites.outputs.mode != 'managed-recovery'", "deploy"),
            ("Verify post-deploy configuration and bounded live proofs",
             "needs.durable-acquisition.result == 'success'",
             "(needs.durable-acquisition.result == 'success' || needs.durable-acquisition.result == 'skipped')",
             "runtime-config"),
            ("Verify post-deploy configuration and bounded live proofs",
             " && needs.durable-acquisition.result == 'success'", "", "runtime-config"),
        )
        for name, original, replacement, key in mutations:
            with self.subTest(job=key, replacement=replacement):
                target = job_block(self.workflow, name)
                self.assertIn(original, target)
                changed = self.workflow.replace(target, target.replace(original, replacement, 1), 1)
                with self.assertRaisesRegex(WorkflowContractError, "condition gate: " + key):
                    assert_manual_dependency_graph(changed)

    def test_duplicate_jobs_properties_and_step_ids_are_rejected(self) -> None:
        condition = "    if: " + assert_manual_dependency_graph(self.workflow)["manual-prerequisites"]["if"] + "\n"
        mutations = (
            ("  manual-prerequisites:\n", "  manual-prerequisites: {}\n  manual-prerequisites:\n", "duplicate mapping key: manual-prerequisites"),
            ("    needs: source-admission\n", "    needs: source-admission\n    needs: deploy\n", "duplicate mapping key: needs"),
            (condition, condition + "    if: always()\n", "duplicate mapping key: if"),
            ("        id: owner\n", "        id: owner\n        id: forged\n", "duplicate mapping key: id"),
            ("        id: source_artifact\n", "        id: owner\n", "duplicate step id: source-admission"),
        )
        for original, replacement, diagnostic in mutations:
            with self.subTest(diagnostic=diagnostic):
                self.assertIn(original, self.workflow)
                changed = self.workflow.replace(original, replacement, 1)
                with self.assertRaisesRegex(WorkflowContractError, re.escape(diagnostic)):
                    assert_manual_dependency_graph(changed)

    def test_new_jobs_missing_manual_job_and_failure_bypasses_require_review(self) -> None:
        cases = (
            (self.workflow + "\n  unreviewed-job:\n    runs-on: ubuntu-latest\n", "job set requires review"),
            (self.workflow.replace("  manual-prerequisites:\n", "  removed-prerequisites:\n", 1), "job set requires review"),
            (self.workflow.replace("  deploy:\n", "  deploy:\n    continue-on-error: true\n", 1), "job failure bypass: deploy"),
            (self.workflow.replace("  durable-acquisition:\n", "  durable-acquisition:\n    continue-on-error: true\n", 1), "job failure bypass: durable-acquisition"),
            (self.workflow.replace("  recovery-reconciliation:\n", "  recovery-reconciliation:\n    continue-on-error: true\n", 1), "job failure bypass: recovery-reconciliation"),
            (self.workflow.replace("      - name: Require main and classify current source ownership\n", "      - name: Require main and classify current source ownership\n        continue-on-error: true\n", 1), "step failure bypass: source-admission"),
            (self.workflow.replace("      - name: Classify the exact native candidate without admitting deployment\n", "      - name: Classify the exact native candidate without admitting deployment\n        continue-on-error: true\n", 1), "step failure bypass: manual-prerequisites"),
            (self.workflow.replace("      - name: Inspect the held prior acquisition without provider mutation\n", "      - name: Inspect the held prior acquisition without provider mutation\n        continue-on-error: true\n", 1), "step failure bypass: durable-acquisition"),
            (self.workflow.replace("      - name: Require the fixed inspection and unchanged absent private fence\n", "      - name: Require the fixed inspection and unchanged absent private fence\n        continue-on-error: true\n", 1), "step failure bypass: recovery-reconciliation"),
        )
        for changed, diagnostic in cases:
            with self.subTest(diagnostic=diagnostic), self.assertRaisesRegex(WorkflowContractError, re.escape(diagnostic)):
                assert_manual_dependency_graph(changed)

    def test_only_complete_reviewed_manual_step_shapes_can_tolerate_failure(self) -> None:
        document = workflow_document(self.workflow)
        admitted = [(name, step["name"]) for name, job in document["jobs"].items()
                    for step in job.get("steps", []) if "continue-on-error" in step]
        self.assertEqual(admitted, [
            ("manual-prerequisites", step["name"]) for step in REVIEWED_MANUAL_FAILURE_STEPS])
        manual = job_block(self.workflow, "Check manual authority prerequisites before provider writes")
        for reviewed in REVIEWED_MANUAL_FAILURE_STEPS:
            original = step_block(manual, reviewed["name"])
            replacements = (
                original.replace("continue-on-error: true", "continue-on-error: false", 1),
                original.replace("continue-on-error: true", "continue-on-error: 'true'", 1),
                original.replace("        run: >-\n", "        env:\n          HF_TOKEN: unreviewed\n        run: >-\n", 1),
                original.replace("python -B scripts/", "python -B unreviewed/", 1),
                original.replace("id: " + reviewed["id"], "id: unreviewed", 1),
            )
            for replacement in replacements:
                with self.subTest(step=reviewed["id"], replacement=replacement):
                    self.assertNotEqual(original, replacement)
                    changed = self.workflow.replace(original, replacement, 1)
                    with self.assertRaisesRegex(WorkflowContractError, "step failure bypass: manual-prerequisites"):
                        assert_manual_dependency_graph(changed)
        original = step_block(manual, REVIEWED_MANUAL_FAILURE_STEPS[0]["name"])
        marker = "      - name: Inspect the held prior acquisition without provider mutation\n"
        changed = self.workflow.replace(marker, original + "\n" + marker, 1)
        with self.assertRaisesRegex(WorkflowContractError, "step failure bypass: durable-acquisition"):
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
