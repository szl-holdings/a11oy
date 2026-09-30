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
    r"python(?:3(?:\.\d+)?)?(?:[ \t]+(?!-(?:c|e|m)(?:[ \t]|$))-[A-Za-z]+)*|bash|sh|node"
    r")"
    r"(?![ \t]+-(?:c|e|m)(?:[ \t]|$))"
    r"[ \t]+(?!-)"
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
        canonical = path.relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return None
    if canonical != normalized:
        # Do not derive __file__ identity from an alias/symlink source path.
        return None
    if not path.is_file():
        return None
    return normalized, path.read_text(encoding="utf-8")


class _PythonSourcePath(str):
    """A source executed by Python, independent of the filename extension."""


def _python_command_texts(text: str, inherited_directory: str | None,
                          source_path: str | None = None) -> list[tuple[str, str | None, tuple[str, bool] | None]]:
    """Bound standard process calls, without treating Python string data as code.

    This is a static check of supported subprocess/os/asyncio calls, not proof
    that arbitrary dynamically constructed Python cannot execute another file.
    Unknown commands and ambiguous aliases in those calls fail closed. Fixed
    script sources and runtime directories have separate provenance; script
    data is not command text. Importlib/eval/reflection and arbitrary objects'
    conversion methods are outside this bounded process-call analysis.
    """
    current_call_line = 0

    def failure(message, node=None):
        line = current_call_line or getattr(node, "lineno", None)
        location = source_path or "<python source>"
        if line is not None:
            location += ":" + str(line)
        return RuntimeError(location + ": " + message)

    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        raise failure("Python command delegation cannot be parsed", exc) from None
    nodes = list(ast.walk(tree))
    parents = {child: node for node in nodes for child in ast.iter_child_nodes(node)}
    scope_types = (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)
    bindings: dict[ast.AST, dict[str, list[object]]] = {}

    def scopes(node):
        result = []
        cursor = parents.get(node)
        function_seen = False
        while cursor is not None:
            if isinstance(cursor, scope_types):
                if not isinstance(cursor, ast.ClassDef) or not function_seen:
                    result.append(cursor)
                function_seen |= isinstance(cursor, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda))
            cursor = parents.get(cursor)
        return result or [tree]

    def bind(node, name, value):
        bindings.setdefault(scopes(node)[0], {}).setdefault(name, []).append(value)

    for node in nodes:
        if isinstance(node, ast.Import):
            for alias in node.names:
                bind(node, alias.asname or alias.name.split(".")[0],
                     ("qualified", alias.name if alias.asname else alias.name.split(".")[0]))
        elif isinstance(node, ast.ImportFrom):
            if node.level and (
                    (node.module or "").split(".")[0] in {"subprocess", "os", "asyncio", "sys", "pathlib", "builtins"}
                    or any(alias.name in {"subprocess", "os", "asyncio", "sys", "pathlib", "builtins"} for alias in node.names)):
                raise failure("Relative Python execution/helper import cannot be bounded", node)
            if node.module in {"subprocess", "os", "asyncio", "sys", "pathlib", "builtins"} and any(alias.name == "*" for alias in node.names):
                raise RuntimeError("Python execution wildcard import cannot be bounded")
            for alias in node.names:
                bind(node, alias.asname or alias.name,
                     None if node.level else ("qualified", f"{node.module}.{alias.name}"))
        elif isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            parent = parents[node]
            value = (parent.value if isinstance(parent, ast.Assign) and node in parent.targets
                     else parent.value if isinstance(parent, ast.AnnAssign) and parent.target is node
                     else None)
            if value is None:
                cursor = parent
                while isinstance(cursor, (ast.Tuple, ast.List)):
                    cursor = parents.get(cursor)
                if isinstance(cursor, (ast.Assign, ast.NamedExpr)):
                    value = ("unknown", cursor.value)
            bind(node, node.id, value)
        elif isinstance(node, ast.arg):
            bind(node, node.arg, None)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bind(node, node.name, None)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            for name in node.names:
                bind(node, name, None)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            bind(node, node.name, None)

    def lookup(name, chain):
        for scope in chain:
            values = bindings.get(scope, {}).get(name)
            if values is not None:
                return values
        return []

    def qualified(node, chain=None, seen=frozenset()):
        if node is None or id(node) in seen or len(seen) > MAX_REFERENCE_DEPTH:
            return None
        chain = scopes(node) if chain is None else chain
        seen = seen | {id(node)}
        if isinstance(node, ast.Name):
            values = lookup(node.id, chain)
            if len(values) != 1:
                return None
            value = values[0]
            return value[1] if isinstance(value, tuple) and value[0] == "qualified" else (
                None if isinstance(value, tuple) else qualified(value, seen=seen))
        if isinstance(node, ast.Attribute):
            base = qualified(node.value, chain, seen)
            return f"{base}.{node.attr}" if base else None
        return None

    process_roots = {"subprocess", "os", "asyncio"}
    executions = {f"subprocess.{name}" for name in (
        "run", "Popen", "call", "check_call", "check_output", "getoutput", "getstatusoutput")}
    executions |= {"os.system", "os.popen", "asyncio.create_subprocess_shell", "asyncio.create_subprocess_exec"}
    unsupported = {f"os.{name}" for name in (
        "execl", "execlp", "execle", "execlpe", "execv", "execvp", "execve", "execvpe",
        "spawnl", "spawnlp", "spawnle", "spawnlpe", "spawnv", "spawnvp", "spawnve", "spawnvpe",
        "posix_spawn", "posix_spawnp", "chdir", "fchdir", "startfile")}

    if any(isinstance(node, ast.Attribute) and isinstance(node.ctx, (ast.Store, ast.Del))
           and (qualified(node.value) or "").split(".")[0]
           in process_roots | {"sys", "pathlib", "builtins"} for node in nodes):
        raise RuntimeError("Python execution module attributes were mutated")

    path_intrinsics = {"os.path", "os.path.abspath", "os.path.dirname", "os.path.join",
                       "pathlib", "pathlib.Path", "sys", "builtins", "builtins.str"}

    def intrinsic_value(node, seen=frozenset()):
        # A returned path/string is data; handing out the helper/module is not.
        if node is None or id(node) in seen or isinstance(node, ast.Call):
            return False
        seen = seen | {id(node)}
        name = qualified(node)
        if name is not None:
            return name in path_intrinsics
        if isinstance(node, ast.Name):
            return any((isinstance(value, tuple) and value[0] == "qualified"
                        and value[1] in path_intrinsics)
                       or (isinstance(value, ast.AST) and intrinsic_value(value, seen))
                       for scope in scopes(node)
                       for value in bindings.get(scope, {}).get(node.id, []))
        return any(intrinsic_value(child, seen) for child in ast.iter_child_nodes(node))

    def known_process_result(node):
        # The value returned by run() is process result data, not its callee.
        # Every run() call is still independently checked by the execution loop.
        return isinstance(node, ast.Call) and qualified(node.func) == "subprocess.run"

    def potential_process(node, seen=frozenset()):
        if node is None or id(node) in seen:
            return False
        if known_process_result(node):
            return False
        seen = seen | {id(node)}
        name = qualified(node)
        if name and name.split(".")[0] in process_roots:
            return True
        if isinstance(node, ast.Name):
            # Inspect shadowed outer bindings too: an ambiguous executor alias
            # must not disappear just because a nearer parameter hides it.
            return any((isinstance(value, tuple) and value[0] == "qualified" and value[1].split(".")[0] in process_roots)
                       or (isinstance(value, tuple) and value[0] == "unknown" and potential_process(value[1], seen))
                       or (isinstance(value, ast.AST) and potential_process(value, seen))
                       for scope in scopes(node)
                       for value in bindings.get(scope, {}).get(node.id, []))
        return any(potential_process(child, seen) for child in ast.iter_child_nodes(node))

    def execution_value(node, seen=frozenset()):
        if node is None or id(node) in seen:
            return False
        if known_process_result(node):
            return False
        seen = seen | {id(node)}
        name = qualified(node)
        if name is not None:
            return name in executions | unsupported | process_roots
        if isinstance(node, ast.Name):
            return any((isinstance(value, tuple) and value[0] == "qualified"
                        and value[1] in executions | unsupported | process_roots)
                       or (isinstance(value, tuple) and value[0] == "unknown" and execution_value(value[1], seen))
                       or (isinstance(value, ast.AST) and execution_value(value, seen))
                       for scope in scopes(node)
                       for value in bindings.get(scope, {}).get(node.id, []))
        return any(execution_value(child, seen) for child in ast.iter_child_nodes(node))

    for node in nodes:
        escaping = []
        if isinstance(node, ast.Call) and qualified(node.func) not in executions:
            escaping = [*node.args, *(keyword.value for keyword in node.keywords)]
        elif isinstance(node, (ast.Return, ast.Yield, ast.YieldFrom)):
            escaping = [node.value]
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            escaping = [*node.args.defaults, *(value for value in node.args.kw_defaults if value is not None)]
        elif isinstance(node, ast.Assign) and any(not isinstance(target, ast.Name) for target in node.targets):
            escaping = [node.value]
        elif isinstance(node, ast.AnnAssign) and not isinstance(node.target, ast.Name):
            escaping = [node.value]
        if any(execution_value(value) or intrinsic_value(value) for value in escaping):
            raise failure("Python execution callable or module escaped its bounded scope", node)

    class RepoPath:
        """Source-derived repository identity, never a host absolute literal."""
        def __init__(self, relative, absolute=False, mutable=False):
            self.relative = relative
            self.absolute = absolute
            self.mutable = mutable

    class RelativePath:
        def __init__(self, relative):
            self.relative = relative

    def join_path(base, component, node):
        if (not base.absolute or type(component) is not str or not component
                or not re.fullmatch(r"(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+", component)
                or ".." in PurePosixPath(component).parts):
            raise failure("Python source-derived path cannot be bounded", node)
        return RepoPath((PurePosixPath(base.relative) / component).as_posix().removeprefix("./"), base.absolute, base.mutable)

    def builtin_str(node):
        return (qualified(node) == "builtins.str"
                or isinstance(node, ast.Name) and node.id == "str"
                and not lookup("str", scopes(node)))

    def literal(node, seen=frozenset()):
        if node is None or id(node) in seen or len(seen) > MAX_REFERENCE_DEPTH:
            raise failure("Python execution command cannot be bounded", node)
        seen = seen | {id(node)}
        if isinstance(node, ast.Constant) and type(node.value) is str:
            if len(node.value) > 16 * 1024:
                raise RuntimeError("Python execution command is too large")
            return node.value, set()
        if qualified(node) == "sys.executable":
            return "python", set()
        if isinstance(node, ast.Name) and node.id == "__file__":
            if (lookup("__file__", scopes(node)) or source_path is None
                    or not re.fullmatch(r"(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+", source_path)
                    or ".." in PurePosixPath(source_path).parts):
                raise failure("Python source file identity cannot be bounded", node)
            return RepoPath(source_path), set()
        if isinstance(node, ast.Call):
            function = qualified(node.func)
            if function in {"pathlib.Path", "os.path.abspath", "os.path.dirname", "os.path.join"} or builtin_str(node.func):
                if node.keywords or not node.args or any(isinstance(arg, ast.Starred) for arg in node.args):
                    raise failure("Python source-derived path cannot be bounded", node)
                value, _ = literal(node.args[0], seen)
                if function == "os.path.join":
                    if not isinstance(value, RepoPath):
                        raise failure("Python source-derived path lacks repository identity", node)
                    for component in node.args[1:]:
                        part, _ = literal(component, seen)
                        value = join_path(value, part, node)
                    return RepoPath(value.relative, value.absolute), set()
                if len(node.args) != 1:
                    raise failure("Python source-derived path cannot be bounded", node)
                if builtin_str(node.func) and isinstance(value, RepoPath):
                    return RepoPath(value.relative, value.absolute), set()
                if not isinstance(value, RepoPath):
                    raise failure("Python source-derived path lacks repository identity", node)
                if function == "pathlib.Path":
                    value = RepoPath(value.relative, value.absolute, True)
                if function == "os.path.abspath":
                    value = RepoPath(value.relative, True)
                if function == "os.path.dirname":
                    if not value.absolute or not value.relative:
                        raise failure("Python source-derived path escapes or lacks repository identity", node)
                    parent = PurePosixPath(value.relative).parent.as_posix()
                    value = RepoPath("" if parent == "." else parent, value.absolute)
                return value, set()
            if isinstance(node.func, ast.Attribute):
                value, _ = literal(node.func.value, seen)
                if node.func.attr == "resolve" and isinstance(value, RepoPath) and value.mutable and not node.args and not node.keywords:
                    return RepoPath(value.relative, True, True), set()
                if node.func.attr == "relative_to" and isinstance(value, RepoPath) and value.mutable and len(node.args) == 1 and not node.keywords:
                    base, _ = literal(node.args[0], seen)
                    if isinstance(base, RepoPath) and base.absolute and value.absolute:
                        try:
                            relative = PurePosixPath(value.relative).relative_to(PurePosixPath(base.relative)).as_posix()
                        except ValueError:
                            raise failure("Python source-derived relative path escapes its anchor", node) from None
                        return RelativePath(relative), set()
                if node.func.attr == "as_posix" and isinstance(value, RelativePath) and not node.args and not node.keywords:
                    return value.relative, set()
        if (isinstance(node, ast.Subscript) and isinstance(node.value, ast.Attribute)
                and node.value.attr == "parents"):
            value, _ = literal(node.value.value, seen)
            index = node.slice
            if (isinstance(value, RepoPath) and value.absolute and value.mutable and isinstance(index, ast.Constant)
                    and type(index.value) is int and 0 <= index.value < len(PurePosixPath(value.relative).parts)):
                parent = PurePosixPath(value.relative).parents[index.value].as_posix()
                return RepoPath("" if parent == "." else parent, value.absolute, True), set()
            raise failure("Python source-derived parent is outside the repository", node)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            base, _ = literal(node.left, seen)
            component, _ = literal(node.right, seen)
            if isinstance(base, RepoPath) and base.absolute and base.mutable:
                return join_path(base, component, node), set()
        if isinstance(node, ast.Name):
            values = lookup(node.id, scopes(node))
            if len(values) == 1 and isinstance(values[0], ast.AST):
                return literal(values[0], seen)
        if isinstance(node, (ast.List, ast.Tuple)) and len(node.elts) <= MAX_REFERENCED_SOURCES:
            parts = [literal(part, seen) for part in node.elts]
            if all(type(value) is str for value, _ in parts):
                return [value for value, _ in parts], ({id(node)} if isinstance(node, ast.List) else set())
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            left, left_origins = literal(node.left, seen)
            right, right_origins = literal(node.right, seen)
            if type(left) is type(right) and type(left) in {str, list}:
                if len(left) + len(right) > (16 * 1024 if type(left) is str else MAX_REFERENCED_SOURCES):
                    raise RuntimeError("Python execution command is too large")
                return left + right, left_origins | right_origins
        raise failure("Python execution command cannot be bounded", node)

    def origins(node, seen=frozenset()):
        # Track mutable containers even when a script-data operand is opaque.
        if node is None or id(node) in seen or len(seen) > MAX_REFERENCE_DEPTH:
            return set()
        seen = seen | {id(node)}
        if isinstance(node, ast.List):
            return {id(node)}
        if isinstance(node, ast.Name):
            return set().union(*(origins(value, seen) for value in lookup(node.id, scopes(node))
                                 if isinstance(value, ast.AST)))
        if isinstance(node, ast.Subscript):
            return origins(node.value, seen)
        if isinstance(node, (ast.Tuple, ast.BinOp)):
            return set().union(*(origins(child, seen) for child in ast.iter_child_nodes(node)))
        return set()

    def argv_nodes(node, seen=frozenset()):
        if node is None or id(node) in seen or len(seen) > MAX_REFERENCE_DEPTH:
            raise failure("Python execution argv cannot be bounded", node)
        seen = seen | {id(node)}
        if isinstance(node, (ast.List, ast.Tuple)) and len(node.elts) <= MAX_REFERENCED_SOURCES:
            if any(isinstance(part, ast.Starred) for part in node.elts):
                raise failure("Python execution argv cannot be bounded", node)
            return node.elts
        if isinstance(node, ast.Name):
            values = lookup(node.id, scopes(node))
            if len(values) == 1 and isinstance(values[0], ast.AST):
                return argv_nodes(values[0], seen)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            parts = argv_nodes(node.left, seen) + argv_nodes(node.right, seen)
            if len(parts) <= MAX_REFERENCED_SOURCES:
                return parts
        raise failure("Python execution argv cannot be bounded", node)

    def script_data(node, seen=frozenset()):
        # Data after a fixed script cannot choose that script. Never stringify
        # this domain into executable evidence or relax nested process calls.
        if node is None or id(node) in seen or len(seen) > MAX_REFERENCE_DEPTH or execution_value(node):
            raise failure("Python script data cannot be bounded", node)
        seen = seen | {id(node)}
        try:
            value, _ = literal(node)
        except RuntimeError:
            if isinstance(node, ast.Name):
                values = lookup(node.id, scopes(node))
                if len(values) == 1:
                    if values[0] is None:  # A parameter: an opaque data operand.
                        return
                    if isinstance(values[0], ast.AST):
                        return script_data(values[0], seen)
            if (isinstance(node, ast.Call) and builtin_str(node.func)
                    and len(node.args) == 1 and not node.keywords
                    and not isinstance(node.args[0], (ast.Starred, ast.List, ast.Tuple, ast.Dict, ast.Set))):
                if not execution_value(node.args[0]):
                    return
            raise failure("Python script data cannot be bounded", node) from None
        if not isinstance(value, RepoPath) and type(value) is not str:
            raise failure("Python script data cannot be bounded", node)

    escaped_lists = set()
    for node in nodes:
        if isinstance(node, ast.Attribute):
            escaped_lists.update(origins(node.value))
        elif isinstance(node, ast.Subscript) and isinstance(node.ctx, (ast.Store, ast.Del)):
            escaped_lists.update(origins(node.value))
        elif isinstance(node, (ast.Return, ast.Yield, ast.YieldFrom)):
            escaped_lists.update(origins(node.value))
        elif isinstance(node, ast.Call) and qualified(node.func) not in executions:
            for argument in [*node.args, *(keyword.value for keyword in node.keywords)]:
                for part in ast.walk(argument):
                    if isinstance(part, ast.Name):
                        escaped_lists.update(origins(part))
        elif isinstance(node, ast.Assign) and any(not isinstance(target, ast.Name) for target in node.targets):
            for part in ast.walk(node.value):
                if isinstance(part, ast.Name):
                    escaped_lists.update(origins(part))
        elif isinstance(node, (ast.List, ast.Tuple, ast.Set, ast.Dict)):
            for part in ast.walk(node):
                if isinstance(part, ast.Name):
                    escaped_lists.update(origins(part))

    def mutable_path(node):
        try:
            value, _ = literal(node)
        except RuntimeError:
            return False
        return isinstance(value, RelativePath) or isinstance(value, RepoPath) and value.mutable

    # Path.__str__/__fspath__ can change through private state or an escaped
    # instance. Reject those effects instead of trusting its reconstructed AST.
    allowed_argv_origins = set()
    for node in nodes:
        if isinstance(node, ast.Call) and qualified(node.func) in executions:
            argument = node.args[0] if node.args else next(
                (item.value for item in node.keywords if item.arg == "args"), None)
            allowed_argv_origins.update(origins(argument))
    for node in nodes:
        if (isinstance(node, ast.Attribute) and isinstance(node.ctx, (ast.Store, ast.Del))
                and mutable_path(node.value)):
            raise failure("Python source-derived Path object was mutated", node)
        escaping = []
        if isinstance(node, ast.Call) and qualified(node.func) not in executions:
            bounded_helper = (qualified(node.func) in {
                "pathlib.Path", "os.path.abspath", "os.path.dirname", "os.path.join"}
                or builtin_str(node.func))
            if isinstance(node.func, ast.Attribute) and mutable_path(node.func.value):
                try:
                    literal(node)
                except RuntimeError:
                    raise failure("Python source-derived Path method cannot be bounded", node) from None
                bounded_helper = True
            if not bounded_helper:
                escaping = [*node.args, *(item.value for item in node.keywords)]
        elif isinstance(node, (ast.Return, ast.Yield, ast.YieldFrom)):
            escaping = [node.value]
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            escaping = [*node.args.defaults, *(value for value in node.args.kw_defaults if value is not None)]
        elif isinstance(node, ast.Assign) and any(not isinstance(target, ast.Name) for target in node.targets):
            escaping = [node.value]
        elif isinstance(node, ast.AnnAssign) and not isinstance(node.target, ast.Name):
            escaping = [node.value]
        elif isinstance(node, (ast.List, ast.Tuple, ast.Set, ast.Dict)) and id(node) not in allowed_argv_origins:
            escaping = list(ast.iter_child_nodes(node))
        if any(mutable_path(part) for value in escaping for part in ast.walk(value)):
            raise failure("Python source-derived Path object escaped its bounded scope", node)

    commands = []
    for node in nodes:
        if not isinstance(node, ast.Call):
            continue
        current_call_line = node.lineno
        function = qualified(node.func)
        if function in unsupported or (function is None and potential_process(node.func)):
            raise RuntimeError("Python execution alias or working directory cannot be bounded")
        if function not in executions:
            continue
        if any(keyword.arg is None for keyword in node.keywords) or any(isinstance(arg, ast.Starred) for arg in node.args):
            raise RuntimeError("Python execution arguments cannot be bounded")
        keywords = {keyword.arg: keyword.value for keyword in node.keywords}
        if len(keywords) != len(node.keywords):
            raise RuntimeError("Python execution arguments cannot be bounded")
        executable = keywords.get("executable")
        if executable is not None and not (isinstance(executable, ast.Constant) and executable.value is None):
            raise RuntimeError("Python execution executable override cannot be bounded")
        if function != "asyncio.create_subprocess_exec" and len(node.args) > 1:
            raise RuntimeError("Python execution positional arguments cannot be bounded")
        argument = node.args[0] if node.args else keywords.get("args")
        if node.args and "args" in keywords:
            raise RuntimeError("Python execution arguments cannot be bounded")
        structural = None
        if function == "asyncio.create_subprocess_exec":
            structural = node.args
            command_origins = set().union(*(origins(arg) for arg in node.args))
        else:
            command_origins = origins(argument)
            try:
                structural = argv_nodes(argument)
            except RuntimeError:
                command, _ = literal(argument)
                if type(command) is not str:
                    raise failure("Python execution command cannot be bounded", node)
        if command_origins & escaped_lists:
            raise RuntimeError("Python execution argv was mutated or escaped")
        shell = keywords.get("shell")
        if shell is not None and not (isinstance(shell, ast.Constant) and type(shell.value) is bool):
            raise RuntimeError("Python execution shell mode cannot be bounded")
        uses_shell = (function in {"os.system", "os.popen", "subprocess.getoutput",
                                  "subprocess.getstatusoutput", "asyncio.create_subprocess_shell"}
                      or (shell is not None and shell.value is True))
        if structural is not None:
            if not structural:
                raise failure("Python execution command cannot be bounded", node)
            program_value, _ = literal(structural[0])
            if type(program_value) is not str:
                raise failure("Python execution program cannot be bounded", node)
            argv = [program_value]
        else:
            if uses_shell and any(token in command for token in (";", "&", "|", "\n", "`", "$")):
                raise RuntimeError("Python shell delegation cannot be bounded")
            try:
                argv = shlex.split(command, posix=True)
            except ValueError as exc:
                raise RuntimeError("Python execution argv cannot be bounded") from exc
        if not argv:
            raise RuntimeError("Python execution command cannot be bounded")
        program = PurePosixPath(argv[0]).name
        if any(character.isspace() for character in argv[0]) or program == "env" or any(token in argv[0] for token in ("\\", ":", "$", "`", "\n", "\x00")):
            raise RuntimeError("Python execution program cannot be bounded")
        interpreter = re.fullmatch(r"python(?:3(?:\.\d+)?)?", program) is not None
        if (interpreter or program in {"bash", "sh", "node"}) and argv[0] != program:
            raise RuntimeError("Python interpreter executable identity cannot be bounded")
        source_reference = None
        anchored_script = None
        isolated = False
        fixed_script = False
        if interpreter and structural is not None and not uses_shell:
            index = 1
            while index < len(structural):
                value, _ = literal(structural[index])
                if type(value) is not str or value not in {"-B", "-u", "-O", "-OO", "-I"}:
                    break
                isolated |= value == "-I"
                argv.append(value)
                index += 1
            if index >= len(structural):
                raise failure("Python interpreter source cannot be bounded", node)
            selector, _ = literal(structural[index])
            if isinstance(selector, RepoPath):
                if not selector.absolute:
                    raise failure("Python source-derived script lacks absolute repository identity", node)
                anchored_script = selector.relative
                source_reference = (selector.relative, True)
                fixed_script = True
            elif type(selector) is str and not selector.startswith("-"):
                if (not re.fullmatch(r"(?:\./)?(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+", selector)
                        or ".." in PurePosixPath(selector).parts):
                    raise failure("Python interpreter source path cannot be bounded", node)
                source_reference = (selector, False)
                fixed_script = True
            if fixed_script:
                for operand in structural[index + 1:]:
                    script_data(operand)
                # Only the interpreter and source are executable evidence.
                command = " ".join(argv)
        if not fixed_script:
            if structural is not None:
                values = [literal(part)[0] for part in structural]
                if any(type(value) is not str for value in values):
                    raise failure("Python execution command cannot be bounded", node)
                argv = values
            if any(any(token in part for token in ("$", "`", "\n", "\x00")) for part in argv):
                raise RuntimeError("Python interpreter expansion cannot be bounded")
            if program in {"bash", "sh"} and (len(argv) < 2 or argv[1].startswith("-")):
                raise RuntimeError("Python shell interpreter delegation cannot be bounded")
            if interpreter or program in {"bash", "sh", "node"}:
                index = 1
                while index < len(argv) and argv[index] in {"-B", "-u", "-O", "-OO", "-I"}:
                    index += 1
                if index >= len(argv):
                    raise RuntimeError("Python interpreter source cannot be bounded")
                selector = argv[index]
                if selector in {"-c", "-e"}:
                    if index + 1 >= len(argv):
                        raise RuntimeError("Python inline execution cannot be bounded")
                    inline = argv[index + 1]
                    known_mutation = (_python_mutates_space(inline) if interpreter
                                      else any(pattern.search(inline) for pattern in MUTATION_PATTERNS))
                    if not known_mutation:
                        raise RuntimeError("Python inline execution cannot be bounded")
                elif selector == "-m" and interpreter:
                    if index + 1 >= len(argv) or not re.fullmatch(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*", argv[index + 1]):
                        raise RuntimeError("Python module execution cannot be bounded")
                elif selector.startswith("-") or any(character.isspace() for character in selector):
                    raise RuntimeError("Python interpreter source identity cannot be bounded")
                elif (not re.fullmatch(r"(?:\./)?(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+", selector)
                      or ".." in PurePosixPath(selector).parts):
                    raise RuntimeError("Python interpreter source path cannot be bounded")
            command = " ".join(argv)
        directory = inherited_directory
        cwd = keywords.get("cwd")
        if cwd is not None and not (isinstance(cwd, ast.Constant) and cwd.value is None):
            try:
                directory_value, _ = literal(cwd)
            except RuntimeError:
                if anchored_script is None or not isolated or uses_shell:
                    raise failure("Python execution command cannot be bounded", node) from None
                directory_value = None
            if isinstance(directory_value, RepoPath):
                if not directory_value.absolute:
                    raise failure("Python source-derived cwd lacks absolute repository identity", node)
                directory = directory_value.relative
            elif directory_value is None:
                directory = None  # UNKNOWN, never silently inherit a known cwd.
            elif type(directory_value) is str:
                path = PurePosixPath(directory_value)
                if (not re.fullmatch(r"(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+", directory_value)
                        or path.is_absolute() or ".." in path.parts or directory is None):
                    raise failure("Python execution working directory escapes or lacks repository provenance", node)
                directory = (PurePosixPath(directory) / path).as_posix().removeprefix("./")
            else:
                raise failure("Python execution working directory cannot be bounded", node)
        if directory is None and (anchored_script is None or not isolated or uses_shell):
            raise failure("Python execution working directory cannot be bounded", node)
        commands.append(("run: " + command, directory, source_reference))
    return commands


def _referenced_sources(
    text: str,
    repo_files: dict[str, str] | None = None,
) -> list[tuple[str | None, str]]:
    """Include scripts and local actions that the workflow actually executes."""

    combined: list[tuple[str | None, str]] = [(None, text)]
    queue: list[tuple[str | None, str, int, str | None]] = [(None, text, 0, "")]
    visited: set[tuple[str, str | None, bool]] = set()
    while queue:
        current_path, source_text, depth, inherited_directory = queue.pop()
        if depth > MAX_REFERENCE_DEPTH:
            raise RuntimeError("local writer reference depth is unbounded")
        current = _executable_text(source_text)
        is_yaml_execution_context = (
            current_path is None
            or PurePosixPath(current_path).name in {"action.yml", "action.yaml"}
        )
        is_python = current_path is not None and (isinstance(current_path, _PythonSourcePath) or current_path.endswith(".py"))
        contexts = (_python_command_texts(source_text, inherited_directory, current_path)
                    if is_python else [(current, inherited_directory, None)])
        if is_python:
            current = "\n".join(command for command, _directory, _anchor in contexts)
        references: set[tuple[str, str, bool, str | None, bool]] = set()
        for command_text, command_directory, source_reference in contexts:
            if source_reference is not None:
                script, anchored = source_reference
                if not anchored and command_directory is None:
                    raise RuntimeError("relative Python source requires known repository working directory")
                references.add((script, "" if anchored else command_directory, True, command_directory, True))
            if is_python:
                # Executed inline commands remain mutation evidence; expected
                # command strings elsewhere in Python do not become references.
                combined.append((None, command_text))
            direct_calls = {match.group("path") for match in DIRECT_SCRIPT_CALL.finditer(command_text)}
            script_matches = list(LOCAL_SCRIPT_CALL.finditer(command_text))
            script_calls = {match.group("path") for match in script_matches}
            python_script_calls = {match.group("path") for match in script_matches
                                   if re.match(r"\s*python(?:3(?:\.\d+)?)?(?:\s|$)", match.group(0))}
            module_calls = {match.group("module") for match in LOCAL_MODULE_CALL.finditer(command_text)}
            working_directories = (_working_directories(current)
                if is_yaml_execution_context and (script_calls or direct_calls or module_calls)
                else {command_directory})
            if (script_calls or direct_calls or module_calls) and None in working_directories:
                raise RuntimeError("relative Python source requires known repository working directory")
            for relative_path in script_calls | direct_calls:
                references.update((relative_path, base_dir, is_python, base_dir, relative_path in python_script_calls)
                                  for base_dir in working_directories)
            for module in module_calls:
                module_path = module.replace(".", "/")
                for base_dir in working_directories:
                    alternatives = (f"{module_path}.py", f"{module_path}/__main__.py")
                    available = [path for path in alternatives
                                 if _repo_source(path, repo_files, base_dir=base_dir) is not None]
                    if is_python and not available:
                        raise RuntimeError("required local writer module is unavailable: " + module)
                    references.update((path, base_dir, False, base_dir, False) for path in available)

        for match in LOCAL_ACTION_CALL.finditer(current) if not is_python else ():
            action_dir = match.group("path").rstrip("/")
            references.update(
                {
                    (f"{action_dir}/action.yml", "", False, inherited_directory, False),
                    (f"{action_dir}/action.yaml", "", False, inherited_directory, False),
                }
            )

        if (
            current_path is not None
            and PurePosixPath(current_path).name in {"action.yml", "action.yaml"}
            and re.search(r"(?m)^\s*(?:runs:|using:)", current)
        ):
            action_dir = PurePosixPath(current_path).parent.as_posix()
            references.update(
                (match.group("path"), action_dir, True, inherited_directory, False)
                for match in ACTION_ENTRYPOINT.finditer(current)
            )
            references.update(
                (match.group("path"), action_dir, True, inherited_directory, False)
                for match in ACTION_DOCKER_IMAGE.finditer(current)
            )

        if (
            current_path is not None
            and PurePosixPath(current_path).name.lower().startswith("dockerfile")
        ):
            docker_dir = PurePosixPath(current_path).parent.as_posix()
            references.update(
                (relative_path, docker_dir, True, inherited_directory, False)
                for relative_path in _docker_local_sources(current)
            )

        for relative_path, base_dir, required, next_directory, python_source in sorted(
                references, key=lambda item: (item[0], item[1], item[2], item[3] or "", item[4])):
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
            if python_source:
                normalized = _PythonSourcePath(normalized)
            visit = (normalized, next_directory, python_source or normalized.endswith(".py"))
            if visit in visited:
                continue
            if len(visited) >= MAX_REFERENCED_SOURCES:
                raise RuntimeError("too many local writer references")
            visited.add(visit)
            combined.append((normalized, source_text))
            queue.append((normalized, source_text, depth + 1, next_directory))
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
        if relative_path is not None and (isinstance(relative_path, _PythonSourcePath) or relative_path.lower().endswith(".py")):
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
        self.assertRegex(text, r"(?m)^  runtime-config:\n(?:    [^\n]*\n)*?    needs: \[manual-prerequisites, deploy\]$")

    def _python_wrapper_writers(self, source: str, *, files=None, directory="") -> list[str]:
        workflow = """name: delegated Python writer
on: [schedule]
jobs:
  mutate:
    env:
      SPACE_ID: SZLHOLDINGS/a11oy
    steps:
      - run: python3 scripts/driver.py
"""
        if directory:
            workflow = workflow.replace("python3 scripts/driver.py", "python3 driver.py")
            workflow += "        working-directory: " + directory + "\n"
        repo_files = {"scripts/driver.py": source, "scripts/writer.py": "client.create_commit(repo_id='target', operations=[])\n"}
        if files is not None:
            repo_files = files
        return find_automatic_writers({"wrapper.yml": workflow}, repo_files)

    def test_python_expected_command_strings_and_argv_are_not_execution(self) -> None:
        source = '''"""Expected: python3 scripts/writer.py"""
expected = "python3 scripts/writer.py"
argv_fixture = ["python3", "scripts/writer.py"]
marker = "client.create_commit(repo_id='SZLHOLDINGS/a11oy', operations=[])"
assert expected.startswith("python3")
'''
        self.assertEqual(self._python_wrapper_writers(source), [])

    def test_python_action_yaml_fixture_does_not_execute_local_action(self) -> None:
        source = 'expected = "uses: ./.github/actions/writer"\n'
        self.assertEqual(self._python_wrapper_writers(source, files={
            "scripts/driver.py": source,
            ".github/actions/writer/action.yml": "runs:\n  using: node20\n  main: writer.js\n",
            ".github/actions/writer/writer.js": "client.upload_folder({repo_id: 'SZLHOLDINGS/a11oy'})\n",
        }), [])

    def test_actual_python_process_wrappers_and_static_aliases_reach_writer(self) -> None:
        sources = (
            'import subprocess\nsubprocess.run("python3 scripts/writer.py", shell=True)\n',
            'import subprocess as sp\nsp.check_call(["python3", "scripts/writer.py"])\n',
            'from subprocess import Popen as launch\nlaunch(args=["python3", "scripts/writer.py"])\n',
            'import subprocess as sp\nlaunch = sp.run\ncommand = ("python3", "scripts/writer.py")\nlaunch(command)\n',
            'import subprocess\nargv = ["python3", "scripts/writer.py"]\nsubprocess.run(argv)\n',
            'import os\ncommand = "python3 " + "scripts/writer.py"\nos.system(command)\n',
            'import os as operating\noperating.popen("python3 scripts/writer.py")\n',
            'import subprocess, sys\nsubprocess.run([sys.executable, "scripts/writer.py"])\n',
            'import subprocess\nsubprocess.run(["python3", "-m", "scripts.writer"])\n',
            'import subprocess\nsubprocess.run(["python3", "-B", "-m", "scripts.writer"])\n',
        )
        for source in sources:
            with self.subTest(source=source):
                self.assertEqual(self._python_wrapper_writers(source), ["wrapper.yml"])

    def test_actual_inline_python_command_remains_mutation_evidence(self) -> None:
        source = "import subprocess\nsubprocess.run(['python3', '-c', \"client.create_commit(repo_id='target', operations=[])\"])\n"
        self.assertEqual(self._python_wrapper_writers(source), ["wrapper.yml"])
        self.assertEqual(self._python_wrapper_writers(
            source.replace("['python3', '-c'", "['python3', '-B', '-c'")), ["wrapper.yml"])

    def test_standard_run_result_data_is_not_execution_authority(self) -> None:
        sources = (
            'import subprocess\ndef observe():\n    result = subprocess.run(["printf", "harmless"])\n    return result.stdout if result.returncode == 0 else None\n',
            'import subprocess\ndef observe():\n    result = subprocess.run(["printf", "harmless"])\n    data = result.stdout.decode("ascii").strip()\n    return data\n',
            'from subprocess import run as execute\ndef observe():\n    result = execute(["printf", "harmless"])\n    return (result.stdout, result.stderr, result.returncode)\n',
        )
        for source in sources:
            with self.subTest(source=source):
                self.assertEqual(self._python_wrapper_writers(source), [])
                writer = source.replace('["printf", "harmless"]', '["python3", "scripts/writer.py"]')
                self.assertEqual(self._python_wrapper_writers(writer), ["wrapper.yml"])

    def test_returned_run_data_does_not_waive_unknown_commands_or_cwd(self) -> None:
        sources = (
            'import subprocess\ndef observe(command):\n    result = subprocess.run(command)\n    return result.stdout\n',
            'import subprocess\ndef observe(directory):\n    result = subprocess.run(["python3", "scripts/writer.py"], cwd=directory)\n    return result.stdout\n',
            'import subprocess\ncommand = input("must-not-echo")\nresult = subprocess.run(command)\nprint(result.stdout)\n',
        )
        for source in sources:
            with self.subTest(source=source), self.assertRaises(RuntimeError) as caught:
                self._python_wrapper_writers(source)
            message = str(caught.exception)
            self.assertRegex(message, r"scripts/driver\.py:\d+: Python execution command cannot be bounded")
            self.assertNotIn("must-not-echo", message)

    def test_real_executor_escape_remains_blocked_beside_run_result_data(self) -> None:
        escapes = (
            'return subprocess.run',
            'return subprocess',
            'return factory(subprocess.run)',
            'result.stdout = subprocess.run\n    return result.stdout',
            'box = [subprocess.run]\n    return box',
        )
        for escape in escapes:
            source = 'import subprocess\ndef observe():\n    result = subprocess.run(["printf", "harmless"])\n    ' + escape + '\n'
            with self.subTest(escape=escape), self.assertRaises(RuntimeError):
                self._python_wrapper_writers(source)

    def test_ambiguous_shadowed_or_dynamic_python_execution_fails_closed(self) -> None:
        sources = (
            'import subprocess as sp\nsp = replacement\nsp.run("python3 scripts/writer.py")\n',
            'import subprocess as sp\ndef run(sp):\n    sp.run("python3 scripts/writer.py")\n',
            'import subprocess\nlaunch = subprocess.run\nlaunch = replacement\nlaunch("python3 scripts/writer.py")\n',
            'import subprocess\nlaunch, = (subprocess.run,)\nlaunch(["python3", "scripts/writer.py"])\n',
            'import subprocess\n(launch := subprocess.run)\nlaunch(["python3", "scripts/writer.py"])\n',
            'import subprocess as sp\nsp.run = replacement\nsp.run(["python3", "scripts/writer.py"])\n',
            'import subprocess as sp\ndel sp.run\nsp.run(["python3", "scripts/writer.py"])\n',
            'import subprocess\ninvoke(subprocess.run)\n',
            'import subprocess\ndef invoke(launch=subprocess.run):\n    launch(["python3", "scripts/writer.py"])\n',
            'import subprocess\nholder.launch = subprocess.run\n',
            'import subprocess\ndef expose():\n    return subprocess.run\n',
            'import subprocess\ninvoke(subprocess)\n',
            'import subprocess\ncommand = "harmless"\ndef run(command):\n    subprocess.run(command)\n',
            'import subprocess, os\nsubprocess.run(os.environ["COMMAND"])\n',
            'import subprocess\nsubprocess.run(*arguments)\n',
            'import subprocess\nsubprocess.run("python3 scripts/writer.py", **options)\n',
            'import os\nos.execv("python3", ["python3", "scripts/writer.py"])\n',
        )
        for source in sources:
            with self.subTest(source=source), self.assertRaises(RuntimeError):
                self._python_wrapper_writers(source)

    def test_mutated_or_escaped_python_argv_fails_closed(self) -> None:
        mutations = (
            'argv.append("scripts/writer.py")',
            'argv.extend(["scripts/writer.py"])',
            'argv[0] = "replacement"',
            'argv += ["scripts/writer.py"]',
            'alias = argv\nalias.append("scripts/writer.py")',
            'mutate(argv)',
            'box = [argv]\nbox[0][1] = "replacement"',
            'box = {"argv": argv}\nbox["argv"][1] = "replacement"',
            'box = (argv,)\nbox[0][1] = "replacement"',
        )
        for mutation in mutations:
            source = 'import subprocess\nargv = ["python3", "scripts/writer.py"]\n' + mutation + '\nsubprocess.run(argv)\n'
            with self.subTest(mutation=mutation), self.assertRaises(RuntimeError):
                self._python_wrapper_writers(source)

    def test_process_overrides_extra_positionals_and_wildcards_fail_closed(self) -> None:
        sources = (
            'import subprocess\nsubprocess.run(["harmless"], executable="scripts/writer.py")\n',
            'import subprocess\nsubprocess.Popen(["harmless"], -1, "scripts/writer.py")\n',
            'import subprocess\nsubprocess.call(["harmless"], options)\n',
            'import os\nos.popen("harmless", "r")\n',
            'from subprocess import *\nrun(["python3", "scripts/writer.py"])\n',
            'from os import *\nsystem("python3 scripts/writer.py")\n',
            'from asyncio import *\ncreate_subprocess_exec("python3", "scripts/writer.py")\n',
            'import os\nos.startfile("scripts/writer.py")\n',
            'from .subprocess import run as launch\nlaunch(["python3", "scripts/writer.py"])\n',
            'from . import subprocess\nsubprocess.run(["python3", "scripts/writer.py"])\n',
            'from . import os as operating\noperating.system("python3 scripts/writer.py")\n',
            'from .os import system\nsystem("python3 scripts/writer.py")\n',
            'from .asyncio import create_subprocess_exec\ncreate_subprocess_exec("python3", "scripts/writer.py")\n',
            'import subprocess\nsubprocess.run(["bash", "-c", "$SCRIPT"], env=environment)\n',
            'import subprocess\nsubprocess.run(["sh", "-c", "python3 scripts/writer.py"])\n',
            'import subprocess\nsubprocess.run(["env", "python3", "scripts/writer.py"])\n',
            'import subprocess\nsubprocess.run(["python3", "scripts/safe.py extra.py"])\n',
            'import subprocess\nsubprocess.run(["/usr/bin/python3", "scripts/writer.py"])\n',
            'import subprocess\nsubprocess.run(["/usr/bin/node", "scripts/writer.js"])\n',
            'import subprocess\nsubprocess.run(["/usr/bin/bash", "scripts/writer.sh"])\n',
            'import subprocess\nsubprocess.run(["/bin/sh", "scripts/writer.sh"])\n',
            'import subprocess\nsubprocess.run(["python3", "/outside/writer.py"])\n',
        )
        for source in sources:
            with self.subTest(source=source), self.assertRaises(RuntimeError):
                self._python_wrapper_writers(source)
        self.assertEqual(self._python_wrapper_writers(
            'import subprocess\nsubprocess.run(["python3", "scripts/writer.py"], executable=None)\n'), ["wrapper.yml"])
        self.assertEqual(self._python_wrapper_writers(
            'import subprocess\nsubprocess.run(["python3", "scripts/writer.py"], stdout=subprocess.PIPE)\n'), ["wrapper.yml"])

    def test_python_delegation_keeps_inherited_and_explicit_static_cwd(self) -> None:
        source = 'import subprocess\nsubprocess.run(["python3", "writer.py"])\n'
        writer = "client.create_commit(repo_id='target', operations=[])\n"
        self.assertEqual(self._python_wrapper_writers(source, directory="tools/deploy", files={
            "tools/deploy/driver.py": source, "tools/deploy/writer.py": writer}), ["wrapper.yml"])
        explicit = source.replace('])', '], cwd="tools/deploy")')
        self.assertEqual(self._python_wrapper_writers(explicit, files={
            "scripts/driver.py": explicit, "tools/deploy/writer.py": writer}), ["wrapper.yml"])

    def test_unbounded_python_cwd_shell_or_missing_delegate_fails_closed(self) -> None:
        sources = (
            'import subprocess\nsubprocess.run(["python3", "scripts/writer.py"], cwd=directory)\n',
            'import subprocess\nsubprocess.run(["python3", "scripts/writer.py"], cwd="../outside")\n',
            'import os\nos.chdir("tools/deploy")\nos.system("python3 writer.py")\n',
            'import os\nos.system("cd tools/deploy; python3 writer.py")\n',
            'import subprocess\nsubprocess.run("python3 scripts/writer.py", shell=mode)\n',
            'import subprocess\nsubprocess.run(["python3", "scripts/missing.py"])\n',
            'import subprocess\nsubprocess.run(["python3", "-m", "scripts.missing"])\n',
            'import subprocess\nsubprocess.run(["python3", "-m", "missing_writer"])\n',
            'import subprocess\nsubprocess.run(["python3", "-c", "from scripts.writer import publish; publish()"])\n',
            'def broken(:\n',
        )
        for source in sources:
            with self.subTest(source=source), self.assertRaises(RuntimeError):
                self._python_wrapper_writers(source)

    def test_source_anchored_python_script_keeps_opaque_tail_as_data(self) -> None:
        sources = (
            'import os, subprocess, sys\nHERE = os.path.dirname(os.path.abspath(__file__))\nCHECKER = os.path.join(HERE, "checker.py")\ndef inspect(root: str):\n    subprocess.run([sys.executable, CHECKER, root])\n',
            'import subprocess, sys\nfrom pathlib import Path\nBASE = Path(__file__).resolve().parents[0]\nCHECKER = BASE / "checker.py"\ndef inspect(root: str):\n    subprocess.run([sys.executable, str(CHECKER), root])\n',
            'import subprocess, sys\nfrom os.path import abspath as absolute, dirname as parent, join as joined\nCHECKER = joined(parent(absolute(__file__)), "checker.py")\ndef inspect(root: str):\n    subprocess.run([sys.executable, CHECKER, root])\n',
        )
        for source in sources:
            with self.subTest(source=source):
                files = {"scripts/driver.py": source, "scripts/checker.py": "print('inert')\n"}
                self.assertEqual(self._python_wrapper_writers(source, files=files), [])
                files["scripts/checker.py"] = "client.create_commit(repo_id='target', operations=[])\n"
                self.assertEqual(self._python_wrapper_writers(source, files=files), ["wrapper.yml"])
        source = sources[0].replace('CHECKER, root', 'CHECKER, "python3 scripts/missing.py", "--runtime-root", "data with spaces"')
        self.assertEqual(self._python_wrapper_writers(source, files={
            "scripts/driver.py": source, "scripts/checker.py": "print('inert')\n"}), [])

    def test_source_derived_relative_path_uses_its_explicit_anchor(self) -> None:
        source = ('import subprocess, sys\nfrom pathlib import Path\n'
                  'ROOT = Path(__file__).resolve().parents[1]\n'
                  'CHECKER = ROOT / "scripts" / "checker.py"\n'
                  'relative = CHECKER.relative_to(ROOT).as_posix()\n'
                  'subprocess.run([sys.executable, relative], cwd=ROOT)\n')
        self.assertEqual(self._python_wrapper_writers(source, files={
            "scripts/driver.py": source,
            "scripts/checker.py": "client.create_commit(repo_id='target', operations=[])\n"}), ["wrapper.yml"])
        dot_source = ('import os, subprocess, sys\n'
                      'HERE = os.path.dirname(os.path.abspath(__file__))\n'
                      'subprocess.run([sys.executable, os.path.join(HERE, "checker.py")])\n')
        workflow = "on: [schedule]\njobs:\n  check:\n    env:\n      SPACE_ID: SZLHOLDINGS/a11oy\n    steps:\n      - run: python3 .github/scripts/driver.py\n"
        self.assertEqual(find_automatic_writers({"wrapper.yml": workflow}, {
            ".github/scripts/driver.py": dot_source,
            ".github/scripts/checker.py": "client.create_commit(repo_id='target', operations=[])\n"}), ["wrapper.yml"])

    def test_opaque_python_argv_origins_still_reject_mutation_and_escape(self) -> None:
        mutations = (
            'argv[1] = replacement', 'argv.append(root)',
            'alias = argv\n    alias.append(root)', 'mutate(argv)',
            'box = [argv]\n    box[0][1] = replacement',
        )
        for mutation in mutations:
            source = ('import os, subprocess, sys\n'
                      'CHECKER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "checker.py")\n'
                      'def inspect(root: str):\n    argv = [sys.executable, CHECKER, root]\n    '
                      + mutation + '\n    subprocess.run(argv)\n')
            with self.subTest(mutation=mutation), self.assertRaises(RuntimeError):
                self._python_wrapper_writers(source, files={
                    "scripts/driver.py": source, "scripts/checker.py": "print('inert')\n"})

    def test_script_data_does_not_qualify_a_nested_process_selector(self) -> None:
        source = ('import os, subprocess, sys\n'
                  'CHECKER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "checker.py")\n'
                  'def inspect(root: str):\n    subprocess.run([sys.executable, CHECKER, root])\n')
        delegates = (
            'import subprocess, sys\nsubprocess.run(sys.argv[1])\n',
            'import subprocess, sys\nsubprocess.run([sys.executable, sys.argv[1]])\n',
        )
        for delegate in delegates:
            with self.subTest(delegate=delegate), self.assertRaises(RuntimeError):
                self._python_wrapper_writers(source, files={
                    "scripts/driver.py": source, "scripts/checker.py": delegate})
        with self.assertRaises(RuntimeError):
            self._python_wrapper_writers(source, files={"scripts/driver.py": source})
        for selector in ('tools_script', 'str(tools_script)'):
            dynamic = 'import subprocess, sys\ndef inspect(tools_script, root):\n    subprocess.run([sys.executable, ' + selector + ', root])\n'
            with self.subTest(selector=selector), self.assertRaises(RuntimeError):
                self._python_wrapper_writers(dynamic)

    def test_source_derived_path_rejects_traversal_and_out_of_repo_parents(self) -> None:
        expressions = (
            'os.path.join(HERE, "/outside.py")', 'os.path.join(HERE, "../writer.py")',
            'os.path.join(HERE, "C:/writer.py")', 'os.path.join(HERE, "folder\\\\writer.py")',
            'Path(__file__).resolve().parents[99] / "writer.py"',
            'Path(__file__).resolve().parents[-1] / "writer.py"',
            'Path(__file__).resolve().parents[True] / "writer.py"',
            'Path(__file__).resolve().parents[0] / "../writer.py"',
            'Path("/outside/writer.py")', 'Path("__file__")',
            '__file__', 'Path(__file__)', 'str(Path(__file__))',
            'os.path.abspath(os.path.dirname(__file__))',
            'os.path.abspath(os.path.join(os.path.dirname(__file__), "writer.py"))',
            'Path(__file__).parents[0].resolve() / "writer.py"',
            '(Path(__file__) / "writer.py").resolve()',
        )
        for expression in expressions:
            source = ('import os, subprocess, sys\nfrom pathlib import Path\n'
                      'HERE = os.path.dirname(os.path.abspath(__file__))\n'
                      'subprocess.run([sys.executable, ' + expression + '])\n')
            with self.subTest(expression=expression), self.assertRaises(RuntimeError):
                self._python_wrapper_writers(source)

    def test_path_helpers_file_and_interpreter_identity_cannot_be_shadowed(self) -> None:
        replacements = (
            '__file__ = "scripts/driver.py"', 'sys.executable = "replacement"',
            'alias = sys\nalias.executable = "replacement"', 'del sys.executable',
            'os.path.join = replacement', 'alias = os.path\nalias.join = replacement',
            'Path = replacement', 'str = replacement',
            'mutate(sys)', 'mutate(os.path)', 'mutate(Path)',
            'holder.helper = Path',
        )
        for replacement in replacements:
            source = ('import os, subprocess, sys\nfrom pathlib import Path\n' + replacement + '\n'
                      'CHECKER = Path(__file__).resolve().parents[0] / "writer.py"\n'
                      'subprocess.run([sys.executable, str(CHECKER)])\n')
            with self.subTest(replacement=replacement), self.assertRaises(RuntimeError):
                self._python_wrapper_writers(source)
        shadowed = ('import os, subprocess, sys\ndef inspect(__file__):\n'
                    '    checker = os.path.join(os.path.dirname(os.path.abspath(__file__)), "writer.py")\n'
                    '    subprocess.run([sys.executable, checker])\n')
        with self.assertRaises(RuntimeError):
            self._python_wrapper_writers(shadowed)

    def test_unknown_cwd_requires_isolated_anchored_source_and_stays_unknown(self) -> None:
        source = ('import subprocess, sys\nfrom pathlib import Path\n'
                  'CHECKER = Path(__file__).resolve().parents[0] / "checker.py"\n'
                  'def inspect(root):\n    subprocess.run([sys.executable, "-I", str(CHECKER), str(root)], cwd=root)\n')
        files = {"scripts/driver.py": source, "scripts/checker.py": "print('inert')\n"}
        self.assertEqual(self._python_wrapper_writers(source, files=files), [])
        files["scripts/checker.py"] = "client.create_commit(repo_id='target', operations=[])\n"
        self.assertEqual(self._python_wrapper_writers(source, files=files), ["wrapper.yml"])
        for bad in (source.replace('"-I", ', ''), source.replace('str(CHECKER)', '"scripts/checker.py"')):
            with self.subTest(bad=bad), self.assertRaises(RuntimeError):
                self._python_wrapper_writers(bad, files={"scripts/driver.py": bad, "scripts/checker.py": "print('inert')\n"})
        files["scripts/checker.py"] = 'import subprocess\nsubprocess.run(["python3", "scripts/writer.py"], cwd=None)\n'
        files["scripts/writer.py"] = "client.create_commit(repo_id='target', operations=[])\n"
        with self.assertRaises(RuntimeError):
            self._python_wrapper_writers(source, files=files)

    def test_visit_context_does_not_merge_known_and_unknown_directories(self) -> None:
        source = ('import subprocess, sys\nfrom pathlib import Path\n'
                  'CHECKER = Path(__file__).resolve().parents[0] / "checker.py"\n'
                  'subprocess.run([sys.executable, str(CHECKER)])\n'
                  'def inspect(root):\n    subprocess.run([sys.executable, "-I", str(CHECKER)], cwd=root)\n')
        files = {"scripts/driver.py": source,
                 "scripts/checker.py": 'import subprocess\nsubprocess.run(["python3", "scripts/writer.py"])\n',
                 "scripts/writer.py": "client.create_commit(repo_id='target', operations=[])\n"}
        with self.assertRaises(RuntimeError):
            self._python_wrapper_writers(source, files=files)
        # A new independently anchored cwd can establish repository provenance.
        files["scripts/checker.py"] = ('import subprocess\nfrom pathlib import Path\n'
            'ROOT = Path(__file__).resolve().parents[1]\n'
            'subprocess.run(["python3", "scripts/writer.py"], cwd=ROOT)\n')
        self.assertEqual(self._python_wrapper_writers(source, files=files), ["wrapper.yml"])

    def test_source_derived_path_instances_cannot_mutate_or_escape(self) -> None:
        mutations = (
            'CHECKER._str = "scripts/writer.py"',
            'alias = CHECKER\nalias._str = "scripts/writer.py"',
            'setattr(CHECKER, "_str", "scripts/writer.py")',
            'mutate(CHECKER)', 'holder.path = CHECKER',
            'box = [CHECKER]\nbox[0]._str = "scripts/writer.py"',
            'argv = [sys.executable, CHECKER]\nargv[1]._str = "scripts/writer.py"',
            'CHECKER.touch()',
        )
        for mutation in mutations:
            source = ('import subprocess, sys\nfrom pathlib import Path\n'
                      'CHECKER = Path(__file__).resolve().parents[0] / "checker.py"\n'
                      + mutation + '\nsubprocess.run([sys.executable, str(CHECKER)])\n')
            with self.subTest(mutation=mutation), self.assertRaises(RuntimeError):
                self._python_wrapper_writers(source, files={
                    "scripts/driver.py": source, "scripts/checker.py": "print('inert')\n"})

    def test_python_execution_language_does_not_depend_on_script_suffix(self) -> None:
        source = ('import os, subprocess, sys\n'
                  'CHECKER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "checker.data")\n'
                  'def inspect(root: str):\n    subprocess.run([sys.executable, CHECKER, root])\n')
        files = {"scripts/driver.py": source,
                 "scripts/checker.data": 'expected = "client.create_commit(repo_id=target, operations=[])"\n'}
        self.assertEqual(self._python_wrapper_writers(source, files=files), [])
        files["scripts/checker.data"] = "client.create_commit(repo_id='target', operations=[])\n"
        self.assertEqual(self._python_wrapper_writers(source, files=files), ["wrapper.yml"])
        files["scripts/checker.data"] = 'import subprocess, sys\nsubprocess.run(sys.argv[1])\n'
        with self.assertRaises(RuntimeError):
            self._python_wrapper_writers(source, files=files)
        workflow = "on: [schedule]\njobs:\n  check:\n    env:\n      SPACE_ID: SZLHOLDINGS/a11oy\n    steps:\n      - run: python3 scripts/publish\n"
        self.assertEqual(find_automatic_writers({"wrapper.yml": workflow}, {
            "scripts/publish": 'expected = "client.create_commit(repo_id=target, operations=[])"\n'}), [])
        self.assertEqual(find_automatic_writers({"wrapper.yml": workflow}, {
            "scripts/publish": "client.create_commit(repo_id='target', operations=[])\n"}), ["wrapper.yml"])
        for delegate in ('import subprocess, sys\nsubprocess.run(sys.argv[1])\n', 'def broken(:\n'):
            with self.subTest(delegate=delegate), self.assertRaises(RuntimeError):
                find_automatic_writers({"wrapper.yml": workflow}, {"scripts/publish": delegate})

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
