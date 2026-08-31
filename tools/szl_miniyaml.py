#!/usr/bin/env python3
"""SZL-YAML-1: a minimal, versioned YAML subset emitter and parser (stdlib only).

Why this exists: pyyaml is not guaranteed on every machine where SZL gates run.
JSON is a valid YAML 1.2 subset but unreadable for ledgers humans must audit.
This module emits a conservative block-style YAML subset and parses exactly what
it emits. Every SZL YAML artifact states `yaml_subset: SZL-YAML-1` at top level.

Subset rules (emitter guarantees, parser requires):
  - 2-space indentation; block style only (no flow collections except the
    inline empty forms `{}` and `[]`).
  - Mapping keys match ^[A-Za-z_][A-Za-z0-9_.-]*$ and are always bare.
  - Scalars: null, true, false, integers, floats, strings.
  - Strings are emitted bare only when unambiguous (alphanumeric start, no
    ": " or " #" sequences, not a reserved word, not numeric-looking);
    otherwise they are JSON double-quoted on one line.
  - Full-line comments (those starting with `#`) and blank lines are ignored by the
    parser; the emitter never produces them.

This module is deterministic: dumping the same object yields the same text,
and load(dump(obj)) == obj for every supported object.
"""

from __future__ import annotations

import json
import re

SUBSET_NAME = "SZL-YAML-1"

_RESERVED_WORDS = {"null", "true", "false", "yes", "no", "on", "off", "~"}
_INT_RE = re.compile(r"^-?(0|[1-9][0-9]*)$")
_FLOAT_RE = re.compile(r"^-?(0|[1-9][0-9]*)\.[0-9]+$")
_BARE_STR_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.,/()'@+=;<>|-]*$")
_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*$")
_MAP_ENTRY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_.-]*):(?:\s+(.*))?$")


class MiniYAMLError(ValueError):
    """Raised when text is outside the SZL-YAML-1 subset."""


def _check_key(key: object) -> str:
    if not isinstance(key, str) or not _KEY_RE.match(key):
        raise MiniYAMLError(
            f"key {key!r} is outside the SZL-YAML-1 subset "
            "(keys must match ^[A-Za-z_][A-Za-z0-9_.-]*$)"
        )
    return key


def _fmt_scalar(value: object) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, str):
        bare_ok = (
            len(value) > 0
            and _BARE_STR_RE.match(value) is not None
            and value.lower() not in _RESERVED_WORDS
            and _INT_RE.match(value) is None
            and _FLOAT_RE.match(value) is None
            and ": " not in value
            and " #" not in value
            and not value.endswith(":")
            and not value.startswith("- ")
        )
        if bare_ok:
            return value
        return json.dumps(value, ensure_ascii=False)
    raise MiniYAMLError(f"unsupported scalar type: {type(value).__name__}")


def dump(obj: object) -> str:
    """Serialize a dict/list/scalar tree to SZL-YAML-1 text."""
    lines: list[str] = []
    _emit(obj, 0, lines)
    return "\n".join(lines) + "\n"


def _emit(obj: object, indent: int, lines: list[str]) -> None:
    pad = " " * indent
    if isinstance(obj, dict):
        if not obj:
            lines.append(pad + "{}")
            return
        for key, value in obj.items():
            _check_key(key)
            if isinstance(value, dict) and value:
                lines.append(f"{pad}{key}:")
                _emit(value, indent + 2, lines)
            elif isinstance(value, list) and value:
                lines.append(f"{pad}{key}:")
                _emit(value, indent + 2, lines)
            elif isinstance(value, dict):
                lines.append(f"{pad}{key}: {{}}")
            elif isinstance(value, list):
                lines.append(f"{pad}{key}: []")
            else:
                lines.append(f"{pad}{key}: {_fmt_scalar(value)}")
        return
    if isinstance(obj, list):
        if not obj:
            lines.append(pad + "[]")
            return
        for item in obj:
            if isinstance(item, dict) and item:
                first = True
                for key, value in item.items():
                    _check_key(key)
                    prefix = f"{pad}- " if first else f"{pad}  "
                    first = False
                    if isinstance(value, dict) and value:
                        lines.append(f"{prefix}{key}:")
                        _emit(value, indent + 4, lines)
                    elif isinstance(value, list) and value:
                        lines.append(f"{prefix}{key}:")
                        _emit(value, indent + 4, lines)
                    elif isinstance(value, dict):
                        lines.append(f"{prefix}{key}: {{}}")
                    elif isinstance(value, list):
                        lines.append(f"{prefix}{key}: []")
                    else:
                        lines.append(f"{prefix}{key}: {_fmt_scalar(value)}")
            elif isinstance(item, dict):
                lines.append(f"{pad}- {{}}")
            elif isinstance(item, list):
                if item:
                    raise MiniYAMLError(
                        "non-empty lists nested directly inside lists are "
                        "outside the SZL-YAML-1 subset (wrap them in a mapping)"
                    )
                lines.append(f"{pad}- []")
            else:
                lines.append(f"{pad}- {_fmt_scalar(item)}")
        return
    # Top-level scalar: representable but unusual; emit as-is.
    lines.append(pad + _fmt_scalar(obj))


def load(text: str) -> object:
    """Parse SZL-YAML-1 text back into a dict/list/scalar tree."""
    lines: list[list] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip():
            continue
        stripped = raw.lstrip(" ")
        if stripped.startswith("#"):
            continue
        if raw != raw.rstrip():
            raise MiniYAMLError(f"line {lineno}: trailing whitespace")
        indent = len(raw) - len(stripped)
        if indent % 2 != 0:
            raise MiniYAMLError(f"line {lineno}: odd indentation")
        if "\t" in raw:
            raise MiniYAMLError(f"line {lineno}: tab character")
        lines.append([indent, stripped, lineno])
    if not lines:
        return None
    obj, index = _parse_block(lines, 0, lines[0][0])
    if index != len(lines):
        raise MiniYAMLError(f"line {lines[index][2]}: unexpected trailing content")
    return obj


def _parse_block(lines: list[list], i: int, indent: int):
    content = lines[i][1]
    if content == "-" or content.startswith("- "):
        return _parse_seq(lines, i, indent)
    return _parse_map(lines, i, indent)


def _parse_seq(lines: list[list], i: int, indent: int):
    items: list = []
    n = len(lines)
    while i < n:
        ind, content, lineno = lines[i]
        if ind != indent or not (content == "-" or content.startswith("- ")):
            break
        rest = "" if content == "-" else content[2:]
        if rest == "":
            if i + 1 < n and lines[i + 1][0] > indent:
                value, i = _parse_block(lines, i + 1, lines[i + 1][0])
                items.append(value)
            else:
                items.append(None)
                i += 1
        elif _MAP_ENTRY_RE.match(rest):
            # A mapping whose first pair is inline after the dash. Rewrite the
            # line as a mapping line at virtual indent (indent + 2) and parse.
            lines[i] = [indent + 2, rest, lineno]
            value, i = _parse_map(lines, i, indent + 2)
            items.append(value)
        else:
            items.append(_parse_scalar(rest, lineno))
            i += 1
    return items, i


def _parse_map(lines: list[list], i: int, indent: int):
    out: dict = {}
    n = len(lines)
    while i < n:
        ind, content, lineno = lines[i]
        if ind != indent:
            break
        match = _MAP_ENTRY_RE.match(content)
        if match is None:
            break
        key, rest = match.group(1), match.group(2)
        if key in out:
            raise MiniYAMLError(f"line {lineno}: duplicate key {key!r}")
        if rest is None:
            if i + 1 < n and lines[i + 1][0] > indent:
                value, i = _parse_block(lines, i + 1, lines[i + 1][0])
                out[key] = value
            else:
                out[key] = None
                i += 1
        else:
            out[key] = _parse_scalar(rest, lineno)
            i += 1
    return out, i


def _parse_scalar(token: str, lineno: int) -> object:
    if token == "null":
        return None
    if token == "true":
        return True
    if token == "false":
        return False
    if token == "{}":
        return {}
    if token == "[]":
        return []
    if _INT_RE.match(token):
        return int(token)
    if _FLOAT_RE.match(token):
        return float(token)
    if token.startswith('"'):
        try:
            value = json.loads(token)
        except json.JSONDecodeError as exc:
            raise MiniYAMLError(f"line {lineno}: bad quoted string: {exc}") from exc
        if not isinstance(value, str):
            raise MiniYAMLError(f"line {lineno}: quoted value is not a string")
        return value
    if token.startswith(("[", "{", "]", "}", "'", "|", ">", "&", "*", "!", "%")):
        raise MiniYAMLError(f"line {lineno}: token outside SZL-YAML-1 subset")
    return token
