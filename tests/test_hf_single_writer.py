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
        path.relative_to(ROOT.resolve())
    except ValueError:
        return None
    if not path.is_file():
        return None
    return normalized, path.read_text(encoding="utf-8")


class _OpaquePythonValue(RuntimeError):
    """An in-file computed argv/cwd value that is over-approximated, not trusted."""


def _python_command_texts(text: str, inherited_directory: str,
                          source_exists=None, source_directory: str = "") -> list[tuple[str, str]]:
    """Bound standard process calls, without treating Python string data as code.

    This is a static check of supported subprocess/os/asyncio calls, not proof
    that arbitrary dynamically constructed Python cannot execute another file.
    Ambiguous executor aliases, escaped executors, mutated argv, overrides and
    externally supplied commands (environment/argv reads) fail closed.

    A standard process call whose argv or cwd is built from in-file values
    that cannot be reduced to one literal (a wrapper parameter, a computed
    ``Path``) is over-approximated instead: every repository script or module
    that the file names in string data (and that exists) is treated as a
    possible delegate, so a writer reachable through such a wrapper is still
    followed. ``source_exists(path, base_dir)`` filters witnesses to real files.
    """
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        raise RuntimeError("Python command delegation cannot be parsed") from exc
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
            if node.module in {"subprocess", "os", "asyncio"} and any(alias.name == "*" for alias in node.names):
                raise RuntimeError("Python execution wildcard import cannot be bounded")
            for alias in node.names:
                bind(node, alias.asname or alias.name, ("qualified", f"{node.module}.{alias.name}"))
        elif isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            parent = parents[node]
            value = (parent.value if isinstance(parent, ast.Assign) and node in parent.targets
                     else parent.value if isinstance(parent, ast.AnnAssign) and parent.target is node
                     else None)
            if value is None and isinstance(parent, ast.For) and parent.target is node:
                value = ("for", parent.iter)
            if value is None:
                cursor = parent
                while isinstance(cursor, (ast.Tuple, ast.List)):
                    cursor = parents.get(cursor)
                if isinstance(cursor, (ast.Assign, ast.NamedExpr)):
                    value = ("unknown", cursor.value)
            bind(node, node.id, value)
        elif isinstance(node, ast.arg):
            bind(node, node.arg, ("param", node))
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

    # ``os.sys.argv = [...]`` (a test harness setting argv) is data, not an
    # executor; every other store/delete on a process-module member fails closed.
    mutable_data_members = {"os.sys.argv", "os.environ"}
    if any(isinstance(node, ast.Attribute) and isinstance(node.ctx, (ast.Store, ast.Del))
           and (qualified(node.value) or "").split(".")[0] in process_roots
           and f"{qualified(node.value)}.{node.attr}" not in mutable_data_members for node in nodes):
        raise RuntimeError("Python execution module attributes were mutated")

    process_data_members = {
        "os.environ", "os.getenv", "os.path", "os.sep", "os.linesep", "os.pathsep", "os.fspath",
        "os.getcwd", "os.name", "os.listdir", "os.scandir", "os.walk", "os.stat", "os.lstat", "os.fstat",
        "os.getpid", "os.cpu_count", "os.urandom", "os.sys.argv", "subprocess.PIPE", "subprocess.DEVNULL", "subprocess.STDOUT",
        "subprocess.CalledProcessError", "subprocess.TimeoutExpired", "subprocess.SubprocessError",
        "subprocess.CompletedProcess"}

    def process_result(node):
        # The value returned by an unambiguous standard process call (for
        # example ``subprocess.run(...).stdout``) is result data, not the
        # callee. The call itself is still validated by the execution loop.
        return isinstance(node, ast.Call) and qualified(node.func) in executions

    def potential_process(node, seen=frozenset()):
        if node is None or id(node) in seen or process_result(node):
            return False
        if isinstance(node, ast.Call) and data_member_access(node):
            return False
        seen = seen | {id(node)}
        name = qualified(node)
        if name and name.split(".")[0] in process_roots:
            # Known data/constant members of the process modules (environment
            # reads, path helpers, pipe sentinels, exception types) cannot
            # launch a process; every other member remains a potential alias.
            return not any(name == prefix or name.startswith(prefix + ".")
                           for prefix in process_data_members)
        if isinstance(node, ast.Name):
            # Inspect shadowed outer bindings too: an ambiguous executor alias
            # must not disappear just because a nearer parameter hides it.
            return any((isinstance(value, tuple) and value[0] == "qualified" and value[1].split(".")[0] in process_roots)
                       or (isinstance(value, tuple) and value[0] in {"unknown", "for"} and potential_process(value[1], seen))
                       or (isinstance(value, ast.AST) and potential_process(value, seen))
                       for scope in scopes(node)
                       for value in bindings.get(scope, {}).get(node.id, []))
        return any(potential_process(child, seen) for child in ast.iter_child_nodes(node))

    def execution_value(node, seen=frozenset()):
        if node is None or id(node) in seen:
            return False
        seen = seen | {id(node)}
        if isinstance(node, ast.Call) and data_member_access(node):
            return False
        if process_result(node):
            # Only the arguments can smuggle an executor out of a result.
            return any(execution_value(value, seen)
                       for value in [*node.args, *(keyword.value for keyword in node.keywords)])
        name = qualified(node)
        if name is not None:
            return name in executions | unsupported | process_roots
        if isinstance(node, ast.Name):
            return any((isinstance(value, tuple) and value[0] == "qualified"
                        and value[1] in executions | unsupported | process_roots)
                       or (isinstance(value, tuple) and value[0] in {"unknown", "for"} and execution_value(value[1], seen))
                       or (isinstance(value, ast.AST) and execution_value(value, seen))
                       for scope in scopes(node)
                       for value in bindings.get(scope, {}).get(node.id, []))
        return any(execution_value(child, seen) for child in ast.iter_child_nodes(node))

    def data_member_access(call):
        # getattr(os, "O_BINARY", 0) / mock.patch.object(os, "environ", ...) name
        # one constant data member; handing out an executor name stays closed.
        function = qualified(call.func)
        if function is None and isinstance(call.func, ast.Name) and not lookup(call.func.id, scopes(call.func)):
            function = "builtins." + call.func.id
        if function not in {"builtins.getattr", "builtins.hasattr"} and not (
                function or "").endswith("patch.object"):
            return False
        if len(call.args) < 2 or not isinstance(call.args[1], ast.Constant) or type(call.args[1].value) is not str:
            return False
        module = qualified(call.args[0])
        if module not in process_roots | {"builtins", "sys"}:
            return False
        member = f"{module}.{call.args[1].value}"
        return (member.startswith("os.O_") or member in {"os.environ", "os.getenv", "sys.argv", "builtins.__import__"}
                or any(member == prefix for prefix in process_data_members))

    for node in nodes:
        escaping = []
        if isinstance(node, ast.Call) and data_member_access(node):
            escaping = [*node.args[2:], *(keyword.value for keyword in node.keywords)]
        elif isinstance(node, ast.Call) and qualified(node.func) not in executions:
            escaping = [*node.args, *(keyword.value for keyword in node.keywords)]
        elif isinstance(node, (ast.Return, ast.Yield, ast.YieldFrom)):
            escaping = [node.value]
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            escaping = [*node.args.defaults, *(value for value in node.args.kw_defaults if value is not None)]
        elif isinstance(node, ast.Assign) and any(not isinstance(target, ast.Name) for target in node.targets):
            escaping = [node.value]
        elif isinstance(node, ast.AnnAssign) and not isinstance(node.target, ast.Name):
            escaping = [node.value]
        if any(execution_value(value) for value in escaping):
            raise RuntimeError("Python execution callable or module escaped its bounded scope")

    def opaque(node):
        # In-file computed data (a wrapper parameter, a computed Path/str, an
        # attribute or f-string) that is not one literal. Undefined names,
        # rebinding and mutation are NOT opaque; they stay fail-closed.
        if isinstance(node, ast.Name):
            values = lookup(node.id, scopes(node))
            if len(values) == 1:
                return isinstance(values[0], tuple) and values[0][0] in {"param", "for"}
            # Several in-file assignments of computed data are over-approximated;
            # a bare rebinding (augmented assignment, del, global) stays closed.
            return bool(values) and all(isinstance(value, ast.AST)
                                        or isinstance(value, tuple) and value[0] in {"param", "for", "unknown"}
                                        for value in values)
        if isinstance(node, ast.Starred):
            return opaque(node.value)
        return isinstance(node, (ast.Call, ast.Attribute, ast.JoinedStr, ast.Subscript, ast.IfExp, ast.BoolOp))

    def literal(node, seen=frozenset()):
        if node is None or id(node) in seen or len(seen) > MAX_REFERENCE_DEPTH:
            raise RuntimeError("Python execution command cannot be bounded")
        seen = seen | {id(node)}
        if isinstance(node, ast.Constant) and type(node.value) is str:
            if len(node.value) > 16 * 1024:
                raise RuntimeError("Python execution command is too large")
            return node.value, set()
        if qualified(node) == "sys.executable":
            return "python", set()
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
        if opaque(node):
            raise _OpaquePythonValue("Python execution command cannot be bounded")
        raise RuntimeError("Python execution command cannot be bounded")

    def origins(node):
        try:
            return literal(node)[1]
        except RuntimeError:
            return set()

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

    def loop_candidates(argument):
        # ``for command in ([...], [...]): subprocess.run(command)`` binds the
        # argv to each element of a fixed literal sequence; every element is
        # bounded and validated as its own command. Anything else is unchanged.
        if isinstance(argument, ast.Name):
            values = lookup(argument.id, scopes(argument))
            if (len(values) == 1 and isinstance(values[0], tuple) and values[0][0] == "for"
                    and isinstance(values[0][1], (ast.Tuple, ast.List))
                    and 0 < len(values[0][1].elts) <= MAX_REFERENCED_SOURCES):
                return list(values[0][1].elts)
        return [argument]

    external_sources = {"os.environ", "os.getenv", "os.environb", "os.getenvb", "sys.argv", "sys.stdin",
                        "builtins.input", "builtins.open", "fileinput.input"}

    def external_command(call, every_keyword=False):
        """Commands read from the environment, argv, stdin or files have no in-file witness."""
        arguments = [*call.args, *(keyword.value for keyword in call.keywords
                                   if every_keyword or keyword.arg in {None, "args"})]
        pending, seen = list(arguments), set()
        while pending:
            current = pending.pop()
            if id(current) in seen or len(seen) > 4096:
                continue
            seen.add(id(current))
            for part in ast.walk(current):
                name = qualified(part)
                if name is not None and any(name == prefix or name.startswith(prefix + ".")
                                            for prefix in external_sources):
                    return True
                if isinstance(part, ast.Name) and part.id in {"input", "open"} and not lookup(part.id, scopes(part)):
                    return True
                if isinstance(part, ast.Name):
                    for value in lookup(part.id, scopes(part)):
                        if isinstance(value, ast.AST):
                            pending.append(value)
                        elif isinstance(value, tuple) and value[0] in {"unknown", "for"}:
                            pending.append(value[1])
        return False

    def externally_fed(call, argument):
        """A wrapper whose in-file callers pass environment/argv/stdin data as the argv."""
        cursor = parents.get(call)
        while cursor is not None and not isinstance(cursor, (ast.FunctionDef, ast.AsyncFunctionDef)):
            cursor = parents.get(cursor)
        if cursor is None:
            return False
        names, pending, seen = set(), [argument], set()
        while pending:
            current = pending.pop()
            if current is None or id(current) in seen or len(seen) > 4096:
                continue
            seen.add(id(current))
            for part in ast.walk(current):
                if isinstance(part, ast.Name):
                    names.add(part.id)
                    for value in lookup(part.id, scopes(part)):
                        if isinstance(value, ast.AST):
                            pending.append(value)
                        elif isinstance(value, tuple) and value[0] in {"unknown", "for"}:
                            pending.append(value[1])
        positional = [arg.arg for arg in [*cursor.args.posonlyargs, *cursor.args.args]]
        for other in nodes:
            if not isinstance(other, ast.Call):
                continue
            if isinstance(other.func, ast.Name) and other.func.id == cursor.name:
                offset = 0
            elif isinstance(other.func, ast.Attribute) and other.func.attr == cursor.name:
                offset = 1 if positional[:1] in (["self"], ["cls"]) else 0
            else:
                continue
            fed = [value for index, value in enumerate(other.args)
                   if isinstance(value, ast.Starred)
                   or index + offset < len(positional) and positional[index + offset] in names]
            fed += [keyword.value for keyword in other.keywords if keyword.arg is None or keyword.arg in names]
            if fed and external_command(ast.Call(func=other.func, args=fed, keywords=[])):
                return True
        return False

    def witness_commands():
        """Every existing repository script/module this file names in string data."""
        dirs = sorted({inherited_directory, "", source_directory})
        pieces = []
        for node in nodes:
            if isinstance(node, ast.Constant) and type(node.value) is str and len(node.value) <= 16 * 1024:
                pieces.append(node.value)
            elif isinstance(node, (ast.List, ast.Tuple)):
                parts = [("python3" if qualified(part) == "sys.executable" else part.value)
                         for part in node.elts
                         if qualified(part) == "sys.executable"
                         or isinstance(part, ast.Constant) and type(part.value) is str]
                if parts:
                    pieces.append(" ".join(parts))
            elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div) and not isinstance(parents.get(node), ast.BinOp):
                chain, cursor = [], node
                while isinstance(cursor, ast.BinOp) and isinstance(cursor.op, ast.Div):
                    if isinstance(cursor.right, ast.Constant) and type(cursor.right.value) is str:
                        chain.append(cursor.right.value)
                    cursor = cursor.left
                if isinstance(cursor, ast.Constant) and type(cursor.value) is str:
                    chain.append(cursor.value)
                if chain:
                    pieces.append("/".join(reversed(chain)))
        found = []
        for piece in pieces:
            for token in re.split(r"[\s\"',;|&()\[\]{}=]+", piece):
                token = token.removeprefix("./")
                if (not re.fullmatch(r"(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+", token)
                        or ".." in PurePosixPath(token).parts):
                    continue
                suffix = PurePosixPath(token).suffix.lower()
                runner = {".py": "python3", ".sh": "bash", ".bash": "bash",
                          ".js": "node", ".mjs": "node", ".cjs": "node"}.get(suffix)
                candidates = [f"{runner} {token}"] if runner else []
                if re.fullmatch(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+", token) and not runner:
                    candidates.append(f"python3 -m {token}")
                for base_dir in dirs:
                    for candidate in candidates:
                        target = (token if not candidate.startswith("python3 -m ")
                                  else token.replace(".", "/") + ".py")
                        if source_exists is not None and source_exists(target, base_dir):
                            found.append(("run: " + candidate, base_dir))
        return sorted(set(found))

    unbounded_calls = []
    commands = []
    for node in nodes:
        if not isinstance(node, ast.Call):
            continue
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
        if external_command(node):
            raise RuntimeError("Python execution command is externally supplied and cannot be bounded")
        for argument in loop_candidates(argument):
            try:
                if function == "asyncio.create_subprocess_exec":
                    values = [literal(arg) for arg in node.args]
                    if not values or any(type(value) is not str for value, _ in values):
                        raise RuntimeError("Python execution command cannot be bounded")
                    command = [value for value, _ in values]
                    command_origins = set().union(*(items for _, items in values))
                else:
                    command, command_origins = literal(argument)
            except _OpaquePythonValue:
                if externally_fed(node, argument):
                    raise RuntimeError("Python execution command is externally supplied and cannot be bounded")
                unbounded_calls.append(node)
                continue
            if command_origins & escaped_lists:
                raise RuntimeError("Python execution argv was mutated or escaped")
            shell = keywords.get("shell")
            if shell is not None and not (isinstance(shell, ast.Constant) and type(shell.value) is bool):
                raise RuntimeError("Python execution shell mode cannot be bounded")
            uses_shell = (function in {"os.system", "os.popen", "subprocess.getoutput",
                                      "subprocess.getstatusoutput", "asyncio.create_subprocess_shell"}
                          or (shell is not None and shell.value is True))
            if uses_shell and isinstance(command, str) and any(token in command for token in (";", "&", "|", "\n", "`", "$")):
                raise RuntimeError("Python shell delegation cannot be bounded")
            if isinstance(command, list):
                if not command:
                    raise RuntimeError("Python execution command cannot be bounded")
                argv = command
            else:
                try:
                    argv = shlex.split(command, posix=True)
                except ValueError as exc:
                    raise RuntimeError("Python execution argv cannot be bounded") from exc
            if not argv or any(any(token in argument for token in ("$", "`", "\n", "\x00")) for argument in argv):
                raise RuntimeError("Python interpreter expansion cannot be bounded")
            program = PurePosixPath(argv[0]).name
            if any(character.isspace() for character in argv[0]) or program == "env" or any(token in argv[0] for token in ("\\", ":")):
                raise RuntimeError("Python execution program cannot be bounded")
            interpreter = re.fullmatch(r"python(?:3(?:\.\d+)?)?", program) is not None
            if (interpreter or program in {"bash", "sh", "node"}) and argv[0] != program:
                raise RuntimeError("Python interpreter executable identity cannot be bounded")
            if program in {"bash", "sh"} and (len(argv) < 2 or argv[1].startswith("-")):
                raise RuntimeError("Python shell interpreter delegation cannot be bounded")
            if interpreter or program in {"bash", "sh", "node"}:
                index = 1
                while index < len(argv) and argv[index] in {"-B", "-u", "-O", "-OO"}:
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
                except _OpaquePythonValue:
                    # A dynamic cwd only matters when the command can resolve a
                    # repository script or module relative to it. A bare external
                    # program (for example ``git rev-parse HEAD``) resolves no
                    # local source; its command text remains mutation evidence.
                    if (interpreter or program in {"bash", "sh", "node"} or "/" in argv[0]
                            or program != argv[0] or not re.fullmatch(r"[A-Za-z0-9_.+-]+", program)):
                        # A local-source launch from an unknown cwd is
                        # over-approximated through the file's witnesses.
                        unbounded_calls.append(node)
                    commands.append(("run: " + command, directory))
                    continue
                if type(directory_value) is not str:
                    raise RuntimeError("Python execution working directory cannot be bounded")
                path = PurePosixPath(directory_value.replace("\\", "/"))
                if path.is_absolute() or ".." in path.parts:
                    raise RuntimeError("Python execution working directory escapes the repository")
                directory = (PurePosixPath(directory) / path).as_posix().removeprefix("./")
            commands.append(("run: " + command, directory))
    if unbounded_calls:
        commands.extend(witness_commands())
    return commands


def _referenced_sources(
    text: str,
    repo_files: dict[str, str] | None = None,
) -> list[tuple[str | None, str]]:
    """Include scripts and local actions that the workflow actually executes."""

    combined: list[tuple[str | None, str]] = [(None, text)]
    queue: list[tuple[str | None, str, int, str]] = [(None, text, 0, "")]
    visited: set[tuple[str, str]] = set()
    while queue:
        current_path, source_text, depth, inherited_directory = queue.pop()
        if depth > MAX_REFERENCE_DEPTH:
            raise RuntimeError("local writer reference depth is unbounded")
        current = _executable_text(source_text)
        is_yaml_execution_context = (
            current_path is None
            or PurePosixPath(current_path).name in {"action.yml", "action.yaml"}
        )
        is_python = current_path is not None and current_path.endswith(".py")
        contexts = (_python_command_texts(
                        source_text, inherited_directory,
                        lambda path, base_dir: _repo_source(path, repo_files, base_dir=base_dir) is not None,
                        PurePosixPath(current_path).parent.as_posix().removeprefix(".") if current_path else "")
                    if is_python else [(current, None)])
        if is_python:
            current = "\n".join(command for command, _directory in contexts)
        references: set[tuple[str, str, bool, str]] = set()
        for command_text, command_directory in contexts:
            if is_python:
                # Executed inline commands remain mutation evidence; expected
                # command strings elsewhere in Python do not become references.
                combined.append((None, command_text))
            direct_calls = {match.group("path") for match in DIRECT_SCRIPT_CALL.finditer(command_text)}
            script_calls = {match.group("path") for match in LOCAL_SCRIPT_CALL.finditer(command_text)}
            module_calls = {match.group("module") for match in LOCAL_MODULE_CALL.finditer(command_text)}
            working_directories = (_working_directories(current)
                if is_yaml_execution_context and (script_calls or direct_calls or module_calls)
                else {command_directory if command_directory is not None else inherited_directory})
            for relative_path in script_calls | direct_calls:
                references.update((relative_path, base_dir, is_python, base_dir)
                                  for base_dir in working_directories)
            for module in module_calls:
                module_path = module.replace(".", "/")
                for base_dir in working_directories:
                    alternatives = (f"{module_path}.py", f"{module_path}/__main__.py")
                    available = [path for path in alternatives
                                 if _repo_source(path, repo_files, base_dir=base_dir) is not None]
                    if is_python and not available:
                        raise RuntimeError("required local writer module is unavailable: " + module)
                    references.update((path, base_dir, False, base_dir) for path in available)

        for match in LOCAL_ACTION_CALL.finditer(current) if not is_python else ():
            action_dir = match.group("path").rstrip("/")
            references.update(
                {
                    (f"{action_dir}/action.yml", "", False, inherited_directory),
                    (f"{action_dir}/action.yaml", "", False, inherited_directory),
                }
            )

        if (
            current_path is not None
            and PurePosixPath(current_path).name in {"action.yml", "action.yaml"}
            and re.search(r"(?m)^\s*(?:runs:|using:)", current)
        ):
            action_dir = PurePosixPath(current_path).parent.as_posix()
            references.update(
                (match.group("path"), action_dir, True, inherited_directory)
                for match in ACTION_ENTRYPOINT.finditer(current)
            )
            references.update(
                (match.group("path"), action_dir, True, inherited_directory)
                for match in ACTION_DOCKER_IMAGE.finditer(current)
            )

        if (
            current_path is not None
            and PurePosixPath(current_path).name.lower().startswith("dockerfile")
        ):
            docker_dir = PurePosixPath(current_path).parent.as_posix()
            references.update(
                (relative_path, docker_dir, True, inherited_directory)
                for relative_path in _docker_local_sources(current)
            )

        for relative_path, base_dir, required, next_directory in sorted(references):
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
            visit = (normalized, next_directory)
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
            'import subprocess\nimport os\ndef run(command):\n    subprocess.run(command)\nrun(os.environ["COMMAND"])\n',
            'import subprocess, sys\nsubprocess.run(sys.argv[1:])\n',
            'import subprocess\nargv = ["python3", "scripts/writer.py"]\nargv += extra\nsubprocess.run(argv)\n',
            'import subprocess, os\nsubprocess.run(os.environ["COMMAND"])\n',
            'import subprocess\nsubprocess.run(*arguments)\n',
            'import subprocess\nsubprocess.run("python3 scripts/writer.py", **options)\n',
            'import os\nos.execv("python3", ["python3", "scripts/writer.py"])\n',
            'import subprocess\nresult = subprocess.run\ndef expose():\n    return result\n',
            'import subprocess, os\ndef expose():\n    return subprocess.run(["git", "status"], preexec_fn=os.system)\n',
            'import subprocess\ndef expose():\n    return subprocess.run(["git", "status"]).__class__(subprocess.run)\n',
        )
        for source in sources:
            with self.subTest(source=source), self.assertRaises(RuntimeError):
                self._python_wrapper_writers(source)

    def test_in_file_computed_python_commands_are_over_approximated(self) -> None:
        # A wrapper parameter or computed path cannot be reduced to one literal;
        # every existing repository script the file names is then a delegate.
        delegating = (
            'import subprocess\ndef run(command):\n    return subprocess.run(command, check=False)\n'
            'run(["python3", "scripts/writer.py"])\n',
            'import subprocess, sys\nfrom pathlib import Path\nROOT = Path(__file__).parent\n'
            'subprocess.run([sys.executable, str(ROOT / "writer.py")])\n',
            'import subprocess\ndef run(argv, cwd):\n    subprocess.run(argv, cwd=cwd)\n'
            'run(["python3", "scripts/writer.py"], cwd=".")\n',
            'import subprocess\ndef launch(args):\n    subprocess.run(["python3", *args])\nlaunch(["-m", "scripts.writer"])\n',
        )
        for source in delegating:
            with self.subTest(source=source):
                self.assertEqual(self._python_wrapper_writers(source), ["wrapper.yml"])
        harmless = (
            'import subprocess\ncommand = "harmless"\ndef run(command):\n    subprocess.run(command)\n',
            'import subprocess\ndef git(root):\n    return subprocess.run(["git", "-C", root, "ls-files"], capture_output=True).stdout\n',
            'import subprocess\nfor command in (["git", "diff", "--quiet"], ["git", "diff", "--cached", "--quiet"]):\n'
            '    subprocess.run(command, check=False)\n',
        )
        for source in harmless:
            with self.subTest(source=source):
                self.assertEqual(self._python_wrapper_writers(source), [])
        # A fixed literal loop still reaches a writer named in its elements.
        loop = 'import subprocess\nfor command in (["git", "status"], ["python3", "scripts/writer.py"]):\n    subprocess.run(command)\n'
        self.assertEqual(self._python_wrapper_writers(loop), ["wrapper.yml"])

    def test_process_module_data_members_are_not_executors(self) -> None:
        sources = (
            'import os\nflags = os.O_RDONLY | getattr(os, "O_BINARY", 0)\nfd = os.open("x", flags)\n',
            'import os\nfor name in sorted(os.listdir(".")):\n    name.endswith(".py")\n',
            'import os\nvalue = os.environ.get("X", "y")\nrecord(str(value))\n',
            'import os, sys\nos.sys.argv = ["tool", "--check"]\n',
        )
        for source in sources:
            with self.subTest(source=source):
                self.assertEqual(self._python_wrapper_writers(source), [])
        escapes = (
            'import os\nlaunch = getattr(os, "system")\n',
            'import os\nhandle(getattr(os, "system"))\n',
            'from unittest import mock\nimport subprocess\nmock.patch.object(subprocess, "run", fake)\n',
            'import os\nos.system = replacement\n',
            'import subprocess\nfor launch in (subprocess.run,):\n    launch(["python3", "scripts/writer.py"])\n',
        )
        for source in escapes:
            with self.subTest(source=source), self.assertRaises(RuntimeError):
                self._python_wrapper_writers(source)

    def test_python_process_result_data_is_not_an_escaped_executor(self) -> None:
        sources = (
            'import subprocess\ndef read():\n    base_suite = subprocess.run(["git", "status"], stdout=subprocess.PIPE)\n'
            '    return base_suite.stdout if base_suite.returncode == 0 else None\n',
            'import subprocess\nactual = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()\n'
            'require(actual == expected, "mismatch")\n',
        )
        for source in sources:
            with self.subTest(source=source):
                self.assertEqual(self._python_wrapper_writers(source), [])
        # The same result-data shape still reaches a real delegated writer.
        writer = ('import subprocess\ndef read():\n    completed = subprocess.run(["python3", "scripts/writer.py"])\n'
                  '    return completed.returncode\n')
        self.assertEqual(self._python_wrapper_writers(writer), ["wrapper.yml"])

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
