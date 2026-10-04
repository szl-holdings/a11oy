#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Supply-chain: pure validation of a scoped GDW base-image observation.

This record supplies an expected SQLite version. It does not observe the final
image, attest dependency contents, authorize storage, or replace the actual-host
version equality and full-state acknowledgement required before serving.
"""

from datetime import datetime
import json
import re


SCHEMA = "szl.gdw-runtime-base-observation/v1"
REPOSITORY = "szl-holdings/a11oy"
BASE_SHA256 = "caaf356f40667c496d405780745b9ac25771c189a51dfcc42430d531ea09f8a2"
BASE_REFERENCE = "docker.io/library/python@sha256:" + BASE_SHA256
PLATFORM = "linux/amd64"
EXECUTABLE = "/usr/local/bin/python"
MAX_OBSERVATION_BYTES = 16 * 1024
MAX_COMPILE_OPTIONS = 256
REQUIREMENTS = {
    "sqlite_equality": "REQUIRED_BEFORE_RESTORE_OR_CLAIM",
    "actual_host_ack": "REQUIRED_BEFORE_SERVE",
    "mismatch": "HELD_NO_LEARN_NO_RELAXATION",
}
_FIELDS = {
    "schema", "state", "repository", "source_revision", "dockerfile_sha256",
    "scope", "final_runtime", "execution", "base", "interpreter", "sqlite",
    "requirements",
}


class RuntimeBaseBlocked(RuntimeError):
    """Only fixed metadata classifications leave this boundary."""


def canonical(value) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=True, sort_keys=True,
                          separators=(",", ":"), allow_nan=False).encode("ascii") + b"\n"
    except Exception:
        raise RuntimeBaseBlocked("RUNTIME_BASE_JSON_INVALID") from None


def _shape(value, fields):
    if type(value) is not dict or len(value) != len(fields) or set(value) != fields:
        raise RuntimeBaseBlocked("RUNTIME_BASE_FIELDS_INVALID")
    return value


def _fixed(value, expected):
    if type(value) is not type(expected) or value != expected:
        raise RuntimeBaseBlocked("RUNTIME_BASE_FACT_INVALID")


def _number(value, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise RuntimeBaseBlocked("RUNTIME_BASE_NUMBER_INVALID")


def _hex(value, length=64):
    if (type(value) is not str or len(value) != length
            or re.fullmatch(r"[0-9a-f]+", value) is None or value == "0" * length):
        raise RuntimeBaseBlocked("RUNTIME_BASE_IDENTITY_INVALID")
    return value


def _sqlite_version(value):
    if (type(value) is not str or len(value) > 11
            or re.fullmatch(r"3\.(?:0|[1-9][0-9]{0,2})\.(?:0|[1-9][0-9]{0,2})", value) is None):
        raise RuntimeBaseBlocked("RUNTIME_BASE_SQLITE_VERSION_INVALID")


def _source_id(value):
    # SQLite replaces the final four hash characters with alt1/alt2 for some
    # modified builds; preserve that disclosure, never normalize it away.
    # https://www.sqlite.org/releaselog/3_21_0.html
    if (type(value) is not str or len(value) != 84
            or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2} "
                            r"(?:[0-9a-f]{64}|[0-9a-f]{60}alt[12])", value) is None
            or value[20:] == "0" * 64 or value[20:80] == "0" * 60):
        raise RuntimeBaseBlocked("RUNTIME_BASE_SQLITE_SOURCE_INVALID")
    try:
        datetime.strptime(value[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        raise RuntimeBaseBlocked("RUNTIME_BASE_SQLITE_SOURCE_INVALID") from None


def validate_runtime_base_observation(value, source_revision, dockerfile_sha256) -> dict:
    """Validate exact types/keys and source bindings, returning a detached dict.

    No filesystem, clock, process, registry, Docker, credential, or application
    access occurs here. The acquisition owner must also bind execution run IDs
    to its own canonical source context and compare the expected SQLite value.
    """
    _hex(source_revision, 40)
    _hex(dockerfile_sha256)
    _shape(value, _FIELDS)
    for key, expected in (
        ("schema", SCHEMA), ("state", "OBSERVED"), ("repository", REPOSITORY),
        ("source_revision", source_revision), ("dockerfile_sha256", dockerfile_sha256),
        ("scope", "PINNED_BASE_STDLIB_ONLY"), ("final_runtime", "FINAL_RUNTIME_NOT_OBSERVED"),
    ):
        _fixed(value[key], expected)
    execution = _shape(value["execution"], {"runner", "run_id", "run_attempt"})
    _fixed(execution["runner"], "GITHUB_ACTIONS_CANONICAL_MAIN")
    _number(execution["run_id"], 1, 2**63 - 1)
    _number(execution["run_attempt"], 1, 1000)
    base = _shape(value["base"], {"reference", "platform", "manifest_sha256", "config_sha256"})
    _fixed(base["reference"], BASE_REFERENCE)
    _fixed(base["platform"], PLATFORM)
    _hex(base["manifest_sha256"])
    _hex(base["config_sha256"])
    interpreter = _shape(value["interpreter"], {
        "implementation", "version", "executable", "isolation", "native_platform",
    })
    _fixed(interpreter["implementation"], "cpython")
    _fixed(interpreter["executable"], EXECUTABLE)
    _fixed(interpreter["isolation"], "ISOLATED_NO_SITE_NO_BYTECODE")
    _fixed(interpreter["native_platform"], PLATFORM)
    version = interpreter["version"]
    if type(version) is not list or len(version) != 3:
        raise RuntimeBaseBlocked("RUNTIME_BASE_PYTHON_VERSION_INVALID")
    _fixed(version[0], 3)
    _fixed(version[1], 14)
    _number(version[2], 0, 999)
    sqlite = _shape(value["sqlite"], {
        "python_version", "sql_version", "source_id", "compile_options_count", "compile_options_sha256",
    })
    _sqlite_version(sqlite["python_version"])
    _fixed(sqlite["sql_version"], sqlite["python_version"])
    _source_id(sqlite["source_id"])
    _number(sqlite["compile_options_count"], 1, MAX_COMPILE_OPTIONS)
    _hex(sqlite["compile_options_sha256"])
    _shape(value["requirements"], set(REQUIREMENTS))
    for key, expected in REQUIREMENTS.items():
        _fixed(value["requirements"][key], expected)
    encoded = canonical(value)
    if len(encoded) > MAX_OBSERVATION_BYTES:
        raise RuntimeBaseBlocked("RUNTIME_BASE_BOUND_INVALID")
    return json.loads(encoded)
