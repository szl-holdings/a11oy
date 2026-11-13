"""/verify must be registered exactly once in serve.py.

Starlette matches routes in registration order, so a second GET /verify handler
is unreachable dead code that misleads readers about which page is served.
Static AST check: no import of serve.py, no network."""
import ast
import pathlib

SERVE = pathlib.Path(__file__).resolve().parents[1] / "serve.py"
VERBS = {"get", "api_route", "add_api_route", "route"}


def _get_registrations(path: str) -> list[int]:
    lines = []
    for node in ast.walk(ast.parse(SERVE.read_text(encoding="utf-8"))):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if node.func.attr not in VERBS or not isinstance(node.func.value, ast.Name) or node.func.value.id != "app":
            continue
        if not (node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value == path):
            continue
        methods = {"GET"}
        for kw in node.keywords:
            if kw.arg == "methods" and isinstance(kw.value, (ast.List, ast.Tuple)):
                methods = {e.value for e in kw.value.elts if isinstance(e, ast.Constant)}
        if "GET" in methods:
            lines.append(node.lineno)
    return lines


def test_verify_get_registered_at_most_once():
    regs = _get_registrations("/verify")
    assert len(regs) <= 1, f"GET /verify registered {len(regs)} times at lines {regs}; later ones are dead"
