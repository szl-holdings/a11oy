#!/usr/bin/env python3
"""
check_url_secret_leak.py — guard that finance API keys never leak into URLs.

a11oy_vertical_feeds.py fetches official market data (feed_polygon, _cached_fetch,
_client). The Polygon.io key is deliberately sent via an
`Authorization: Bearer <key>` HEADER and NEVER in the request URL, because
_cached_fetch embeds the failing URL in its error payloads
("{type}: {str(e)[:120]}"). A key placed in the query string would therefore
leak into a returned/cached error string. Today that safety property is only
enforced by manual grep; this guard makes it a CI check.

The guard parses the target module with Python's ast and FAILS if a secret value
(POLYGON_API_KEY or any api-key/token/secret/password-like env var, or a local
variable derived from one) is concatenated into a URL or query string. It does
NOT fire on the legitimate header usage (f"Bearer {key}") because a header string
is not a URL/query construction.

Detected leak shapes:
  - f-strings:        url = f"https://x/y?apiKey={key}"
  - concatenation:    url = base + "?apiKey=" + key
  - %-format:         url = "https://x?apiKey=%s" % key
  - str.format:       url = "https://x?apiKey={}".format(key)
  - inline env:       url = f"https://x?apiKey={os.environ['POLYGON_API_KEY']}"
  - query-param dict: client.get(url, params={"apiKey": key})

Usage:
  python3 scripts/check_url_secret_leak.py [--file a11oy_vertical_feeds.py]

Exit codes:
  0 — clean (no secret reaches a URL / query string)
  1 — a secret-in-URL / secret-in-query-param pattern was detected
  2 — configuration / usage error (e.g. file missing or unparseable)
"""

from __future__ import annotations

import argparse
import ast
import os
import re
import sys

# Env-var names (and local variables derived from them) that carry a secret.
# POLYGON_API_KEY matches via "api_key". Keep this broad — a false positive is
# cheap to allowlist, a leaked key is not.
SECRET_NAME_RX = re.compile(
    r"(api[_-]?key|apikey|access[_-]?key|secret|token|password|passwd|pwd|"
    r"credential|bearer|auth[_-]?token|client[_-]?secret)",
    re.IGNORECASE,
)

# Static text that marks an expression as URL / query-string construction:
# a scheme, a path/host separator, a query separator, or an explicit
# secret-ish query parameter assignment ("apiKey=", "token=", ...).
URL_MARKER_RX = re.compile(
    r"(https?://)|(://)|[?&]|(api[_-]?key|apikey|token|secret|access[_-]?key|"
    r"auth|key|password)\s*=",
    re.IGNORECASE,
)

# Keyword arguments to HTTP-client calls that end up in the URL's query string.
# A secret here leaks exactly like a secret concatenated into the URL literal.
# `headers=` is intentionally NOT here — that is the safe channel.
QUERY_KWARGS = {"params", "query"}


def _is_os_environ(node: ast.AST) -> bool:
    """True for the `os.environ` attribute node (os.environ[...] / os.environ.get)."""
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "environ"
        and isinstance(node.value, ast.Name)
        and node.value.id == "os"
    )


def _const_str(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def env_secret_name(node: ast.AST) -> str | None:
    """If `node` reads a secret-like environment variable, return its name.

    Handles os.environ.get("X"), os.getenv("X"), getenv("X"), os.environ["X"],
    and those wrapped in trailing calls like .strip()/.rstrip()/.lstrip().
    """
    # Unwrap trailing string method calls: os.environ.get("X", "").strip()
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        inner = env_secret_name(node.func.value)
        if inner:
            return inner

    if isinstance(node, ast.Call):
        func = node.func
        name = None
        if isinstance(func, ast.Attribute) and func.attr in ("get", "getenv"):
            # os.environ.get("X") / os.getenv("X")
            if _is_os_environ(func.value) or (
                isinstance(func.value, ast.Name) and func.value.id == "os"
            ):
                if node.args:
                    name = _const_str(node.args[0])
        elif isinstance(func, ast.Name) and func.id == "getenv":
            if node.args:
                name = _const_str(node.args[0])
        if name and SECRET_NAME_RX.search(name):
            return name

    if isinstance(node, ast.Subscript) and _is_os_environ(node.value):
        # os.environ["X"] — handle both py3.9+ (slice=Constant) shapes
        key = node.slice
        if isinstance(key, ast.Index):  # pragma: no cover (py<3.9)
            key = key.value  # type: ignore[attr-defined]
        name = _const_str(key)
        if name and SECRET_NAME_RX.search(name):
            return name

    return None


def build_taint_set(tree: ast.AST) -> set[str]:
    """Names of local variables whose value derives (directly or transitively)
    from a secret env var. Computed module-wide to a fixpoint (over-approximate,
    which for a guard errs on the safe side)."""

    def targets(stmt: ast.AST) -> list[str]:
        out: list[str] = []
        tlist: list[ast.AST] = []
        if isinstance(stmt, ast.Assign):
            tlist = list(stmt.targets)
        elif isinstance(stmt, (ast.AnnAssign, ast.AugAssign, ast.NamedExpr)):
            tlist = [stmt.target]
        for t in tlist:
            if isinstance(t, ast.Name):
                out.append(t.id)
        return out

    def rhs(stmt: ast.AST) -> ast.AST | None:
        if isinstance(stmt, (ast.Assign, ast.AugAssign, ast.NamedExpr)):
            return stmt.value
        if isinstance(stmt, ast.AnnAssign):
            return stmt.value
        return None

    assigns = [
        n
        for n in ast.walk(tree)
        if isinstance(n, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.NamedExpr))
    ]

    tainted: set[str] = set()
    changed = True
    while changed:
        changed = False
        for stmt in assigns:
            value = rhs(stmt)
            if value is None:
                continue
            if expr_has_secret(value, tainted):
                for name in targets(stmt):
                    if name not in tainted:
                        tainted.add(name)
                        changed = True
    return tainted


def expr_has_secret(node: ast.AST, tainted: set[str]) -> bool:
    """True if the expression references a secret env var or a tainted variable."""
    for sub in ast.walk(node):
        if env_secret_name(sub):
            return True
        if isinstance(sub, ast.Name) and sub.id in tainted:
            return True
    return False


def static_text(node: ast.AST) -> str:
    """Concatenate all static string literals reachable in an expression, so we
    can decide whether it is URL / query-string construction."""
    parts: list[str] = []
    for sub in ast.walk(node):
        s = _const_str(sub)
        if s is not None:
            parts.append(s)
    return " ".join(parts)


def looks_like_url_construction(node: ast.AST) -> bool:
    return bool(URL_MARKER_RX.search(static_text(node)))


def _lineno(node: ast.AST) -> int:
    return getattr(node, "lineno", 0)


def find_violations(tree: ast.AST, tainted: set[str]) -> list[tuple[int, str]]:
    violations: list[tuple[int, str]] = []

    for node in ast.walk(tree):
        # 1) Any URL/query-string construction expression that carries a secret.
        if isinstance(node, (ast.JoinedStr, ast.BinOp, ast.Call)):
            # For Call, only string-building calls (.format / urlencode) are
            # URL construction; other calls are handled via their arguments below.
            is_build = isinstance(node, (ast.JoinedStr, ast.BinOp))
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                is_build = node.func.attr in ("format", "urlencode", "join")
            if is_build and looks_like_url_construction(node) and expr_has_secret(
                node, tainted
            ):
                violations.append(
                    (
                        _lineno(node),
                        "secret value is built into a URL / query string",
                    )
                )

        # 2) A secret passed as a query-param kwarg to an HTTP client call
        #    (params=/query=) — this ends up in the request URL's query string.
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                if kw.arg in QUERY_KWARGS and expr_has_secret(kw.value, tainted):
                    violations.append(
                        (
                            _lineno(kw.value),
                            f"secret value passed via '{kw.arg}=' — it becomes a "
                            f"URL query parameter",
                        )
                    )

    # De-duplicate by (line, message) and sort.
    return sorted(set(violations))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--file",
        default=os.environ.get("URL_SECRET_LEAK_FILE", "a11oy_vertical_feeds.py"),
        help="Python file to scan (default: a11oy_vertical_feeds.py)",
    )
    args = parser.parse_args()

    path = args.file
    if not os.path.isfile(path):
        print(f"[ERROR] file not found: {path}", file=sys.stderr)
        return 2

    with open(path, "r", encoding="utf-8") as fh:
        source = fh.read()

    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError as e:
        print(f"[ERROR] could not parse {path}: {e}", file=sys.stderr)
        return 2

    tainted = build_taint_set(tree)
    violations = find_violations(tree, tainted)

    if violations:
        print("=" * 70)
        print("URL SECRET-LEAK GUARD FAILED")
        print("=" * 70)
        for line, msg in violations:
            print(f"  ✗ {path}:{line}: {msg}")
        print()
        print(
            "A finance API key (e.g. POLYGON_API_KEY) must never be concatenated "
            "into a request URL or query string: _cached_fetch embeds the failing "
            "URL in its error payloads, so a key in the URL would leak into "
            "returned/cached error strings. Send it via an "
            "'Authorization: Bearer <key>' header instead — see feed_polygon."
        )
        return 1

    print(f"[OK] {path}: no API key / secret reaches a URL or query string.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
