#!/usr/bin/env python3
"""Lock the canonical A11oy Space to one automatic deployment writer."""

from __future__ import annotations

import ast
import json
import re
import shlex
import tempfile
import unittest
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
CANONICAL_WORKFLOW = "hf-sync.yml"
RETIRED_WORKFLOWS = {
    "hf-sync-backend.yml",
    "hf-git-sha-sync.yml",
}
WORKFLOW_SUFFIXES = {".yml", ".yaml"}
MAX_REFERENCED_SOURCES = 256
MAX_REFERENCE_DEPTH = 16
TARGET_MARKERS = (
    "SZLHOLDINGS/a11oy",
    "szlholdings-a11oy.hf.space",
)
MUTATION_PATTERNS = (
    re.compile(r"reusable-hf-deploy\.ya?ml", re.IGNORECASE),
    re.compile(
        r"\.\s*(?:create_commit|upload_file|upload_folder|"
        r"add_space_variable|set_space_variable|delete_space_variable|"
        r"add_space_secret|set_space_secret|delete_space_secret|"
        r"restart_space)\s*\(",
        re.IGNORECASE,
    ),
)
MUTATION_METHODS = {
    "create_commit",
    "upload_file",
    "upload_folder",
    "add_space_variable",
    "set_space_variable",
    "delete_space_variable",
    "add_space_secret",
    "set_space_secret",
    "delete_space_secret",
    "restart_space",
}
_INTERPRETER_EXECUTABLE_PATH = (
    r"(?P<path>(?:\./)?(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+"
    r"(?:\.(?:py|sh|js|mjs|cjs|ts))?)"
)
_DIRECT_EXECUTABLE_PATH = (
    r"(?P<path>(?:\./|(?:[A-Za-z0-9_.-]+/)+)"
    r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*)"
)
LOCAL_SCRIPT_CALL = re.compile(
    r"(?:^|[ \t])(?:"
    r"python(?:3(?:\.\d+)?)?(?:[ \t]+-[A-Za-z]+)*|bash|sh|node"
    r")"
    r"(?![ \t]+-(?:c|e|m)(?:[ \t]|$))"
    r"[ \t]+"
    + _INTERPRETER_EXECUTABLE_PATH,
    re.MULTILINE,
)
LOCAL_MODULE_CALL = re.compile(
    r"\bpython(?:3(?:\.\d+)?)?\b"
    r"(?:(?:[ \t]+(?!-m(?:[ \t]|$))[^ \t;&|]+))*"
    r"[ \t]+-m[ \t]+"
    r"(?P<module>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)"
)
DIRECT_SCRIPT_CALL = re.compile(
    r"(?m)^\s*(?:(?:-\s*)?run:\s*(?:[|>-]\s*)?|(?=\./))"
    + _DIRECT_EXECUTABLE_PATH
    + r"(?=\s|$)"
)
LOCAL_ACTION_CALL = re.compile(
    r"(?m)^\s*(?:-\s*)?uses:\s*[\"']?\./(?P<path>[^#\s\"']+)"
)
ACTION_ENTRYPOINT = re.compile(
    r"(?m)^\s*(?:main|pre|post):\s*[\"']?"
    r"(?P<path>[^#\s\"']+\.(?:py|sh|js|mjs|cjs|ts))"
)
ACTION_DOCKER_IMAGE = re.compile(
    r"(?m)^\s*image:\s*[\"']?"
    r"(?P<path>(?!docker://)[^#\s\"']+)[\"']?\s*(?:#.*)?$"
)
WORKING_DIRECTORY = re.compile(
    r"(?m)^\s*working-directory:\s*(?P<path>.+?)\s*$"
)


def _on_block(text: str) -> str:
    """Return the top-level workflow trigger declaration."""

    lines = text.splitlines()
    for index, line in enumerate(lines):
        if re.fullmatch(r"on:\s*.*", line):
            block = [line]
            for nested in lines[index + 1 :]:
                if nested and not nested.startswith((" ", "\t", "#")):
                    break
                block.append(nested)
            return "\n".join(block)
    return ""


def _trigger_events(text: str) -> set[str]:
    """Parse top-level trigger names without requiring a YAML dependency."""

    block = _on_block(text)
    if not block:
        return set()

    first_line, *nested = block.splitlines()
    inline = first_line.partition(":")[2].strip()
    if inline:
        if inline.startswith("[") and inline.endswith("]"):
            inline = inline[1:-1]
            return {
                event.strip().strip("'\"")
                for event in inline.split(",")
                if event.strip()
            }
        return {inline.strip("'\"")}

    entries = [
        (len(match.group("indent")), match.group("name"))
        for line in nested
        if (
            match := re.fullmatch(
                r"(?P<indent> +)(?P<name>[A-Za-z_][\w-]*):.*",
                line,
            )
        )
    ]
    if not entries:
        return set()
    event_indent = min(indent for indent, _ in entries)
    return {
        name
        for indent, name in entries
        if indent == event_indent
    }


def _has_automatic_trigger(text: str) -> bool:
    """Treat every trigger except workflow_dispatch as automatic."""

    return bool(_trigger_events(text) - {"workflow_dispatch"})


def _has_main_push(text: str) -> bool:
    """Return true only for a top-level on.push event targeting main."""

    lines = text.splitlines()
    push_index: int | None = None
    for index, line in enumerate(lines):
        if re.fullmatch(r" {2}push:\s*(?:\{\})?\s*", line):
            push_index = index
            break
    if push_index is None:
        return False

    push_block: list[str] = []
    for line in lines[push_index + 1 :]:
        if line and not line.startswith((" ", "\t", "#")):
            break
        if re.match(r" {2}\S", line):
            break
        push_block.append(line)
    block = "\n".join(push_block)
    return not block.strip() or bool(
        re.search(r"(?m)^\s{4,}branches:\s*(?:\[main\]|.*\bmain\b)", block)
    )


def _executable_text(text: str) -> str:
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    )


def _working_directories(text: str) -> set[str]:
    """Return every bounded static run directory used by a workflow."""

    directories = {""}
    for match in WORKING_DIRECTORY.finditer(text):
        raw_value = match.group("path")
        if "${{" in raw_value:
            raise RuntimeError("dynamic working-directory cannot be bounded")
        try:
            tokens = shlex.split(raw_value, comments=True, posix=True)
        except ValueError as exc:
            raise RuntimeError("working-directory cannot be bounded") from exc
        if len(tokens) != 1:
            raise RuntimeError("working-directory cannot be bounded")
        raw_path = tokens[0]
        path = PurePosixPath(raw_path.replace("\\", "/"))
        if path.is_absolute() or ".." in path.parts:
            raise RuntimeError("working-directory escapes the repository")
        directories.add(path.as_posix().removeprefix("./"))
    return directories


def _docker_local_sources(text: str) -> set[str]:
    """Return bounded local COPY/ADD inputs from a Docker action image."""

    sources: set[str] = set()
    for raw_line in text.splitlines():
        match = re.match(r"^\s*(?:COPY|ADD)\s+(?P<spec>.+?)\s*$", raw_line, re.I)
        if match is None:
            continue
        spec = match.group("spec")
        try:
            if spec.startswith("["):
                values = json.loads(spec)
                if not isinstance(values, list) or len(values) < 2:
                    raise ValueError("invalid JSON-form COPY/ADD")
                tokens = [str(value) for value in values]
            else:
                tokens = shlex.split(spec, comments=True, posix=True)
                copied_from_stage = False
                while tokens and tokens[0].startswith("--"):
                    option = tokens.pop(0)
                    if option == "--from":
                        if not tokens:
                            raise RuntimeError(
                                "Docker action COPY --from is incomplete"
                            )
                        tokens.pop(0)
                        copied_from_stage = True
                    elif option.startswith("--from="):
                        copied_from_stage = True
                if copied_from_stage:
                    continue
        except (ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError("Docker action COPY/ADD cannot be bounded") from exc
        if len(tokens) < 2:
            raise RuntimeError("Docker action COPY/ADD cannot be bounded")
        for source in tokens[:-1]:
            normalized = source.replace("\\", "/")
            if (
                normalized in {".", "./"}
                or any(character in normalized for character in "*?[")
                or re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://", normalized)
            ):
                raise RuntimeError("Docker action COPY/ADD source cannot be bounded")
            sources.add(normalized)
    return sources


def _repo_source(
    relative_path: str,
    repo_files: dict[str, str] | None,
    *,
    base_dir: str = "",
) -> tuple[str, str] | None:
    candidate = PurePosixPath(relative_path.replace("\\", "/"))
    if candidate.is_absolute() or ".." in candidate.parts:
        return None
    candidate = PurePosixPath(base_dir) / candidate
    normalized = candidate.as_posix().removeprefix("./")
    parts = PurePosixPath(normalized).parts
    if not parts or ".." in parts:
        return None

    if repo_files is not None:
        text = repo_files.get(normalized)
        return (normalized, text) if text is not None else None

    path = ROOT.joinpath(*parts).resolve()
    try:
        path.relative_to(ROOT.resolve())
    except ValueError:
        return None
    if not path.is_file():
        return None
    return normalized, path.read_text(encoding="utf-8")


def _referenced_sources(
    text: str,
    repo_files: dict[str, str] | None = None,
) -> list[tuple[str | None, str]]:
    """Include scripts and local actions that the workflow actually executes."""

    combined: list[tuple[str | None, str]] = [(None, text)]
    queue: list[tuple[str | None, str, int]] = [(None, text, 0)]
    visited: set[str] = set()
    while queue:
        current_path, source_text, depth = queue.pop()
        if depth > MAX_REFERENCE_DEPTH:
            raise RuntimeError("local writer reference depth is unbounded")
        current = _executable_text(source_text)
        direct_calls = {
            match.group("path") for match in DIRECT_SCRIPT_CALL.finditer(current)
        }
        script_calls = {
            match.group("path") for match in LOCAL_SCRIPT_CALL.finditer(current)
        }
        module_calls = {
            match.group("module") for match in LOCAL_MODULE_CALL.finditer(current)
        }
        is_yaml_execution_context = (
            current_path is None
            or PurePosixPath(current_path).name in {"action.yml", "action.yaml"}
        )
        working_directories = (
            _working_directories(current)
            if is_yaml_execution_context
            and (script_calls or direct_calls or module_calls)
            else {""}
        )
        references: set[tuple[str, str, bool]] = set()
        for relative_path in script_calls | direct_calls:
            references.update(
                (relative_path, base_dir, False)
                for base_dir in working_directories
            )
        for module in module_calls:
            module_path = module.replace(".", "/")
            references.update(
                (relative_path, base_dir, False)
                for base_dir in working_directories
                for relative_path in (
                    f"{module_path}.py",
                    f"{module_path}/__main__.py",
                )
            )

        for match in LOCAL_ACTION_CALL.finditer(current):
            action_dir = match.group("path").rstrip("/")
            references.update(
                {
                    (f"{action_dir}/action.yml", "", False),
                    (f"{action_dir}/action.yaml", "", False),
                }
            )

        if (
            current_path is not None
            and PurePosixPath(current_path).name in {"action.yml", "action.yaml"}
            and re.search(r"(?m)^\s*(?:runs:|using:)", current)
        ):
            action_dir = PurePosixPath(current_path).parent.as_posix()
            references.update(
                (match.group("path"), action_dir, True)
                for match in ACTION_ENTRYPOINT.finditer(current)
            )
            references.update(
                (match.group("path"), action_dir, True)
                for match in ACTION_DOCKER_IMAGE.finditer(current)
            )

        if (
            current_path is not None
            and PurePosixPath(current_path).name.lower().startswith("dockerfile")
        ):
            docker_dir = PurePosixPath(current_path).parent.as_posix()
            references.update(
                (relative_path, docker_dir, True)
                for relative_path in _docker_local_sources(current)
            )

        for relative_path, base_dir, required in sorted(references):
            source = _repo_source(
                relative_path,
                repo_files,
                base_dir=base_dir,
            )
            if source is None:
                if required:
                    raise RuntimeError(
                        f"required local writer source is unavailable: {relative_path}"
                    )
                continue
            normalized, source_text = source
            if normalized in visited:
                continue
            if len(visited) >= MAX_REFERENCED_SOURCES:
                raise RuntimeError("too many local writer references")
            visited.add(normalized)
            combined.append((normalized, source_text))
            queue.append((normalized, source_text, depth + 1))
    return combined


def _python_mutates_space(text: str) -> bool:
    """Find real Python API calls while ignoring marker strings in tests."""

    try:
        tree = ast.parse(text)
    except SyntaxError:
        return any(pattern.search(text) for pattern in MUTATION_PATTERNS)
    return any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in MUTATION_METHODS
        for node in ast.walk(tree)
    )


def _mutates_canonical_space(
    text: str,
    repo_files: dict[str, str] | None = None,
) -> bool:
    sources = _referenced_sources(text, repo_files)
    lowered = "\n".join(source_text for _, source_text in sources).lower()
    mutation_found = False
    for relative_path, source_text in sources:
        executable = _executable_text(source_text)
        if relative_path is not None and relative_path.lower().endswith(".py"):
            mutation_found = _python_mutates_space(source_text)
        else:
            mutation_found = any(
                pattern.search(executable) for pattern in MUTATION_PATTERNS
            )
        if mutation_found:
            break
    return (
        any(marker.lower() in lowered for marker in TARGET_MARKERS)
        and mutation_found
    )


def find_automatic_writers(
    workflows: dict[str, str],
    repo_files: dict[str, str] | None = None,
) -> list[str]:
    """Find automatically triggered workflows that can mutate the Space."""

    return sorted(
        name
        for name, text in workflows.items()
        if _has_automatic_trigger(text)
        and _mutates_canonical_space(text, repo_files)
    )


def load_workflows(directory: Path = WORKFLOWS) -> dict[str, str]:
    """Load both workflow extensions supported by GitHub Actions."""

    return {
        path.name: path.read_text(encoding="utf-8")
        for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in WORKFLOW_SUFFIXES
    }


class HuggingFaceSingleWriterTests(unittest.TestCase):
    def test_only_canonical_automatic_writer_exists(self) -> None:
        workflows = load_workflows()
        self.assertEqual(find_automatic_writers(workflows), [CANONICAL_WORKFLOW])
        self.assertTrue(RETIRED_WORKFLOWS.isdisjoint(workflows))

        general_suite = workflows["tests.yml"]
        self.assertTrue(
            {"push", "pull_request"}.issubset(_trigger_events(general_suite))
        )
        self.assertNotIn("paths:", _on_block(general_suite))
        self.assertIn(
            "run: python3 tests/test_hf_single_writer.py",
            general_suite,
        )

    def test_loader_includes_yml_and_yaml_workflows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            (directory / "one.yml").write_text("name: one\n", encoding="utf-8")
            (directory / "two.yaml").write_text("name: two\n", encoding="utf-8")
            (directory / "ignored.txt").write_text("not a workflow\n", encoding="utf-8")
            self.assertEqual(set(load_workflows(directory)), {"one.yml", "two.yaml"})

    def test_trigger_parser_accepts_consistent_nonstandard_indentation(self) -> None:
        workflow = """
name: indented
on:
    schedule:
        - cron: "0 * * * *"
    workflow_dispatch: {}
jobs: {}
"""
        self.assertEqual(
            _trigger_events(workflow),
            {"schedule", "workflow_dispatch"},
        )
        self.assertTrue(_has_automatic_trigger(workflow))

    def test_canonical_writer_is_serialized_and_source_bound(self) -> None:
        text = (WORKFLOWS / CANONICAL_WORKFLOW).read_text(encoding="utf-8")
        self.assertTrue(_has_main_push(text))
        self.assertIn("group: sync-relock-canonical-a11oy", text)
        self.assertIn("cancel-in-progress: false", text)
        self.assertIn("ref: ${{ github.sha }}", text)
        self.assertIn("source-revision-variable: SZL_GIT_SHA", text)
        self.assertRegex(text, r"(?s)runtime-config:.*?needs:\s*deploy")

    def test_all_non_manual_triggers_detect_delegated_writer(self) -> None:
        canonical = (WORKFLOWS / CANONICAL_WORKFLOW).read_text(encoding="utf-8")
        competing = """
name: unsafe duplicate
on:
  schedule:
    - cron: "0 * * * *"
jobs:
  mutate:
    steps:
      - run: python3 .github/scripts/unsafe_hf_writer.py
        env:
          SPACE_ID: SZLHOLDINGS/a11oy
"""
        manual = """
name: manual recovery
on: workflow_dispatch
jobs:
  mutate:
    steps:
      - run: python3 .github/scripts/unsafe_hf_writer.py
        env:
          SPACE_ID: SZLHOLDINGS/a11oy
"""
        repo_files = {
            ".github/scripts/unsafe_hf_writer.py": (
                "from huggingface_hub import HfApi\n"
                "HfApi().create_commit(repo_id='target', operations=[])\n"
            )
        }
        self.assertEqual(
            find_automatic_writers(
                {
                    CANONICAL_WORKFLOW: canonical,
                    "unsafe-duplicate.yaml": competing,
                    "manual-recovery.yml": manual,
                },
                repo_files,
            ),
            [CANONICAL_WORKFLOW, "unsafe-duplicate.yaml"],
        )

    def test_repo_local_python_module_writer_is_detected(self) -> None:
        canonical = (WORKFLOWS / CANONICAL_WORKFLOW).read_text(encoding="utf-8")
        competing = """
name: unsafe module writer
on:
    schedule:
        - cron: "0 * * * *"
jobs:
    mutate:
        steps:
            - run: python3.12 -W error -X dev -m scripts.hf_writer
              env:
                  SPACE_ID: SZLHOLDINGS/a11oy
"""
        repo_files = {
            "scripts/hf_writer.py": (
                "from huggingface_hub import HfApi\n"
                "HfApi().create_commit(repo_id='target', operations=[])\n"
            )
        }
        self.assertEqual(
            find_automatic_writers(
                {
                    CANONICAL_WORKFLOW: canonical,
                    "unsafe-module.yaml": competing,
                },
                repo_files,
            ),
            [CANONICAL_WORKFLOW, "unsafe-module.yaml"],
        )

    def test_secret_only_writer_is_detected(self) -> None:
        canonical = (WORKFLOWS / CANONICAL_WORKFLOW).read_text(encoding="utf-8")
        competing = """
name: unsafe secret writer
on:
  schedule:
    - cron: "0 * * * *"
jobs:
  mutate:
    steps:
      - run: python3 scripts/hf_secret_writer.py
        env:
          SPACE_ID: SZLHOLDINGS/a11oy
"""
        repo_files = {
            "scripts/hf_secret_writer.py": (
                "from huggingface_hub import HfApi\n"
                "HfApi().add_space_secret("
                "repo_id='target', key='K', value='digest')\n"
            )
        }
        self.assertEqual(
            find_automatic_writers(
                {
                    CANONICAL_WORKFLOW: canonical,
                    "unsafe-secret.yaml": competing,
                },
                repo_files,
            ),
            [CANONICAL_WORKFLOW, "unsafe-secret.yaml"],
        )

    def test_local_action_entrypoint_and_direct_script_are_resolved(self) -> None:
        canonical = (WORKFLOWS / CANONICAL_WORKFLOW).read_text(encoding="utf-8")
        local_action = """
name: unsafe local action
on:
  schedule:
    - cron: "0 * * * *"
jobs:
  mutate:
    env:
      SPACE_ID: SZLHOLDINGS/a11oy
    steps:
      - uses: ./.github/actions/unsafe
"""
        direct_script = """
name: unsafe direct script
on:
  workflow_run:
    workflows: [upstream]
    types: [completed]
jobs:
  mutate:
    env:
      SPACE_ID: SZLHOLDINGS/a11oy
    steps:
      - run: ./.github/scripts/unsafe.sh
"""
        repo_files = {
            ".github/actions/unsafe/action.yml": (
                "runs:\n"
                "  using: node20\n"
                "  main: dist/index.js\n"
            ),
            ".github/actions/unsafe/dist/index.js": (
                "client.upload_folder({repo_id: process.env.SPACE_ID})\n"
            ),
            ".github/scripts/unsafe.sh": (
                "python -c 'HfApi().create_commit("
                "repo_id=\"target\", operations=[])'\n"
            ),
        }
        self.assertEqual(
            find_automatic_writers(
                {
                    CANONICAL_WORKFLOW: canonical,
                    "unsafe-action.yaml": local_action,
                    "unsafe-script.yml": direct_script,
                },
                repo_files,
            ),
            [
                CANONICAL_WORKFLOW,
                "unsafe-action.yaml",
                "unsafe-script.yml",
            ],
        )

    def test_extensionless_writer_honors_static_working_directory(self) -> None:
        canonical = (WORKFLOWS / CANONICAL_WORKFLOW).read_text(encoding="utf-8")
        competing = """
name: unsafe extensionless writer
on:
  schedule:
    - cron: "0 * * * *"
jobs:
  mutate:
    defaults:
      run:
        working-directory: tools/deploy
    env:
      SPACE_ID: SZLHOLDINGS/a11oy
    steps:
      - run: ./publish
"""
        interpreter_competing = """
name: unsafe interpreter extensionless writer
on:
  schedule:
    - cron: "0 * * * *"
jobs:
  mutate:
    defaults:
      run:
        working-directory: tools/deploy
    env:
      SPACE_ID: SZLHOLDINGS/a11oy
    steps:
      - run: python publish
"""
        repo_files = {
            "tools/deploy/publish": (
                "client.upload_folder({repo_id: process.env.SPACE_ID})\n"
            ),
        }
        self.assertEqual(
            find_automatic_writers(
                {
                    CANONICAL_WORKFLOW: canonical,
                    "unsafe-extensionless.yml": competing,
                    "unsafe-interpreter-extensionless.yml": (
                        interpreter_competing
                    ),
                },
                repo_files,
            ),
            [
                CANONICAL_WORKFLOW,
                "unsafe-extensionless.yml",
                "unsafe-interpreter-extensionless.yml",
            ],
        )

    def test_local_docker_action_sources_are_resolved(self) -> None:
        canonical = (WORKFLOWS / CANONICAL_WORKFLOW).read_text(encoding="utf-8")
        competing = """
name: unsafe Docker action
on:
  schedule:
    - cron: "0 * * * *"
jobs:
  mutate:
    env:
      SPACE_ID: SZLHOLDINGS/a11oy
    steps:
      - uses: ./.github/actions/docker-writer
"""
        repo_files = {
            ".github/actions/docker-writer/action.yml": (
                "runs:\n"
                "  using: docker\n"
                "  image: Dockerfile\n"
            ),
            ".github/actions/docker-writer/Dockerfile": (
                "FROM python:3.12-slim\n"
                "COPY publish /usr/local/bin/publish\n"
                'ENTRYPOINT ["/usr/local/bin/publish"]\n'
            ),
            ".github/actions/docker-writer/publish": (
                "HfApi().create_commit(repo_id='target', operations=[])\n"
            ),
        }
        self.assertEqual(
            find_automatic_writers(
                {
                    CANONICAL_WORKFLOW: canonical,
                    "unsafe-docker-action.yml": competing,
                },
                repo_files,
            ),
            [CANONICAL_WORKFLOW, "unsafe-docker-action.yml"],
        )

    def test_unbounded_local_writer_sources_fail_closed(self) -> None:
        dynamic_directory = """
name: dynamic writer
on: [schedule]
jobs:
  mutate:
    defaults:
      run:
        working-directory: ${{ matrix.directory }}
    steps:
      - run: ./publish
"""
        with self.assertRaisesRegex(
            RuntimeError,
            "dynamic working-directory cannot be bounded",
        ):
            find_automatic_writers(
                {"dynamic-writer.yml": dynamic_directory},
                {"publish": "print('not the resolved source')\n"},
            )

        docker_action = """
name: unbounded Docker action
on: [schedule]
jobs:
  mutate:
    steps:
      - uses: ./.github/actions/docker-writer
"""
        with self.assertRaisesRegex(
            RuntimeError,
            "Docker action COPY/ADD source cannot be bounded",
        ):
            find_automatic_writers(
                {"docker-writer.yml": docker_action},
                {
                    ".github/actions/docker-writer/action.yml": (
                        "runs:\n"
                        "  using: docker\n"
                        "  image: Dockerfile\n"
                    ),
                    ".github/actions/docker-writer/Dockerfile": (
                        "FROM python:3.12-slim\n"
                        "COPY . /app\n"
                    ),
                },
            )
        self.assertEqual(
            _docker_local_sources(
                "COPY --from=builder /usr/local/bin/publish /publish\n"
            ),
            set(),
        )


if __name__ == "__main__":
    unittest.main()
