#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Concrete managed import controls with only synthetic local executable code."""

import ast
import json
import os
from pathlib import Path
import sys

import pytest

import gdw_durable_source as source
from tests.test_gdw_durable_source import install_image, verify

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def image(tmp_path, monkeypatch):
    value, app, inputs = install_image(tmp_path / "image", contents={
        "packages/inference/src/voters/__init__.py": b"OFFLINE_MARKER = 'admitted'\n",
        "szl_unay_routes.py": (ROOT / "szl_unay_routes.py").read_bytes(),
    })
    verify(value, app, inputs)
    monkeypatch.setattr(source, "_IMPORT_POLICY", None)
    source.install_import_policy(value, app)
    monkeypatch.setenv("GDW_DURABLE_STORAGE", source.MANAGED_MODE)
    return value, app, inputs


def extract_function(filename, function_name, namespace):
    """Execute the actual source function without unrelated module startup."""
    tree = ast.parse((ROOT / filename).read_text())
    node = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == function_name)
    exec(compile(ast.Module(body=[node], type_ignores=[]), filename, "exec"), namespace)
    return namespace[function_name]


def test_verified_application_and_package_roots_are_available(image):
    _value, app, _inputs = image
    paths = [str(app), str(app / "packages"), str(app / "packages/inference/src/voters")]
    assert source.managed_import_paths(paths) == paths
    file = str(app / "packages/inference/src/voters/__init__.py")
    assert source.managed_import_file(file) == file


@pytest.mark.parametrize("path", ["/", "/app/../other", "/agentic_pinn", "/dev1_quantum_sensors",
                                 "/dev2_spoof_sda", "/dev3_fusion_pinn", "/a11oy_pr", "/src/a11oy",
                                 "/a11W", "/a11oy_e", "relative", "/untrusted/plugin.zip"])
def test_outside_or_ambiguous_source_roots_rejected(image, path):
    with pytest.raises(source.SourceBlocked): source.managed_import_paths([path])


def test_new_directory_inside_application_is_not_implicitly_admitted(image):
    _value, app, _inputs = image
    directory = app / "unreviewed"
    directory.mkdir()
    with pytest.raises(source.SourceBlocked, match="DIRECTORY_NOT_ADMITTED"):
        source.managed_import_paths([str(directory)])


def test_managed_path_cannot_be_used_before_source_admission(image, monkeypatch):
    monkeypatch.setattr(source, "_IMPORT_POLICY", None)
    with pytest.raises(source.SourceBlocked, match="ADMISSION_UNAVAILABLE"):
        source.managed_import_paths(["/app"])


def test_runtime_source_symlink_substitution_rejected_before_path_load(image, tmp_path):
    _value, app, _inputs = image
    directory = app / "packages"
    outside = tmp_path / "packages"
    directory.rename(outside)
    directory.symlink_to(outside)
    with pytest.raises(source.SourceBlocked): source.managed_import_paths([str(directory)])
    with pytest.raises(source.SourceBlocked): source.managed_import_file(str(directory / "inference/src/voters/__init__.py"))


def test_direct_loader_checks_exact_current_bytes(image):
    _value, app, _inputs = image
    path = app / "packages/inference/src/voters/__init__.py"
    path.write_bytes(b"OFFLINE_MARKER = 'changed'\n")
    with pytest.raises(source.SourceBlocked, match="FILE"):
        source.managed_import_file(str(path))


def test_legacy_path_resolution_is_unchanged_without_managed_mode(image, monkeypatch):
    monkeypatch.delenv("GDW_DURABLE_STORAGE")
    monkeypatch.setattr(source, "_IMPORT_POLICY", None)
    paths = ["/", "../legacy-layout", "/unlisted"]
    assert source.managed_import_paths(paths) is paths
    assert source.managed_import_file("legacy/source.py") == "legacy/source.py"
    source.reject_managed_generated_source()


def test_unay_actual_path_setup_excludes_parent_before_module_resolution(image, monkeypatch):
    _value, app, _inputs = image
    tree = ast.parse((ROOT / "szl_unay_routes.py").read_text())
    start = next(index for index, node in enumerate(tree.body) if isinstance(node, ast.Assign)
                 and any(isinstance(target, ast.Name) and target.id == "_HERE" for target in node.targets))
    end = next(index for index, node in enumerate(tree.body) if isinstance(node, ast.Import)
               and any(alias.name == "szl_unay" for alias in node.names))
    namespace = {"os": os, "sys": sys, "__file__": str(app / "szl_unay_routes.py")}
    old = list(sys.path)
    monkeypatch.setattr(sys, "path", [path for path in old if path not in {str(app), str(app.parent)}])
    exec(compile(ast.Module(body=tree.body[start:end], type_ignores=[]), "szl_unay_routes.py", "exec"), namespace)
    assert sys.path[0] == str(app)
    assert str(app.parent) not in sys.path
    monkeypatch.delenv("GDW_DURABLE_STORAGE")
    monkeypatch.setattr(sys, "path", list(old))
    exec(compile(ast.Module(body=tree.body[start:end], type_ignores=[]), "szl_unay_routes.py", "exec"), namespace)
    assert str(app.parent) in sys.path


def test_kernel_config_validates_all_paths_before_any_sys_path_mutation(image, monkeypatch):
    _value, app, _inputs = image
    function = extract_function("szl_hub.py", "_kernel_extend_sys_path", {"os": os, "sys": sys})
    previous = list(sys.path)
    monkeypatch.setattr(sys, "path", list(previous))
    monkeypatch.setenv("SZL_KERNEL_PATHS", str(app / "packages") + os.pathsep + "/unadmitted/kernel")
    with pytest.raises(source.SourceBlocked): function()
    assert sys.path == previous
    monkeypatch.setenv("SZL_KERNEL_PATHS", str(app / "packages"))
    function()
    assert sys.path[0] == str(app / "packages")


def test_kernel_legacy_explicit_search_path_still_operates(image, monkeypatch):
    function = extract_function("szl_hub.py", "_kernel_extend_sys_path", {"os": os, "sys": sys})
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.delenv("GDW_DURABLE_STORAGE")
    monkeypatch.setenv("SZL_KERNEL_PATHS", "/legacy/kernel")
    function()
    assert sys.path[0] == "/legacy/kernel"


def test_fundamental_developer_siblings_are_never_added_in_managed_mode(image, tmp_path, monkeypatch):
    sibling = tmp_path / "dev1_quantum_sensors"
    sibling.mkdir()
    namespace = {"os": os, "sys": sys, "_SIBLING_DIRS": {"quantum_sensor": [str(sibling)]}}
    function = extract_function("fundamental_limits.py", "_ensure_on_path", namespace)
    monkeypatch.setattr(sys, "path", list(sys.path))
    function("quantum_sensor")
    assert str(sibling) not in sys.path
    monkeypatch.delenv("GDW_DURABLE_STORAGE")
    function("quantum_sensor")
    assert sys.path[0] == str(sibling)


def test_spine_defaults_to_admitted_here_and_rejects_arbitrary_environment(image, monkeypatch):
    _value, app, _inputs = image
    namespace = {"_os": os, "List": list, "__file__": str(app / "szl_kc_jpt.py")}
    function = extract_function("szl_kc_jpt.py", "_spine_search_dirs", namespace)
    monkeypatch.delenv("A11OY_SPINE_DIRS", raising=False)
    assert function() == [str(app)]
    monkeypatch.setenv("A11OY_SPINE_DIRS", "/unadmitted/spine")
    with pytest.raises(source.SourceBlocked): function()
    monkeypatch.setenv("A11OY_SPINE_DIRS", str(app / "packages"))
    assert function() == [str(app), str(app / "packages")]


def test_spine_legacy_sibling_paths_remain_available(image, monkeypatch):
    _value, app, _inputs = image
    sibling = app.parent / "a11oy_pr"
    sibling.mkdir()
    namespace = {"_os": os, "List": list, "__file__": str(app / "szl_kc_jpt.py")}
    function = extract_function("szl_kc_jpt.py", "_spine_search_dirs", namespace)
    monkeypatch.delenv("GDW_DURABLE_STORAGE")
    monkeypatch.delenv("A11OY_SPINE_DIRS", raising=False)
    assert str(sibling) in function()


def test_actual_embedded_source_runner_cannot_execute_temporary_program_in_managed_mode(image, tmp_path, monkeypatch):
    import OUROBOROS_RUN_ALL as runner
    file = tmp_path / "offline_module.py"
    marker = tmp_path / "executed"
    file.write_text("from pathlib import Path\nPath(" + repr(str(marker)) + ").write_text('offline')\n")
    with pytest.raises(source.SourceBlocked, match="GENERATED_PROGRAM"):
        runner._load_module(file, "_offline_generated_source_control")
    assert not marker.exists()
    with pytest.raises(source.SourceBlocked, match="GENERATED_PROGRAM"):
        runner._run_all()
    assert not marker.exists()
    monkeypatch.delenv("GDW_DURABLE_STORAGE")
    runner._load_module(file, "_offline_generated_source_control")
    assert marker.read_text() == "offline"
    sys.modules.pop("_offline_generated_source_control", None)


def test_canonical_command_disables_bytecode_before_first_local_import():
    docker = (ROOT / "Dockerfile").read_text()
    command = next(line[4:] for line in docker.splitlines() if line.startswith("CMD "))
    assert json.loads(command) == ["python", "-B", "gdw_runtime.py"]
    assert "gdw_durable_source.py" in docker


def test_voter_direct_path_loader_invokes_verification_before_execution():
    tree = ast.parse((ROOT / "a11oy_v4_agent.py").read_text())
    calls = [(node.lineno, ast.unparse(node.func)) for node in ast.walk(tree) if isinstance(node, ast.Call)]
    verified = next(line for line, function in calls if function == "managed_import_file")
    executed = next(line for line, function in calls if function == "_spec.loader.exec_module")
    assert verified < executed
