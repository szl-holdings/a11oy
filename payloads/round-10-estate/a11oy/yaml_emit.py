"""a11oy.yaml_emit — zero-dependency YAML emitter.

Hand-rolled emitter for the small, controlled subset of YAML used by the
ledgers and conformance profile. Emission only — no parser. The machine
source of truth is JSON/Python; YAML is the human artifact.

Zero-Bandaid Law at the type level: scalar(None) renders the literal string
UNKNOWN. An empty field reads as an oversight; UNKNOWN reads as an audited
state.
"""
from __future__ import annotations


def scalar(value) -> str:
    if value is None:
        return "UNKNOWN"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (int, float)):
        return str(value)
    s = str(value)
    if s == "" or any(c in s for c in ":#{}[]&*!|>'\"%@`") or s != s.strip():
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return s


def _emit(obj, indent: int, lines: list[str]) -> None:
    pad = "  " * indent
    if isinstance(obj, dict):
        if not obj:
            lines[-1] += " {}"
            return
        for key, value in obj.items():
            if isinstance(value, (dict, list)) and value:
                lines.append(f"{pad}{key}:")
                _emit(value, indent + 1, lines)
            elif isinstance(value, dict):
                lines.append(f"{pad}{key}: {{}}")
            elif isinstance(value, list):
                lines.append(f"{pad}{key}: []")
            else:
                lines.append(f"{pad}{key}: {scalar(value)}")
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, (dict, list)) and item:
                lines.append(f"{pad}-")
                _emit(item, indent + 1, lines)
            else:
                lines.append(f"{pad}- {scalar(item)}")
    else:
        lines.append(f"{pad}{scalar(obj)}")


def emit(obj) -> str:
    lines: list[str] = []
    _emit(obj, 0, lines)
    return "\n".join(lines) + "\n"
