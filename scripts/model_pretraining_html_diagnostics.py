# SPDX-License-Identifier: Apache-2.0
"""Identify source-literal HTML additions without retaining response contents.

Diagnostic only: it never approves a transformed page, mutates a response,
imports product code, follows a network link, or reads credentials. Its output
is limited to sizes, hashes, and locations of matching checkout Python literals.
"""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path
from typing import Any

MAX_PAGE = 64 * 1024
MAX_SOURCE_FILE = 1024 * 1024
MAX_FILES = 512
MAX_SOURCE_TOTAL = 32 * 1024 * 1024
MAX_LITERAL = 4096
MAX_MATCHES = 64


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def describe_delta(root: Path, expected: bytes, actual: bytes) -> dict[str, Any]:
    """Locate a bounded changed middle; never emit its text or trust it as code.

    Only regular, root-level Python files inside this checkout are inspected.
    No directory recursion, symlink traversal, product import or deserialization.
    Incomplete coverage stays explicit; source matches are leads, not provenance.
    """
    result: dict[str, Any] = {
        'schema': 'szl.model-html-source-delta/v1', 'state': 'UNAVAILABLE',
        'responseBodyRecorded': False, 'transformationAccepted': False,
        'sourceCoverage': 'NOT_STARTED', 'matches': [],
    }
    if (type(expected) is not bytes or type(actual) is not bytes
            or not 0 < len(expected) <= MAX_PAGE or not 0 < len(actual) <= MAX_PAGE):
        result['reason'] = 'BODY_TYPE_OR_SIZE'
        return result
    if expected == actual:
        result.update(state='IDENTICAL', sourceCoverage='NOT_NEEDED')
        return result
    prefix = 0
    while prefix < min(len(expected), len(actual)) and expected[prefix] == actual[prefix]:
        prefix += 1
    suffix = 0
    remaining = min(len(expected), len(actual)) - prefix
    while suffix < remaining and expected[-1-suffix] == actual[-1-suffix]:
        suffix += 1
    before = expected[prefix:len(expected)-suffix if suffix else len(expected)]
    after = actual[prefix:len(actual)-suffix if suffix else len(actual)]
    result.update(
        state='DELTA_RECORDED_NOT_ACCEPTED', commonPrefixBytes=prefix,
        commonSuffixBytes=suffix, expectedMiddleBytes=len(before),
        observedMiddleBytes=len(after), expectedMiddleSha256=digest(before),
        observedMiddleSha256=digest(after), sourceCoverage='ROOT_PYTHON_LITERALS_ONLY',
    )
    total = 0
    inspected = 0
    partial = False
    resolved_root = root.resolve()
    candidates = sorted(root.glob('*.py'))
    for path in candidates[:MAX_FILES]:
        try:
            if path.is_symlink() or not path.is_file() or path.resolve().parent != resolved_root:
                partial = True
                continue
            size = path.stat().st_size
            if size > MAX_SOURCE_FILE or total + size > MAX_SOURCE_TOTAL:
                partial = True
                continue
            with path.open('rb') as stream:
                raw = stream.read(MAX_SOURCE_FILE + 1)
            if len(raw) > MAX_SOURCE_FILE or total + len(raw) > MAX_SOURCE_TOTAL:
                partial = True
                continue
            total += len(raw)
            tree = ast.parse(raw.decode('utf-8'))
            inspected += 1
            for node in ast.walk(tree):
                if not isinstance(node, ast.Constant) or type(node.value) not in (str, bytes):
                    continue
                literal = node.value.encode('utf-8') if type(node.value) is str else node.value
                if not 16 <= len(literal) <= MAX_LITERAL or not literal.startswith(b'<') or not literal.endswith(b'>'):
                    continue
                offset = actual.find(literal)
                if (offset < 0 or offset + len(literal) <= prefix
                        or offset >= len(actual) - suffix or literal in expected):
                    continue
                if len(result['matches']) >= MAX_MATCHES:
                    partial = True
                    break
                result['matches'].append({
                    'sourceFile': path.name, 'line': node.lineno,
                    'sourceFileSha256': digest(raw), 'literalBytes': len(literal),
                    'literalSha256': digest(literal), 'offsetInObservedBody': offset,
                })
        except (OSError, SyntaxError, UnicodeError, RecursionError, ValueError):
            partial = True
    if len(candidates) > MAX_FILES:
        partial = True
    result.update(sourceFilesParsed=inspected, sourceBytesParsed=total,
                  sourceScanIncomplete=partial)
    return result
