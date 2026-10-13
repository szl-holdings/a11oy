#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Atelier must not write Hub repos that a kernel repo's own publisher owns.

Each converged kernel repo on GitHub runs its own hf-kernel-publish.yml. That
workflow is the single writer of the kernel surface kernels/SZLHOLDINGS/<n> and
of the model twin SZLHOLDINGS/<n>, where it writes a pointer README and prunes
code files. A copy of an organ source pushed from a11oy re-adds what that
publisher removed, so a11oy may not target those ids at all.

Stdlib only. The atelier publish job runs this file before it uploads anything.
"""

from __future__ import annotations

import ast
import importlib.util
import re
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
ATELIER_WORKFLOW = WORKFLOWS / "atelier-hub-publish.yml"
SINGLE_WRITER_TEST = ROOT / "tests" / "test_hf_single_writer.py"
HUB_OWNER = "SZLHOLDINGS"

# GitHub repo szl-holdings/<n> owns Hub kernels/SZLHOLDINGS/<n> and
# SZLHOLDINGS/<n> through its own .github/workflows/hf-kernel-publish.yml.
CONVERGED_KERNEL_REPOS = frozenset(
    {
        "szl-kernels",
        "szl-invariants",
        "szl-govsign",
        "szl-maskmod",
        "szl-receipt-attn",
        "szl-blocked",
        "szl-ouroboros",
        "szl-provctl",
        "szl-block-kv",
        "YARQA-ATTN",
        "szl-lambda-gate",
    }
)

# What atelier still publishes. Removing a converged kernel must not drop any
# of these; adding a target is a deliberate change to this contract.
EXPECTED_ATELIER_TARGETS = frozenset(
    f"{HUB_OWNER}/{name}"
    for name in (
        "szl-atelier",
        "MiniEmbed-Nano",
        "Moons-Nano",
        "TinyKhipu-Nano",
        "ReceiptAgent-Nano",
        "szl-khipu",
        "WILLAY",
        "chaski",
        "chaski-5050",
        "chaski-r2",
        "qantu",
        "waman",
        "chakana",
        "tinku",
        "szl-khipu-kernels",
        "szl-governed-norm",
        "szl-nemo",
        "szl-training-scripts",
    )
)

# Hub writers outside atelier that still name a converged twin. Each is pinned
# to the delete-only shape asserted below; retiring it belongs to its own lane.
KNOWN_DELETE_ONLY_QUARANTINE = frozenset(
    {
        "hub-joblib-estate-quarantine.yml",
        "hub-joblib-estate-merge.yml",
    }
)
QUARANTINE_SCRIPTS = (
    "scripts/hub_quarantine_joblib_estate.py",
    "scripts/hub_merge_joblib_quarantine_prs.py",
)

HUB_WRITE_METHODS = frozenset(
    {
        "create_commit",
        "upload_file",
        "upload_folder",
        "upload_large_folder",
        "delete_file",
        "delete_files",
        "delete_folder",
        "create_branch",
        "delete_branch",
        "create_tag",
        "delete_tag",
        "merge_pull_request",
        "create_pull_request",
        "move_repo",
        "delete_repo",
        "update_repo_settings",
        "update_repo_visibility",
        "super_squash_history",
    }
)
HUB_WRITE_PATTERNS = (
    re.compile(
        r"\.\s*(?:" + "|".join(sorted(HUB_WRITE_METHODS)) + r")\s*\(",
        re.IGNORECASE,
    ),
    re.compile(r"\bgit\b[^\n]*\bpush\b", re.IGNORECASE),
)


def _repo_pattern(names) -> re.Pattern[str]:
    alternatives = "|".join(re.escape(name) for name in sorted(names))
    return re.compile(
        rf"(?<![\w.-]){HUB_OWNER}/(?:{alternatives})(?![\w.-])",
        re.IGNORECASE,
    )


CONVERGED_ID = _repo_pattern(CONVERGED_KERNEL_REPOS)


def _executable_lines(text: str) -> str:
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    )


def inline_publisher(text: str) -> str:
    """Return the python heredoc the publish step executes."""

    match = re.search(
        r"(?m)^(?P<indent>[ \t]*)python - <<'PY'\n(?P<body>.*?)^(?P=indent)PY[ \t]*$",
        text,
        re.DOTALL,
    )
    if match is None:
        raise AssertionError("atelier publish step has no python heredoc")
    return textwrap.dedent(match.group("body"))


def _loop_bindings(tree: ast.AST) -> dict[int, list[str]]:
    """Map a Name node id to the literal strings a for loop binds it to."""

    bound: dict[int, list[str]] = {}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.For) and isinstance(node.target, ast.Name)):
            continue
        if not isinstance(node.iter, (ast.Tuple, ast.List)):
            continue
        values = [
            element.value
            for element in node.iter.elts
            if isinstance(element, ast.Constant) and type(element.value) is str
        ]
        if len(values) != len(node.iter.elts):
            continue
        for inner in ast.walk(node):
            if isinstance(inner, ast.Name) and inner.id == node.target.id:
                bound[id(inner)] = values
    return bound


def publisher_targets(source: str) -> set[str]:
    """Every Hub repo id the inline publisher can name, failing closed."""

    tree = ast.parse(source)
    bindings = _loop_bindings(tree)
    targets: set[str] = set()
    full_id = re.compile(rf"{HUB_OWNER}/[A-Za-z0-9._-]+")
    fstring_parts: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.JoinedStr):
            continue
        head = node.values[0] if node.values else None
        if not (
            isinstance(head, ast.Constant)
            and type(head.value) is str
            and head.value.startswith(f"{HUB_OWNER}/")
        ):
            continue
        fstring_parts.update(id(part) for part in node.values)
        tail = node.values[1:]
        if (
            head.value != f"{HUB_OWNER}/"
            or len(tail) != 1
            or not isinstance(tail[0], ast.FormattedValue)
            or not isinstance(tail[0].value, ast.Name)
            or id(tail[0].value) not in bindings
        ):
            raise AssertionError("a Hub repo id is built from an unbounded value")
        targets.update(f"{HUB_OWNER}/{name}" for name in bindings[id(tail[0].value)])
    for node in ast.walk(tree):
        if id(node) in fstring_parts:
            continue
        if isinstance(node, ast.Constant) and type(node.value) is str:
            # Over-approximate: any id named anywhere, even in a log line, counts.
            targets.update(full_id.findall(node.value))
        elif isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Mod)):
            for side in (node.left, node.right):
                if (
                    isinstance(side, ast.Constant)
                    and type(side.value) is str
                    and HUB_OWNER in side.value
                ):
                    raise AssertionError("a Hub repo id is built by concatenation")
    return targets


def _load_single_writer_analyzer():
    """Private copy of the Space single-writer analyzer, retargeted here."""

    spec = importlib.util.spec_from_file_location(
        "_atelier_kernel_writer_analyzer", SINGLE_WRITER_TEST
    )
    if spec is None or spec.loader is None:
        raise AssertionError("single-writer analyzer is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.TARGET_MARKERS = tuple(
        f"{HUB_OWNER}/{name}" for name in sorted(CONVERGED_KERNEL_REPOS)
    )
    module.MUTATION_METHODS = set(HUB_WRITE_METHODS)
    module.MUTATION_PATTERNS = HUB_WRITE_PATTERNS
    return module


def converged_kernel_writers(workflows: dict[str, str], repo_files=None) -> list[str]:
    """Workflows, manual or automatic, whose executed sources write a converged id."""

    analyzer = _load_single_writer_analyzer()
    return sorted(
        name
        for name, text in workflows.items()
        if analyzer._mutates_canonical_space(text, repo_files)
    )


class AtelierPublisherTargetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workflow = ATELIER_WORKFLOW.read_text(encoding="utf-8")
        self.source = inline_publisher(self.workflow)

    def test_inline_publisher_parses(self) -> None:
        compile(self.source, str(ATELIER_WORKFLOW), "exec")

    def test_no_converged_kernel_repo_is_a_target(self) -> None:
        targets = {target.lower() for target in publisher_targets(self.source)}
        converged = {f"{HUB_OWNER}/{name}".lower() for name in CONVERGED_KERNEL_REPOS}
        self.assertEqual(targets & converged, set())

    def test_no_converged_kernel_id_in_executed_workflow_text(self) -> None:
        self.assertEqual(CONVERGED_ID.findall(_executable_lines(self.workflow)), [])

    def test_no_kernel_surface_is_written(self) -> None:
        tree = ast.parse(self.source)
        for node in ast.walk(tree):
            if isinstance(node, ast.keyword) and node.arg == "repo_type":
                self.assertIsInstance(node.value, ast.Constant)
                self.assertIn(node.value.value, {"model", "space"})
        self.assertNotRegex(self.source, r"huggingface\.co/kernels/")

    def test_remaining_atelier_targets_are_intact(self) -> None:
        self.assertEqual(publisher_targets(self.source), set(EXPECTED_ATELIER_TARGETS))

    def test_kernel_pack_still_carries_every_organ(self) -> None:
        # The organ sources still ship, in the khipu kernel pack only.
        self.assertIn('kdir.glob("*.py")', self.source)
        self.assertIn('path_in_repo=f"kernels/{pth.name}"', self.source)
        self.assertIn(f'repo_id="{HUB_OWNER}/szl-khipu-kernels"', self.source)

    def test_publish_step_runs_this_contract_first(self) -> None:
        guard = "run: python3 a11oy-src/tests/test_atelier_hub_publish_contract.py"
        self.assertTrue(guard in self.workflow, "publish job does not run the contract")
        self.assertLess(
            self.workflow.index(guard),
            self.workflow.index("python - <<'PY'"),
        )


class TargetExtractionTests(unittest.TestCase):
    def test_converged_tuple_target_is_caught(self) -> None:
        source = (
            'per = [("SZLHOLDINGS/YARQA-ATTN", "yarqa.py")]\n'
            "for repo, name in per:\n"
            "    api.upload_file(path_or_fileobj=name, path_in_repo=name,"
            ' repo_id=repo, repo_type="model")\n'
        )
        self.assertIn("SZLHOLDINGS/YARQA-ATTN", publisher_targets(source))

    def test_id_inside_a_larger_string_still_counts(self) -> None:
        self.assertEqual(
            publisher_targets('print("published SZLHOLDINGS/szl-block-kv chain.py")\n'),
            {"SZLHOLDINGS/szl-block-kv"},
        )

    def test_loop_fstring_targets_are_resolved(self) -> None:
        source = (
            'for name in ("qantu", "szl-maskmod"):\n'
            '    repo = f"SZLHOLDINGS/{name}"\n'
        )
        self.assertEqual(
            publisher_targets(source),
            {"SZLHOLDINGS/qantu", "SZLHOLDINGS/szl-maskmod"},
        )

    def test_unbounded_repo_construction_fails_closed(self) -> None:
        sources = (
            'repo = f"SZLHOLDINGS/{choose()}"\n',
            'repo = "SZLHOLDINGS/" + name\n',
            'repo = "SZLHOLDINGS/%s" % name\n',
            'repo = f"SZLHOLDINGS/{name}-mirror"\n',
            'for name in names:\n    repo = f"SZLHOLDINGS/{name}"\n',
        )
        for source in sources:
            with self.subTest(source=source), self.assertRaises(AssertionError):
                publisher_targets(source)

    def test_converged_id_pattern_is_exact(self) -> None:
        self.assertTrue(CONVERGED_ID.search('repo_id="SZLHOLDINGS/szl-maskmod"'))
        self.assertTrue(CONVERGED_ID.search("kernels/szlholdings/yarqa-attn"))
        self.assertFalse(CONVERGED_ID.search('"SZLHOLDINGS/szl-khipu-kernels"'))
        self.assertFalse(CONVERGED_ID.search('"SZLHOLDINGS/szl-kernels-extra"'))
        self.assertFalse(CONVERGED_ID.search("szl-holdings/szl-maskmod"))


class EstateConvergedKernelWriterTests(unittest.TestCase):
    def test_no_new_writer_of_a_converged_kernel_repo(self) -> None:
        workflows = {
            path.name: path.read_text(encoding="utf-8")
            for path in WORKFLOWS.iterdir()
            if path.is_file() and path.suffix.lower() in {".yml", ".yaml"}
        }
        writers = converged_kernel_writers(workflows)
        self.assertNotIn(ATELIER_WORKFLOW.name, writers)
        self.assertLessEqual(set(writers), set(KNOWN_DELETE_ONLY_QUARANTINE))

    def test_known_quarantine_writers_stay_delete_only(self) -> None:
        for relative in QUARANTINE_SCRIPTS:
            path = ROOT / relative
            if not path.is_file():
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            assigned = {
                target.id: node.value
                for node in ast.walk(tree)
                if isinstance(node, ast.Assign)
                for target in node.targets
                if isinstance(target, ast.Name)
            }
            joblib = assigned.get("JOBLIB_PATH")
            self.assertIsInstance(joblib, ast.Constant, relative)
            self.assertEqual(joblib.value, "model.joblib", relative)
            for node in ast.walk(tree):
                if not (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr in HUB_WRITE_METHODS
                ):
                    continue
                with self.subTest(script=relative, call=node.func.attr):
                    self.assertIn(node.func.attr, {"create_commit", "merge_pull_request"})
                if node.func.attr != "create_commit":
                    continue
                keywords = {keyword.arg: keyword.value for keyword in node.keywords}
                self.assertIsInstance(keywords.get("create_pr"), ast.Constant, relative)
                self.assertIs(keywords["create_pr"].value, True, relative)
                operations = keywords.get("operations")
                self.assertIsInstance(operations, ast.List, relative)
                for operation in operations.elts:
                    self.assertIsInstance(operation, ast.Call, relative)
                    self.assertEqual(ast.unparse(operation.func), "CommitOperationDelete")
                    self.assertEqual(
                        [ast.unparse(keyword.value) for keyword in operation.keywords],
                        ["JOBLIB_PATH"],
                    )

    def test_detector_flags_an_atelier_style_kernel_copy(self) -> None:
        workflow = """name: copy organ to converged twin
on: workflow_dispatch
jobs:
  publish:
    steps:
      - run: |
          python - <<'PY'
          api.upload_file(path_or_fileobj="yarqa.py", path_in_repo="yarqa.py",
                          repo_id="SZLHOLDINGS/YARQA-ATTN", repo_type="model")
          PY
"""
        delegated = """name: delegated git push
on:
  schedule:
    - cron: "0 * * * *"
jobs:
  publish:
    steps:
      - run: bash scripts/push_kernel.sh
"""
        repo_files = {
            "scripts/push_kernel.sh": (
                "git push https://huggingface.co/kernels/SZLHOLDINGS/szl-block-kv main\n"
            ),
        }
        self.assertEqual(
            converged_kernel_writers(
                {"copy.yml": workflow, "push.yml": delegated, "other.yml": "name: x\n"},
                repo_files,
            ),
            ["copy.yml", "push.yml"],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
