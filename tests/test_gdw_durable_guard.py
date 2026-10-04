#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Synthetic admission controls; these fixtures are not provider evidence."""
import copy
import hashlib
import pytest
import gdw_durable_guard as guard


def digest(value):
    return hashlib.sha256(guard.canonical(value)).hexdigest()


def fixture():
    variables = {"GDW_PROOF_EXPORT_MODE": "outbox", "GDW_SQLITE_JOURNAL": "DELETE"}
    names = sorted(guard.REQUIRED_SECRETS)
    observed = {"space_revision": guard.SPACE_REVISION, "stage": "PAUSED", "variables": variables,
                "secret_names": names, "variables_sha256": digest(variables)}
    value = {"schema": guard.SCHEMA, "state": "QUALIFIED_LEGACY_STARTUP_GUARD",
             "space_revision": guard.SPACE_REVISION, "image": guard.IMAGE,
             "command": ["python", "gdw_runtime.py"], "working_directory": "/app",
             "source_files_sha256": dict(guard.SOURCE_FILES),
             "observation": {"stage": "PAUSED", "observed_at": "2026-10-04T20:00:00Z",
                "public_variables_sha256": digest(variables), "secret_names_sha256": digest(names),
                "startup_overrides_absent": True},
             "native_probe": {"state": "PREWRITE_REJECTION_VERIFIED", "scope": guard.PROBE_SCOPE,
                "python_version": "3.14.0", "case_count": len(guard.CASES),
                "case_results_sha256": "a" * 64, "report_sha256": "b" * 64,
                "source_closure_sha256": digest(guard.SOURCE_FILES), "forbidden_effect_count": 0,
                "unguarded_control": "PREPARATION_WRITE_OBSERVED"}}
    return value, observed


def test_pure_guard_parser_is_detached_and_performs_no_io(monkeypatch):
    value, observed = fixture()
    monkeypatch.setattr("builtins.open", lambda *_a, **_kw: pytest.fail("pure parser performed I/O"))
    parsed = guard.validate_legacy_guard(value)
    guard.validate_legacy_guard_observation(parsed, observed)
    parsed["source_files_sha256"]["gdw_runtime.py"] = "changed"
    assert value["source_files_sha256"] == guard.SOURCE_FILES


@pytest.mark.parametrize("path,replacement", [
    (("state",), "PLANNED"), (("space_revision",), "f" * 40),
    (("image",), "python:3.14-slim"), (("command",), ["python", "serve.py"]),
    (("working_directory",), "/other"), (("observation", "stage"), "RUNNING"),
    (("observation", "startup_overrides_absent"), 1),
    (("observation", "public_variables_sha256"), "0" * 64),
    (("observation", "observed_at"), "yesterday"),
    (("native_probe", "python_version"), "3.12.14"),
    (("native_probe", "case_count"), True), (("native_probe", "forbidden_effect_count"), False),
    (("native_probe", "forbidden_effect_count"), 1),
    (("native_probe", "unguarded_control"), "NOT_RUN"),
    (("native_probe", "scope"), "COMPLETE_IMAGE_PROVEN"),
    (("source_files_sha256", "gdw_runtime.py"), "f" * 64),
])
def test_missing_native_facts_and_changed_old_source_never_qualify(path, replacement):
    value, _ = fixture()
    target = value
    for item in path[:-1]: target = target[item]
    target[path[-1]] = replacement
    with pytest.raises(guard.GuardBlocked): guard.validate_legacy_guard(value)


@pytest.mark.parametrize("name", ["PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP", "LD_PRELOAD", "PATH", "HOME"])
@pytest.mark.parametrize("location", ["variables", "secrets"])
def test_startup_overrides_are_rejected_in_public_or_secret_names(name, location):
    value, observed = fixture()
    if location == "variables": observed["variables"][name] = "untrusted"
    else: observed["secret_names"].append(name)
    with pytest.raises(guard.GuardBlocked):
        guard.validate_legacy_guard_observation(value, observed)


@pytest.mark.parametrize("stage", ["PAUSED", "RUNTIME_ERROR", "BUILDING"])
def test_partial_managed_configuration_requires_the_persistent_guard(stage):
    value, observed = fixture()
    baseline = copy.deepcopy(observed["variables"])
    expected = {**baseline, "GDW_PROOF_EXPORT_MODE": guard.EXPORT_GUARD}
    observed.update(stage=stage, variables=expected, variables_sha256=digest(expected))
    result = guard.validate_legacy_guard_observation(value, observed,
        baseline_variables=baseline, expected_variables=expected)
    assert result["variables"]["GDW_PROOF_EXPORT_MODE"] == guard.EXPORT_GUARD


@pytest.mark.parametrize("defect", ["baseline", "running", "unowned", "guard_removed", "variable_deleted", "observed_drift", "source", "secrets"])
def test_guarded_readback_cannot_rebase_or_expand_its_authority(defect):
    value, observed = fixture()
    baseline = copy.deepcopy(observed["variables"])
    expected = {**baseline, **guard.MANAGED_VARIABLES}
    observed.update(variables=copy.deepcopy(expected), variables_sha256=digest(expected))
    if defect == "baseline": baseline["OTHER"] = "new"
    elif defect == "running": observed["stage"] = "RUNNING"
    elif defect == "unowned": expected["OTHER"] = "new"
    elif defect == "guard_removed": expected["GDW_PROOF_EXPORT_MODE"] = "outbox"
    elif defect == "variable_deleted": expected.pop("GDW_SQLITE_JOURNAL")
    elif defect == "observed_drift": observed["variables"]["GDW_SQLITE_JOURNAL"] = "WAL"
    elif defect == "source": observed["space_revision"] = "f" * 40
    else: observed["secret_names"].append("UNEXPECTED_SECRET")
    with pytest.raises(guard.GuardBlocked):
        guard.validate_legacy_guard_observation(value, observed,
            baseline_variables=baseline, expected_variables=expected)


@pytest.mark.parametrize("names", [[[]], ["HF_TOKEN", "HF_TOKEN"], ["HF_TOKEN"]])
def test_malformed_duplicate_or_incomplete_secret_names_fail_closed(names):
    with pytest.raises(guard.GuardBlocked): guard.validate_environment({}, names)
